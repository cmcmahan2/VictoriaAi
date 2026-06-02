"""
config.py — Regime Terminal tunables.

Two layers, kept deliberately separate (the video's key insight):
  * REGIME layer  — the HMM. Stable; rarely changes. Detects the market state.
  * STRATEGY layer — what you DO in each regime. Adapts; tune this over time.

None of these defaults are proven. Validate walk-forward (backtest.py) before
risking leveraged capital. Leverage magnifies losses as much as gains.
"""
from __future__ import annotations

# ----------------------------- data -------------------------------------- #
TICKER = "BTC-USD"
INTERVAL = "1h"
LOOKBACK_DAYS = 730            # ~2 years of hourly bars

# ----------------------------- regime (HMM) ------------------------------ #
N_STATES = 7                  # regimes (video uses 7)
# Validated choice: returns+range recover planted regimes at ~98%; adding the
# video's volume_change drops that to ~53% (a first-difference is regime-noise).
# Selectable: "returns","range","volume_change","rel_volume".
FEATURES = ["returns", "range"]
HMM_MAX_ITER = 100
HMM_TOL = 1e-4
HMM_MIN_VAR = 1e-2            # variance floor (features are z-scored ~unit var);
                             # prevents a state collapsing onto outlier bars
HMM_SELF_TRANS_PRIOR = 0.95   # regimes are sticky
HMM_N_INIT = 6                # EM random restarts (avoid local optima)
SEED = 1337

# How regimes are read for DECISIONS. 'filter' = causal (no look-ahead) — correct
# for trading/backtest. 'smooth'/'viterbi' use the full sequence (look-ahead) and
# are for the visual overlay ONLY.
REGIME_INFERENCE = "filter"

# ----------------------------- strategy ---------------------------------- #
LEVERAGE = 2.5                # you said you trade leverage; this scales P&L AND risk
CONFIRMATIONS_REQUIRED = 7    # of CONFIRMATIONS_TOTAL must pass to enter
CONFIRMATIONS_TOTAL = 8
MIN_REGIME_CONFIDENCE = 0.60  # filtered P(regime) must exceed this to act
MIN_HOLD_HOURS = 6            # hysteresis: ignore regime flips shorter than this
COOLDOWN_HOURS = 48           # no re-entry for this long after an exit

# confirmation thresholds (the adaptive part — tune over time)
RSI_MAX = 90.0                # don't chase blow-off tops
RSI_PERIOD = 14
ADX_MIN = 20.0                # require some trend strength
ADX_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
MOMENTUM_LOOKBACK = 24        # hours
VOL_LOOKBACK = 24
VOLUME_MA = 24
MA_FAST, MA_SLOW = 24, 72     # price > MA confirmations

# ----------------------------- risk / costs ------------------------------ #
START_CAPITAL = 10_000.0
FEE_BPS = 5.0                 # taker fee per side, basis points (0.05%)
SLIPPAGE_BPS = 2.0
FUNDING_BPS_PER_8H = 1.0      # perp funding drag while in a position (approx)

# ----------------------------- backtest ---------------------------------- #
WALK_FORWARD_TRAIN_DAYS = 120  # retrain HMM on a rolling window (no look-ahead)
WALK_FORWARD_TEST_DAYS = 30
WALK_FORWARD_STEP_DAYS = 30
WALK_FORWARD_N_INIT = 3        # EM restarts during walk-forward (fewer = faster)
RETRAIN_HMM_WALK_FORWARD = True


def snapshot() -> dict:
    import sys
    mod = sys.modules[__name__]
    return {k: getattr(mod, k) for k in dir(mod) if k.isupper()}
