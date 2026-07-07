"""
config.py — stock-desk tunables (the wheel + congressional copy-trading).

Defaults are reasonable, NOT proven. Backtest first; paper-trade before real money.
Options + leverage can lose more than the premium you collect.
"""
from __future__ import annotations

TICKER = "AAPL"
LOOKBACK_DAYS = 730
START_CAPITAL = 50_000.0
RISK_FREE = 0.04

# ---- wheel strategy ----
PUT_STRIKE_PCT = 0.07        # sell cash-secured put this far BELOW spot
CALL_STRIKE_PCT = 0.07       # sell covered call this far ABOVE cost basis
EXPIRY_DAYS = 21             # ~3 weeks to expiration
PROFIT_TAKE = 0.50           # buy back a contract once it's down to 50% of premium
VOL_LOOKBACK = 20            # days of realized vol feeding the option model
CONTRACTS = 1               # 1 contract = 100 shares
FEE_PER_CONTRACT = 0.65     # options commission per contract per side
SLIPPAGE_PCT = 0.02         # haircut on modeled premium (IV/spread realism)

# ---- congressional copy-trading ----
COPY_NOTIONAL = 5_000.0      # $ per copied position
DISCLOSURE_LAG_DAYS = 30     # politicians report weeks late — copy AFTER the lag
CONGRESS_SOURCE = "capitoltrades"   # see congress.py docstring for what's obtainable

SEED = 1337
