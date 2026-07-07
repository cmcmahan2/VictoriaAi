"""
smoke_test.py — prove the bot wiring works end-to-end, no network required.

This is NOT the backtester (that lands in backtest/ over Phases 1-6). It is a
minimal proof-of-life: generate synthetic candles, run the REAL Strategy and
RiskEngine, simulate FAV+HEDGE fills with a PLACEHOLDER price model, settle
against ground truth, log to SQLite, and run analyze.py on the result.

The token pricing here is deliberately crude (real model arrives in
backtest/pricing.py). Treat any numbers it prints as plumbing validation only.

Run:  python smoke_test.py
"""
from __future__ import annotations

import math
import os
import random
import tempfile

import config
from analyze import analyze, print_report
from logger import TradeLogger, TradeRow
from polymarket_client import Fill, calculate_pnl
from price_feed import Candle, OrderBook, PriceFeed
from risk_engine import RiskEngine
from strategy import Strategy


def make_synth_candles(n: int, start_ts: int, seed: int = config.RANDOM_SEED) -> list[Candle]:
    """Seeded 1m candles with regime-switching drift. Synthetic — not market data.

    Real BTC trends in bursts within 5m windows; pure driftless GBM produces almost
    no tradeable signal, so we add short momentum regimes to exercise the strategy.
    """
    rng = random.Random(seed)
    price = 60000.0
    sigma = 0.0008          # ~0.08% per-minute vol
    drift = 0.0
    regime_left = 0
    candles = []
    for i in range(n):
        if regime_left <= 0:
            regime_left = rng.randint(20, 50)
            drift = rng.choice([-1, 0, 1]) * sigma * rng.uniform(1.0, 2.5)
        regime_left -= 1
        z = rng.gauss(0, 1)
        ret = drift + sigma * z
        new = price * math.exp(ret)
        hi = max(price, new) * (1 + abs(rng.gauss(0, 0.0002)))
        lo = min(price, new) * (1 - abs(rng.gauss(0, 0.0002)))
        vol = rng.uniform(5, 50)
        # taker buy share leans with the candle's return (order-flow proxy)
        buy_share = min(0.95, max(0.05, 0.5 + 0.4 * math.tanh(ret / sigma)))
        candles.append(Candle(start_ts + i * 60, price, hi, lo, new, vol, vol * buy_share))
        price = new
    return candles


def synth_orderbook(feed: PriceFeed, rng: random.Random) -> OrderBook:
    """Synthetic top-of-book whose imbalance leans with short momentum + noise.

    WARNING: this is exactly the circular signal the backtest README warns about.
    In a real deployment the imbalance comes from the live CLOB, not from price.
    """
    mom = feed.momentum(5) or 0.0
    ts = feed.trend_strength(10) or 0.0
    lean = max(-0.85, min(0.85, mom * 80 + 0.5 * ts + rng.gauss(0, 0.12)))
    base = 1000.0
    bid = base * (1 + lean)
    ask = base * (1 - lean)
    mid = 0.5
    return OrderBook(
        bids=((mid - 0.01, bid), (mid - 0.02, bid * 0.6)),
        asks=((mid + 0.01, ask), (mid + 0.02, ask * 0.6)),
    )


def placeholder_fav_price(side: str, confidence: float,
                          spread: float = 0.01, mispricing: float = 0.03) -> float:
    """Crude stand-in for the FAV token price. Real model: backtest/pricing.py.

    The market's implied prob mirrors the risk engine's win-prob mapping, minus a
    small favorable `mispricing` so the favorite is a hair cheap — i.e. an
    ARTIFICIAL baked-in edge so the pipeline actually places trades. This is the
    `mispricing` knob in miniature; it is NOT evidence the strategy works.
    """
    implied = 0.5 + 0.10 * confidence    # market's implied prob for the favorite
    return min(0.98, max(0.02, implied - mispricing + spread / 2))  # pay the ask


def main() -> None:
    rng = random.Random(config.RANDOM_SEED)
    n_windows = 300
    candles = make_synth_candles(n=config.WARMUP_CANDLES + n_windows * 5 + 10, start_ts=1_700_000_000)

    strat = Strategy()
    risk = RiskEngine()
    db_path = os.path.join(tempfile.gettempdir(), "polybot_smoke.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    log = TradeLogger(db_path)

    feed = PriceFeed(maxlen=600)
    idx = 0
    # warm up
    while idx < config.WARMUP_CANDLES:
        feed.add(candles[idx]); idx += 1

    trades = 0
    # step through 5m windows
    while idx + 5 < len(candles):
        window_open_candle = candles[idx]
        w_start = window_open_candle.ts
        price_open = candles[idx - 1].close          # close at window start
        # feed everything up to the decision point (4 of the 5 candles)
        for j in range(4):
            feed.add(candles[idx + j])
        decision_ts = w_start + (config.WINDOW_SECONDS - config.DECISION_LEAD_SECONDS)

        ob = synth_orderbook(feed, rng)
        sig = strat.evaluate(feed, ob, now_ts=decision_ts)

        if sig.should_trade:
            fav_price = placeholder_fav_price(sig.side, sig.confidence)
            hedge_price = min(0.98, (1 - fav_price) + 0.005)
            decision = risk.size(sig, fav_price, hedge_price)
            if not decision.halted:
                opp = "DOWN" if sig.side == "UP" else "UP"
                fav = Fill(sig.side, "tok_fav", fav_price, decision.fav_stake)
                hedge = Fill(opp, "tok_hedge", hedge_price, decision.hedge_stake)
                # ground truth: UP wins if window-end close > window-start close
                price_close = candles[idx + 4].close
                outcome = "UP" if price_close > price_open else "DOWN"
                pnl = calculate_pnl(fav, hedge, outcome)
                bankroll_before = risk.bankroll
                fav_won = int(sig.side == outcome)
                risk.update(bool(fav_won), pnl)
                log.log(TradeRow(
                    ts=decision_ts, window_start=w_start,
                    window_end=w_start + config.WINDOW_SECONDS,
                    hour=__import__("time").gmtime(decision_ts).tm_hour,
                    source="paper", fav_side=sig.side, signal_score=sig.score,
                    confidence=sig.confidence, fav_price=fav_price, fav_stake=decision.fav_stake,
                    outcome=outcome, fav_won=fav_won,
                    costs=config.GAS_COST, pnl=pnl, components=sig.components,
                    win_prob_est=decision.win_prob, kelly_used=decision.kelly_used,
                    hedge_price=hedge_price, hedge_stake=decision.hedge_stake,
                    fav_shares=fav.shares, hedge_shares=hedge.shares,
                    bankroll_before=bankroll_before, bankroll_after=risk.bankroll,
                    drawdown=decision.drawdown,
                ))
                trades += 1

        # advance one full window
        for j in range(4, 5):
            feed.add(candles[idx + j])
        idx += 5

    log.close()
    print("#" * 64)
    print("# SMOKE TEST — SYNTHETIC DATA, NOT A REAL RESULT")
    print("# Numbers below validate wiring only. The absurd win rate / P&L is the")
    print("# circular synthetic orderbook + baked-in mispricing edge (see README).")
    print("#" * 64)
    print(f"Smoke test: generated {trades} simulated trades over {n_windows} windows.")
    print(f"Final bankroll: ${risk.bankroll:.2f}  |  empirical win rate "
          f"{risk.empirical_winrate():.3f}  |  db={db_path}\n")
    print_report(analyze(db_path, starting_bankroll=config.STARTING_BANKROLL))


if __name__ == "__main__":
    main()
