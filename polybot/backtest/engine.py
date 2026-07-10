"""
backtest/engine.py — PHASE 3: the look-ahead-free replay.

Replays 1m candles chronologically. For each 5m window it reconstructs the
PriceFeed using ONLY candles whose close time is <= the decision time, builds a
modeled orderbook, then calls the REAL Strategy and RiskEngine (imported, never
reimplemented), simulates FAV+HEDGE fills at modeled prices + slippage, settles
against the ground-truth outcome, and logs each trade with logger.py's schema.

NO-LOOK-AHEAD is enforced by construction (only past candles are fed) AND asserted
at every decision. The realized outcome is read ONLY for settlement, never for the
signal — except in orderbook 'edge' mode, the explicit look-ahead stress test.

  python -m backtest.engine --days 180                 # real data (run locally)
  python -m backtest.engine --days 60 --synthetic      # sandbox demo
  python -m backtest.engine --days 180 --mispricing 0.03 --orderbook momentum
"""
from __future__ import annotations

import argparse
import os
import time
import types
from dataclasses import dataclass

import config
from logger import TradeLogger, TradeRow
from polymarket_client import Fill, calculate_pnl
from price_feed import PriceFeed
from risk_engine import RiskEngine
from strategy import Strategy

from backtest.data import compute_outcomes, get_candles, synthetic_candles
from backtest.pricing import BacktestConfig, Pricer, git_hash


def config_with(**overrides) -> types.SimpleNamespace:
    """A config-like namespace (all UPPERCASE config attrs) with overrides, so
    walk-forward/optimize can vary params WITHOUT mutating globals or the logic."""
    base = {k: getattr(config, k) for k in dir(config) if k.isupper()}
    base.update(overrides)
    return types.SimpleNamespace(**base)


@dataclass
class BacktestResult:
    rows: list[TradeRow]
    final_bankroll: float
    starting_bankroll: float
    empirical_winrate: float
    candle_span_days: float
    bt_cfg: BacktestConfig
    cfg_overrides: dict
    meta: dict


