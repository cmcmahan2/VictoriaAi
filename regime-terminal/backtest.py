"""
backtest.py — leveraged, walk-forward, look-ahead-free backtest.

For each rolling window we RETRAIN the HMM on the train slice and read regimes on
the test slice via the CAUSAL filtered posterior (with train context for warm
start). We never train on the future. Then we simulate a leveraged long that:
  enters on a confident bull regime + k-of-n confirmations,
  exits immediately on bear/crash (or after MIN_HOLD on a drift to neutral),
  respects a post-exit cooldown,
applying fees, slippage, and funding, and modeling liquidation.

Metrics are honest: total return, CAGR, Sharpe/Sortino, max drawdown, win rate,
exposure, and ALPHA vs buy-and-hold over the same covered span.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import config
from regimes import RegimeModel
from strategy import Indicators, count_passed, decide, target_dir

HOURS_PER_YEAR = 24 * 365


@dataclass
class Trade:
    entry_ts: int
    exit_ts: int
    entry_price: float
    exit_price: float
    bars_held: int
    ret_pct: float            # leveraged equity return for the trade
    reason_in: str
    reason_out: str


@dataclass
class BacktestResult:
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)   # (ts, equity)
    bh_curve: list = field(default_factory=list)        # (ts, buy&hold equity)
    overlay: list = field(default_factory=list)         # (ts, close, stance) causal
    metrics: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# stats (stdlib)
# --------------------------------------------------------------------------- #
def _sharpe(rets, ppy=HOURS_PER_YEAR):
    if len(rets) < 2:
        return 0.0
    m = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
    return (m / sd) * math.sqrt(ppy) if sd else 0.0


def _sortino(rets, ppy=HOURS_PER_YEAR):
    if len(rets) < 2:
        return 0.0
    m = sum(rets) / len(rets)
    dn = [r for r in rets if r < 0]
    if not dn:
        return float("inf")
    dd = math.sqrt(sum(r * r for r in dn) / len(dn))
    return (m / dd) * math.sqrt(ppy) if dd else 0.0


def _max_dd(curve):
    peak, worst = (curve[0] if curve else 0.0), 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return worst


# --------------------------------------------------------------------------- #
# walk-forward causal regime stream -> per-bar (stance, conf, name)
# --------------------------------------------------------------------------- #
def _est_folds(n, train, test, step):
    c, start = 0, 0
    while start + train + 1 < n and start + train < n:
        if start + train >= n:
            break
        c += 1
        start += step
    return max(c, 1)


def walk_forward_regimes(bars, cfg=config, progress=None):
    train = cfg.WALK_FORWARD_TRAIN_DAYS * 24
    test = cfg.WALK_FORWARD_TEST_DAYS * 24
    step = cfg.WALK_FORWARD_STEP_DAYS * 24
    n = len(bars)
    out: dict[int, tuple] = {}
    folds = 0
    n_est = _est_folds(n, train, test, step)
    start = 0
    while start + train + 1 < n:
        tr_lo, tr_hi = start, start + train
        te_lo, te_hi = tr_hi, min(tr_hi + test, n)
        if te_lo >= te_hi:
            break
        if progress:
            progress(f"Training regime HMM — fold {folds + 1}/{n_est}…",
                     0.10 + 0.65 * folds / max(n_est, 1))
        model = RegimeModel(cfg.N_STATES, tuple(cfg.FEATURES), seed=cfg.SEED)
        # train on the train slice (cheaper restarts during WF)
        import config as _c
        _saved = _c.HMM_N_INIT
        _c.HMM_N_INIT = cfg.WALK_FORWARD_N_INIT
        try:
            model.fit(bars[tr_lo:tr_hi])
        finally:
            _c.HMM_N_INIT = _saved
        # causal filtered read over train+test slice; keep only the test portion
        stream = model.regime_stream(bars[tr_lo:te_hi], smooth=False)
        for (i, k, prob, stance, name) in stream:
            abs_idx = tr_lo + i
            if te_lo <= abs_idx < te_hi:
                out[abs_idx] = (stance, prob, name)
        folds += 1
        start += step
    return out, folds


def train_once_regimes(bars, cfg=config, progress=None):
    """Faster, mildly-leaky alternative: one HMM on all bars (params see the whole
    series), causal filtered read. Use only for quick looks; WF is the honest path."""
    if progress:
        progress("Training regime HMM (train-once)…", 0.30)
    model = RegimeModel(cfg.N_STATES, tuple(cfg.FEATURES), seed=cfg.SEED).fit(bars)
    out = {}
    for (i, k, prob, stance, name) in model.regime_stream(bars, smooth=False):
        out[i] = (stance, prob, name)
    return out, 1, model


# --------------------------------------------------------------------------- #
# simulate
# --------------------------------------------------------------------------- #
def run_backtest(bars, cfg=config, walk_forward=True, progress=None,
                 allow_short=None) -> BacktestResult:
    ind = Indicators(bars, cfg)
    if allow_short is None:
        allow_short = getattr(cfg, "ALLOW_SHORT", False)
    if walk_forward:
        regimes, folds = walk_forward_regimes(bars, cfg, progress=progress)
    else:
        regimes, folds, _ = train_once_regimes(bars, cfg, progress=progress)
    if progress:
        progress("Simulating leveraged trades…", 0.85)

    covered = sorted(i for i in regimes if 0 < i < len(bars))
    res = BacktestResult(meta={"walk_forward": walk_forward, "folds": folds,
                               "leverage": cfg.LEVERAGE, "bars": len(bars),
                               "covered": len(covered)})
    if not covered:
        res.metrics = {"trades": 0}
        return res

    L = cfg.LEVERAGE
    cost_rate = (cfg.FEE_BPS + cfg.SLIPPAGE_BPS) / 1e4
    funding_bar = cfg.FUNDING_BPS_PER_8H / 1e4 / 8.0

    equity = cfg.START_CAPITAL
    bh_units = cfg.START_CAPITAL / bars[covered[0]].close   # buy&hold from first covered bar
    pos_dir = 0                          # -1 short, 0 flat, +1 long
    entry_price = entry_ts = 0.0
    entry_equity = 0.0
    bars_held = 0
    bars_since_exit = 10 ** 9
    reason_in = ""
    bar_rets = []
    liquidations = 0

    prev_close = bars[covered[0]].close
    for idx in covered:
        b = bars[idx]
        # 1) mark-to-market the open position into this bar (signed by direction)
        if pos_dir != 0:
            r = b.close / prev_close - 1.0
            growth = 1.0 + L * pos_dir * r - funding_bar
            if growth <= 0:                      # liquidation (long crash or short squeeze)
                equity = 0.0
                liquidations += 1
                res.trades.append(Trade(int(entry_ts), int(b.ts), entry_price, b.close,
                                        bars_held, -1.0, reason_in, "LIQUIDATED"))
                pos_dir = 0
                bars_since_exit = 0
                prev_close = b.close
                res.equity_curve.append((b.ts, equity))
                res.bh_curve.append((b.ts, bh_units * b.close))
                res.overlay.append((b.ts, b.close, regimes[idx][0]))
                bar_rets.append(-1.0)
                continue
            new_equity = equity * growth
            bar_rets.append(new_equity / equity - 1.0)
            equity = new_equity
            bars_held += 1
        else:
            bar_rets.append(0.0)
        prev_close = b.close

        # 2) decide target direction using info known at bar close
        stance, conf, name = regimes[idx]
        n_confirm, _ = count_passed(ind, idx)
        tgt, reason = target_dir(stance, conf, n_confirm, pos_dir, bars_held,
                                 bars_since_exit, allow_short, cfg)

        if tgt != pos_dir:
            if pos_dir != 0:                      # close current leg
                equity *= (1.0 - cost_rate * L)
                res.trades.append(Trade(int(entry_ts), int(b.ts), entry_price, b.close,
                                        bars_held, equity / entry_equity - 1.0, reason_in, reason))
                pos_dir = 0
                bars_since_exit = 0
            if tgt != 0:                          # open new leg
                equity *= (1.0 - cost_rate * L)
                pos_dir = tgt
                entry_price, entry_ts = b.close, b.ts
                entry_equity = equity
                bars_held = 0
                reason_in = ("LONG " if tgt > 0 else "SHORT ") + reason
        elif pos_dir == 0:
            bars_since_exit += 1

        res.equity_curve.append((b.ts, equity))
        res.bh_curve.append((b.ts, bh_units * b.close))
        res.overlay.append((b.ts, b.close, stance))

    res.metrics = _metrics(res, cfg, bar_rets, covered, bars, liquidations)
    return res


def _metrics(res, cfg, bar_rets, covered, bars, liquidations):
    eq = [e for _, e in res.equity_curve]
    final = eq[-1]
    start = cfg.START_CAPITAL
    total_ret = final / start - 1.0
    span_days = (bars[covered[-1]].ts - bars[covered[0]].ts) / 86400.0 or 1e-9
    years = span_days / 365.0
    try:
        cagr = (final / start) ** (1 / years) - 1 if years > 0 and final > 0 else -1.0
    except OverflowError:
        cagr = float("inf")
    bh_final = res.bh_curve[-1][1]
    bh_ret = bh_final / start - 1.0
    wins = [t for t in res.trades if t.ret_pct > 0]
    in_pos_bars = sum(1 for r in bar_rets if r != 0.0)
    return {
        "trades": len(res.trades),
        "win_rate": (len(wins) / len(res.trades)) if res.trades else 0.0,
        "total_return": total_ret,
        "cagr": cagr,
        "buy_hold_return": bh_ret,
        "alpha_vs_bh": total_ret - bh_ret,
        "sharpe": _sharpe(bar_rets),
        "sortino": _sortino(bar_rets),
        "max_drawdown": _max_dd(eq),
        "exposure": in_pos_bars / len(bar_rets) if bar_rets else 0.0,
        "final_equity": final,
        "start_capital": start,
        "span_days": span_days,
        "liquidations": liquidations,
        "avg_trade_ret": (sum(t.ret_pct for t in res.trades) / len(res.trades)) if res.trades else 0.0,
    }
