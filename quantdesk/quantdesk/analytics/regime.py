"""Volatility regime classification: VIX level + term structure.

Drives the risk engine's position-size multiplier (Phase 4):
VIX > 30 halves new-position size; VIX > 40 freezes new trades.
Selling vol into a panic without smaller size is how premium sellers
blow up; this module is the circuit breaker.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class VolRegime(str, Enum):
    LOW = "low"            # VIX < 15  — premium thin; be selective
    NORMAL = "normal"      # 15-20     — business as usual
    ELEVATED = "elevated"  # 20-30     — richer premium, still orderly
    HIGH = "high"          # 30-40     — stress; halve new-position size
    EXTREME = "extreme"    # > 40      — crisis; freeze new trades


class TermStructure(str, Enum):
    CONTANGO = "contango"              # VIX3M > VIX: normal, calm
    BACKWARDATION = "backwardation"    # VIX3M < VIX: near-term panic
    UNKNOWN = "unknown"                # no VIX3M available


class RegimeAssessment(BaseModel):
    """Classification output consumed by risk sizing and the CLI."""

    vix: float
    vix_3m: float | None
    regime: VolRegime
    term_structure: TermStructure
    sizing_multiplier: float
    notes: list[str]


def classify_regime(vix: float, vix_3m: float | None = None) -> RegimeAssessment:
    """Classify the current vol regime from VIX level and term structure.

    Sizing multipliers: 1.0 up to VIX 30, 0.5 for 30-40, 0.0 above 40
    (new-trade freeze). Backwardation adds a warning note but does not
    itself change the multiplier — the level thresholds handle severity.
    """
    if vix <= 0:
        raise ValueError(f"VIX must be positive (got {vix})")

    notes: list[str] = []
    if vix < 15:
        regime, multiplier = VolRegime.LOW, 1.0
        notes.append("Low-vol regime: premium is thin; only take the best setups.")
    elif vix < 20:
        regime, multiplier = VolRegime.NORMAL, 1.0
    elif vix < 30:
        regime, multiplier = VolRegime.ELEVATED, 1.0
        notes.append("Elevated vol: premium rich; stay disciplined on size.")
    elif vix < 40:
        regime, multiplier = VolRegime.HIGH, 0.5
        notes.append("HIGH-vol regime (VIX > 30): new-position size HALVED.")
    else:
        regime, multiplier = VolRegime.EXTREME, 0.0
        notes.append(
            "EXTREME regime (VIX > 40): NEW-TRADE FREEZE. Manage existing "
            "positions only."
        )

    if vix_3m is None:
        term = TermStructure.UNKNOWN
    elif vix_3m >= vix:
        term = TermStructure.CONTANGO
    else:
        term = TermStructure.BACKWARDATION
        notes.append(
            "Term structure in BACKWARDATION: market pricing near-term stress "
            "above long-term — treat rich premium with suspicion."
        )

    return RegimeAssessment(
        vix=vix,
        vix_3m=vix_3m,
        regime=regime,
        term_structure=term,
        sizing_multiplier=multiplier,
        notes=notes,
    )
