"""
backtest/pricing.py — PHASE 2: modeled token prices + synthetic orderbook.

We almost certainly lack historical Polymarket token prices and CANNOT retrieve
historical order books, so we MODEL both. Everything here is an explicit modeling
assumption, surfaced as a knob on `BacktestConfig` so it is visible and sweepable.

TOKEN PRICE MODEL
-----------------
At decision time t inside window [W, W+300], with time_remaining τ (minutes):
    move  = (price_t - price_open) / price_open          # how far BTC has moved
    σ     = recent realized 1-minute volatility
    P_up  = Φ( move / (σ · √τ) )                          # fair UP probability
Derivation: under driftless Gaussian returns, the remaining return is N(0, σ²τ),
and UP wins iff that return exceeds -move, which has probability Φ(move/(σ√τ)).

EDGE / MISPRICING (single knob)
-------------------------------
`mispricing` = how much cheaper than fair the market prices the FAVORITE (the more
likely side). market_fav = fair_fav - mispricing. If >0, buying the favorite has
positive expected value — this is where any backtested edge comes from. Default 0
(efficient market) so the out-of-the-box backtest is the HONEST null: pay fair
value, lose to costs. Sweep it up to ask "how much edge would we need?"

ORDERBOOK (synthetic — the single biggest limitation)
-----------------------------------------------------
`orderbook_imbal` is 25% of the live signal but cannot be replayed from history.
Modes (default 'noise'):
  * 'noise'    : imbalance ~ N(0, orderbook_noise). NO future information. The honest
                 default — the 25% signal contributes nothing real, so measured edge
                 comes only from the 6 price indicators + mispricing.
  * 'momentum' : imbalance leans with recent price momentum (+ noise). Mildly
                 circular: re-expresses momentum the other indicators already see.
  * 'edge'     : imbalance leaks a fraction (`orderbook_edge`) of the realized
                 outcome. DELIBERATE look-ahead — a stress test only, NEVER a result.
                 The engine passes the outcome here ONLY in this mode.
"""
from __future__ import annotations

import math
import random
import subprocess
from dataclasses import asdict, dataclass, field

import config
from analyze import norm_cdf
from price_feed import OrderBook


# --------------------------------------------------------------------------- #
# Config of all modeling assumptions
# --------------------------------------------------------------------------- #
@dataclass
class BacktestConfig:
    # token price model
    mispricing: float = 0.0          # favorite is this much cheaper than fair (edge)
    spread: float = 0.02             # full bid/ask spread on each token
    slippage: float = 0.005          # extra paid above the ask per fill
    min_price: float = 0.02          # clamp token prices away from 0/1
    max_price: float = 0.98

    # volatility / timing
    sigma_window: int = config.VOL_WINDOW          # candles for realized vol
    decision_lead: int = config.DECISION_LEAD_SECONDS  # seconds before close to decide
    sigma_floor: float = 1e-5        # guard against zero vol

    # orderbook model
    orderbook_mode: str = "noise"    # 'noise' | 'momentum' | 'edge'
    orderbook_noise: float = 0.15    # stdev of imbalance noise
    orderbook_edge: float = 0.0      # 'edge' mode: fraction of outcome leaked [0,1]
    orderbook_momentum_k: float = 80.0

    # costs
    gas: float = config.GAS_COST
    fee: float = config.POLYMARKET_FEE

    # reproducibility
    seed: int = config.RANDOM_SEED

    def snapshot(self) -> dict:
        return asdict(self)


def git_hash() -> str:
    """Short git hash for report reproducibility; 'unknown' if not a repo."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------- #
# Price model
# --------------------------------------------------------------------------- #
def p_up(move: float, sigma: float, tau_min: float, floor: float = 1e-5) -> float:
    """Fair probability UP wins. Φ(move / (σ·√τ)), τ in minutes."""
    s = max(sigma, floor)
    denom = s * math.sqrt(max(tau_min, 1e-9))
    if denom <= 0:
        return 0.5
    return norm_cdf(move / denom)


class Pricer:
    """Turns (move, σ, τ) into modeled UP/DOWN mids and FAV/HEDGE fill prices."""

    def __init__(self, cfg: BacktestConfig):
        self.cfg = cfg

    def _clamp(self, x: float) -> float:
        return max(self.cfg.min_price, min(self.cfg.max_price, x))

    def mids(self, move: float, sigma: float, tau_min: float) -> tuple[float, float]:
        """Modeled market mid prices (mid_up, mid_down), summing to 1, with the
        favorite priced `mispricing` cheaper than fair."""
        fair_up = p_up(move, sigma, tau_min, self.cfg.sigma_floor)
        fav_is_up = fair_up >= 0.5
        fair_fav = fair_up if fav_is_up else (1.0 - fair_up)
        mid_fav = self._clamp(fair_fav - self.cfg.mispricing)
        mid_up = mid_fav if fav_is_up else (1.0 - mid_fav)
        return mid_up, 1.0 - mid_up

    def fills(self, side: str, mid_up: float, mid_down: float) -> tuple[float, float]:
        """FAV fill (the side the strategy chose) and HEDGE fill (the opposite),
        each at ask + slippage. Returns (fav_price, hedge_price)."""
        ask = lambda mid: self._clamp(mid + self.cfg.spread / 2.0 + self.cfg.slippage)
        if side == "UP":
            return ask(mid_up), ask(mid_down)
        return ask(mid_down), ask(mid_up)

    def orderbook(self, rng: random.Random, momentum: float | None,
                  up_wins: bool | None) -> OrderBook:
        """Synthetic top-of-book whose imbalance is set by the configured mode.

        `up_wins` is consulted ONLY in 'edge' mode (a deliberate look-ahead stress
        test); the engine passes None otherwise so no future info can leak.
        """
        mode = self.cfg.orderbook_mode
        if mode == "noise":
            lean = rng.gauss(0.0, self.cfg.orderbook_noise)
        elif mode == "momentum":
            m = momentum or 0.0
            lean = math.tanh(self.cfg.orderbook_momentum_k * m) + rng.gauss(0, self.cfg.orderbook_noise)
        elif mode == "edge":
            if up_wins is None:
                lean = rng.gauss(0.0, self.cfg.orderbook_noise)
            else:
                signal = 1.0 if up_wins else -1.0
                lean = self.cfg.orderbook_edge * signal + rng.gauss(0, self.cfg.orderbook_noise)
        else:
            raise ValueError(f"unknown orderbook_mode {mode!r}")
        lean = max(-0.9, min(0.9, lean))
        base = 1000.0
        bid, ask = base * (1 + lean), base * (1 - lean)
        return OrderBook(
            bids=((0.49, bid), (0.48, bid * 0.6)),
            asks=((0.51, ask), (0.52, ask * 0.6)),
        )
