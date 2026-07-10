"""
config.py — all tunable parameters for the Polymarket BTC 5-minute bot.

Everything the strategy / risk engine reads lives here so it can be swept by the
backtester without touching logic. Values are deliberately conservative defaults;
they are NOT proven — tune them with walk-forward backtesting before risking money.

The composite signal is a weighted sum of 7 indicator sub-signals, each squashed
to [-1, +1]. WEIGHTS must sum to 1.0 so the composite also lands in [-1, +1].
`orderbook_imbal` carries the most weight and is the intended primary edge — but
see the backtest README: in any backtest that signal is *synthetic*, not real.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# Composite signal weights (must sum to 1.0). The 7 indicators.
# --------------------------------------------------------------------------- #
WEIGHTS: dict[str, float] = {
    "orderbook_imbal": 0.25,  # CLOB bid/ask imbalance — the primary (real) edge
    "ema_cross":       0.18,  # fast EMA vs slow EMA (trend direction)
    "macd":            0.15,  # MACD histogram (trend momentum)
    "rsi":             0.12,  # RSI distance from 50 (momentum)
    "momentum":        0.12,  # raw rate-of-change over a short lookback
    "volume_delta":    0.10,  # taker buy/sell imbalance
    "trend_strength":  0.08,  # Kaufman efficiency ratio, signed (trend quality)
}

# --------------------------------------------------------------------------- #
# Signal / decision timing
# --------------------------------------------------------------------------- #
SIGNAL_THRESHOLD = 0.15        # |composite| must exceed this to take a trade
DECISION_LEAD_SECONDS = 240    # decide this many seconds before the 5m window closes
                               # (~1 min into the window, 4 min to resolution). Decide
                               # early so token prices aren't already pinned near 0/1
                               # and the directional signal can actually express; a
                               # small lead leaves the favorite priced ~0.9, unbuyable.
WINDOW_SECONDS = 300           # Polymarket BTC market cadence (5 minutes)

# --------------------------------------------------------------------------- #
# Indicator parameters (in 1-minute candles)
# --------------------------------------------------------------------------- #
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
MOMENTUM_LOOKBACK = 10
VOL_DELTA_LOOKBACK = 5
TREND_LOOKBACK = 20
VOL_WINDOW = 30                # candles used to estimate realized 1m volatility
WARMUP_CANDLES = 40            # min candles before the strategy will emit a signal

# Squash gains: convert raw indicator magnitudes to roughly [-1, 1] via tanh(k*x).
# These are scale factors only; they shape sensitivity, not direction.
K_EMA = 120.0                  # applied to (ema_fast - ema_slow) / ema_slow
K_MACD = 60.0                  # applied to macd_hist / price
K_MOMENTUM = 50.0              # applied to fractional momentum

# --------------------------------------------------------------------------- #
# Risk / position sizing (fractional Kelly)
# --------------------------------------------------------------------------- #
STARTING_BANKROLL = 100.0
KELLY_FRACTION = 0.15          # fraction of full-Kelly stake to deploy (¼ risks ruin)
HEDGE_FRACTION = 0.35          # HEDGE stake as a fraction of the FAV stake
MAX_POSITION_FRAC = 0.04       # cap any single FAV stake at 4% of bankroll
MIN_STAKE = 1.0                # don't bother trading below this dollar stake

# Bayesian win-rate tracking: Beta(alpha, beta) posterior over the FAV win prob.
# Start with a weak, slightly-pessimistic prior centered just under 50%.
PRIOR_WINS = 5.0
PRIOR_LOSSES = 5.0

# How much to trust the live signal vs. the empirical (Bayesian) win rate when
# estimating p for Kelly. 1.0 = trust signal fully, 0.0 = trust history fully.
# (At 0.5 the blend halves signal confidence toward the 0.5 prior, leaving the bot
# unable to ever justify buying a favorite — 0.7 keeps it coherent.)
SIGNAL_TRUST = 0.7
# Max win-prob the signal alone is allowed to imply (keeps Kelly from going wild).
MAX_SIGNAL_WINPROB = 0.85

# --------------------------------------------------------------------------- #
# Drawdown control
# --------------------------------------------------------------------------- #
MAX_DRAWDOWN = 0.50           # halt all trading once bankroll is 50% below peak
DERISK_DRAWDOWN = 0.30        # start scaling size down past 30% drawdown
                             # (0.35/0.20 was a hair-trigger that halted on normal
                             #  Kelly variance, truncating otherwise-valid backtests)

# --------------------------------------------------------------------------- #
# Hour filter (UTC). Only trade during these hours. Full set = trade always.
# --------------------------------------------------------------------------- #
ALLOWED_HOURS: set[int] = set(range(24))

# --------------------------------------------------------------------------- #
# Costs
# --------------------------------------------------------------------------- #
GAS_COST = 0.02               # $ per trade, Polygon gas (round trip approx)
POLYMARKET_FEE = 0.07         # crypto TAKER fee rate, Fee V2 (live-verified 2026-07-06,
                              # polyfunnel/docs/GROUND_TRUTH.md): fee = shares·rate·p·(1−p),
                              # takers only, makers pay 0. For a BUY staking S dollars at
                              # price p this equals S·rate·(1−p). Rate is per-market and has
                              # changed silently — read feeSchedule live before real trading.

# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #
RANDOM_SEED = 1337            # reproducibility for any stochastic component


def snapshot() -> dict:
    """Return a JSON-serializable dict of every config value, for report headers."""
    import sys
    mod = sys.modules[__name__]
    out: dict = {}
    for k in dir(mod):
        if k.isupper():
            v = getattr(mod, k)
            out[k] = sorted(v) if isinstance(v, set) else v
    return out
