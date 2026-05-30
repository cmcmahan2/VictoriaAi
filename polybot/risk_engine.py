"""
risk_engine.py — position sizing and bankroll management.

Responsibilities (all reused unchanged by the backtester):
  * fractional-Kelly sizing of the FAV leg from an estimated win prob + token odds
  * a smaller opposite-side HEDGE leg
  * Bayesian (Beta) tracking of the realized FAV win rate
  * drawdown-aware de-risking and a hard halt

Kelly for a binary token bought at price q (pays $1 on win):
    stake S buys S/q shares; win profit = S*(1-q)/q, loss = S
    => net odds b = (1-q)/q,  full-Kelly fraction f* = p - (1-p)/b = (p*b-(1-p))/b
We deploy KELLY_FRACTION * f* of bankroll, capped, then de-risked by drawdown.

The win-prob estimate p blends the live signal confidence with the empirical
Beta posterior (SIGNAL_TRUST controls the mix), so early on we lean on the prior
and only trust the signal more as evidence (or its own strength) accumulates.
"""
from __future__ import annotations

from dataclasses import dataclass

import config
from strategy import Signal


@dataclass
class SizeDecision:
    fav_stake: float          # $ on the favored side
    hedge_stake: float        # $ on the opposite side
    win_prob: float           # p used for Kelly
    kelly_full: float         # full-Kelly fraction f*
    kelly_used: float         # fraction of bankroll actually deployed (FAV)
    drawdown: float           # current drawdown at decision time
    halted: bool              # True => sizing refused (drawdown halt / no edge)
    reason: str = ""


class RiskEngine:
    def __init__(self, cfg=config):
        self.cfg = cfg
        self.bankroll = float(cfg.STARTING_BANKROLL)
        self.peak = self.bankroll
        self.alpha = float(cfg.PRIOR_WINS)    # Beta posterior: wins + prior
        self.beta = float(cfg.PRIOR_LOSSES)   # Beta posterior: losses + prior
        self.trades = 0

    # -- state -------------------------------------------------------------- #
    def empirical_winrate(self) -> float:
        """Posterior mean of the FAV win rate."""
        return self.alpha / (self.alpha + self.beta)

    def drawdown(self) -> float:
        if self.peak <= 0:
            return 0.0
        return max(0.0, (self.peak - self.bankroll) / self.peak)

    def update(self, fav_won: bool, pnl: float) -> None:
        """Record a settled trade: move bankroll, peak, and the Beta posterior."""
        self.bankroll += pnl
        self.peak = max(self.peak, self.bankroll)
        if fav_won:
            self.alpha += 1.0
        else:
            self.beta += 1.0
        self.trades += 1

    # -- sizing ------------------------------------------------------------- #
    def _win_prob_estimate(self, signal: Signal) -> float:
        """Blend signal strength with the empirical Beta win rate."""
        # Map signal confidence [0,1] to an implied win prob in (0.5, MAX].
        span = self.cfg.MAX_SIGNAL_WINPROB - 0.5
        signal_p = 0.5 + span * signal.confidence
        emp = self.empirical_winrate()
        t = self.cfg.SIGNAL_TRUST
        p = t * signal_p + (1.0 - t) * emp
        return min(self.cfg.MAX_SIGNAL_WINPROB, max(0.5, p))

    def _drawdown_scale(self, dd: float) -> float:
        """1.0 above the de-risk threshold, linearly to 0 at the halt threshold."""
        lo, hi = self.cfg.DERISK_DRAWDOWN, self.cfg.MAX_DRAWDOWN
        if dd <= lo:
            return 1.0
        if dd >= hi:
            return 0.0
        return 1.0 - (dd - lo) / (hi - lo)

    def size(self, signal: Signal, fav_price: float, hedge_price: float) -> SizeDecision:
        """Return FAV + HEDGE stakes for this signal at the given token prices."""
        dd = self.drawdown()

        if dd >= self.cfg.MAX_DRAWDOWN:
            return SizeDecision(0, 0, 0.5, 0, 0, dd, True, "drawdown_halt")
        if not (0.0 < fav_price < 1.0):
            return SizeDecision(0, 0, 0.5, 0, 0, dd, True, "bad_fav_price")

        p = self._win_prob_estimate(signal)
        b = (1.0 - fav_price) / fav_price            # net odds from token price
        f_full = (p * b - (1.0 - p)) / b if b > 0 else 0.0

        if f_full <= 0:
            return SizeDecision(0, 0, p, f_full, 0, dd, True, "no_kelly_edge")

        frac = self.cfg.KELLY_FRACTION * f_full
        frac = min(frac, self.cfg.MAX_POSITION_FRAC)
        frac *= self._drawdown_scale(dd)

        fav_stake = round(self.bankroll * frac, 2)
        if fav_stake < self.cfg.MIN_STAKE:
            return SizeDecision(0, 0, p, f_full, frac, dd, True, "below_min_stake")

        hedge_stake = round(fav_stake * self.cfg.HEDGE_FRACTION, 2)
        return SizeDecision(
            fav_stake=fav_stake,
            hedge_stake=hedge_stake,
            win_prob=p,
            kelly_full=f_full,
            kelly_used=frac,
            drawdown=dd,
            halted=False,
            reason="ok",
        )