def run_backtest(
    candles,
    bt_cfg: BacktestConfig | None = None,
    *,
    cfg_overrides: dict | None = None,
    weights: dict | None = None,
    db_path: str | None = None,
    source: str = "backtest",
    data_source: str = "unknown",
) -> BacktestResult:
    bt_cfg = bt_cfg or BacktestConfig()
    cfg_overrides = dict(cfg_overrides or {})
    cfg = config_with(**cfg_overrides)
    strat = Strategy(cfg=cfg, weights=weights or cfg.WEIGHTS)
    risk = RiskEngine(cfg=cfg)
    pricer = Pricer(bt_cfg)
    import random
    rng = random.Random(bt_cfg.seed)

    outcomes = compute_outcomes(candles)
    outcome_by_w = {o.window_start: o for o in outcomes}
    windows = sorted(outcome_by_w)

    feed = PriceFeed(maxlen=200)
    ci, n = 0, len(candles)
    rows: list[TradeRow] = []
    lookahead_checks = 0
    halted_at: int | None = None  # first decision time the drawdown halt fired post-trade

    for W in windows:
        o = outcome_by_w[W]
        decision_ts = W + config.WINDOW_SECONDS - bt_cfg.decision_lead

        # feed ONLY candles that have closed by the decision time
        while ci < n and candles[ci].close_time <= decision_ts:
            feed.add(candles[ci]); ci += 1
        if feed.last is None:
            continue

        # --- NO-LOOK-AHEAD GUARD (non-negotiable) ---
        assert feed.last.close_time <= decision_ts, (
            f"look-ahead: last candle closes {feed.last.close_time} > "
            f"decision {decision_ts}")
        lookahead_checks += 1

        price_t, price_open = feed.price, o.price_open
        if not price_open or price_open <= 0:
            continue
        move = (price_t - price_open) / price_open
        sigma = feed.realized_vol(bt_cfg.sigma_window) or bt_cfg.sigma_floor
        tau_min = (o.window_end - decision_ts) / 60.0
        mid_up, mid_down = pricer.mids(move, sigma, tau_min)

        # outcome is handed to the orderbook ONLY in the 'edge' stress mode
        up_wins = (o.outcome == "UP") if bt_cfg.orderbook_mode == "edge" else None
        ob = pricer.orderbook(rng, feed.momentum(config.MOMENTUM_LOOKBACK), up_wins)

        sig = strat.evaluate(feed, ob, now_ts=decision_ts)
        if not sig.should_trade:
            continue

        fav_price, hedge_price = pricer.fills(sig.side, mid_up, mid_down)
        dec = risk.size(sig, fav_price, hedge_price)
        if dec.halted:
            if dec.reason == "drawdown_halt" and rows and halted_at is None:
                halted_at = decision_ts  # the live bot would stop trading here
            continue

        opp = "DOWN" if sig.side == "UP" else "UP"
        fav = Fill(sig.side, f"{sig.side}_tok", fav_price, dec.fav_stake)
        hedge = Fill(opp, f"{opp}_tok", hedge_price, dec.hedge_stake)

        # ---- settlement (FIRST read of the realized outcome) ----
        pnl = calculate_pnl(fav, hedge, o.outcome, gas_cost=bt_cfg.gas, fee_rate=bt_cfg.fee)
        # taker fee per leg = stake·rate·(1−price)  (Fee V2 curve, matches calculate_pnl)
        costs = bt_cfg.gas + bt_cfg.fee * (
            dec.fav_stake * (1.0 - fav_price) + dec.hedge_stake * (1.0 - hedge_price))
        bankroll_before = risk.bankroll
        fav_won = int(sig.side == o.outcome)
        risk.update(bool(fav_won), pnl)

        rows.append(TradeRow(
            ts=decision_ts, window_start=W, window_end=o.window_end,
            hour=time.gmtime(decision_ts).tm_hour, source=source,
            fav_side=sig.side, signal_score=sig.score, confidence=sig.confidence,
            fav_price=fav_price, fav_stake=dec.fav_stake, outcome=o.outcome,
            fav_won=fav_won, costs=costs, pnl=pnl, components=sig.components,
            win_prob_est=dec.win_prob, kelly_used=dec.kelly_used,
            fav_token=fav.token, hedge_token=hedge.token,
            hedge_price=hedge_price, hedge_stake=dec.hedge_stake,
            fav_shares=fav.shares, hedge_shares=hedge.shares,
            bankroll_before=bankroll_before, bankroll_after=risk.bankroll,
            drawdown=dec.drawdown,
        ))

    if db_path:
        if os.path.exists(db_path):
            os.remove(db_path)
        log = TradeLogger(db_path)
        for r in rows:
            log.log(r)
        log.close()

    span = (candles[-1].ts - candles[0].ts) / 86400.0 if candles else 0.0
    return BacktestResult(
        rows=rows, final_bankroll=risk.bankroll,
        starting_bankroll=cfg.STARTING_BANKROLL,
        empirical_winrate=risk.empirical_winrate(),
        candle_span_days=span, bt_cfg=bt_cfg, cfg_overrides=cfg_overrides,
        meta={
            "git_hash": git_hash(),
            "windows": len(windows),
            "decisions_checked": lookahead_checks,
            "trades": len(rows),
            "candles": len(candles),
            "data_source": data_source,
            "halted_at": halted_at,
            "halt_day": ((halted_at - rows[0].ts) / 86400.0
                         if halted_at and rows else None),
        },
    )


def _load_candles(args) -> list:
    if args.synthetic:
        print(f"[synthetic] {args.days}d seeded candles (NOT real data)…")
        return synthetic_candles(days=args.days)
    print(f"[binance] fetching {args.days}d BTCUSDT 1m klines…")
    try:
        return get_candles(days=args.days)
    except RuntimeError as e:
        print(f"\n  ✗ {e}\n  Sandbox blocks exchanges. Run locally, or use "
              f"--synthetic for a demo.\n")
        raise SystemExit(2)


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 3 — run the backtest")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--mispricing", type=float, default=BacktestConfig.mispricing)
    ap.add_argument("--spread", type=float, default=BacktestConfig.spread)
    ap.add_argument("--slippage", type=float, default=BacktestConfig.slippage)
    ap.add_argument("--orderbook", default=BacktestConfig.orderbook_mode,
                    choices=["noise", "momentum", "edge"])
    ap.add_argument("--orderbook-edge", type=float, default=BacktestConfig.orderbook_edge)
    ap.add_argument("--db", default="backtest_trades.db")
    ap.add_argument("--html", default="reports/backtest.html")
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()

    candles = _load_candles(args)
    bt_cfg = BacktestConfig(
        mispricing=args.mispricing, spread=args.spread, slippage=args.slippage,
        orderbook_mode=args.orderbook, orderbook_edge=args.orderbook_edge,
    )
    res = run_backtest(candles, bt_cfg, db_path=args.db,
                       data_source="synthetic" if args.synthetic else "binance")
    print(f"\n  trades={res.meta['trades']}  windows={res.meta['windows']}  "
          f"final=${res.final_bankroll:.2f}  git={res.meta['git_hash']}")
    print(f"  wrote {args.db}")

    if not args.no_report:
        from backtest.report import build_report
        build_report(args.db, res, html_path=args.html)


if __name__ == "__main__":
    main()
