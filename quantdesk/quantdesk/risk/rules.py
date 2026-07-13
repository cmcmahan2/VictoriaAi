"""Hard rule engine — the gate every proposal passes before the journal.

Rules produce BLOCK or WARN checks. Any BLOCK stops a proposal from
being logged; the CLI requires ``--override`` plus a justification
string, and the journal permanently records the override (Phase 5).
The point is to make freelancing loud, logged, and rare.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from pydantic import BaseModel

from quantdesk.analytics.regime import classify_regime
from quantdesk.config import QuantDeskConfig
from quantdesk.risk.portfolio import Position, avg_abs_correlation_to_book


class Severity(str, Enum):
    BLOCK = "block"
    WARN = "warn"


class RuleCheck(BaseModel):
    rule: str
    passed: bool
    severity: Severity
    detail: str


class RuleVerdict(BaseModel):
    checks: list[RuleCheck]

    @property
    def blocked(self) -> bool:
        return any(c.severity == Severity.BLOCK and not c.passed for c in self.checks)

    @property
    def failures(self) -> list[RuleCheck]:
        return [c for c in self.checks if not c.passed]


def check_proposal(
    *,
    symbol: str,
    sector: str,
    collateral_usd: float,
    account_usd: float,
    book: Sequence[Position],
    vix: float,
    config: QuantDeskConfig,
    close_map: dict[str, Sequence[float]] | None = None,
) -> RuleVerdict:
    """Run every rule against a candidate position. Never short-circuits.

    ``close_map`` (symbol -> daily closes) powers the correlation rule;
    omit it and the rule reports itself unevaluated (WARN, passed) so
    the absence of data is visible rather than silent.
    """
    checks: list[RuleCheck] = []
    risk = config.risk

    # 1. Per-position collateral cap — BLOCK.
    cap = risk.max_position_pct * account_usd
    checks.append(
        RuleCheck(
            rule="position-size-cap",
            passed=collateral_usd <= cap,
            severity=Severity.BLOCK,
            detail=f"collateral ${collateral_usd:,.0f} vs cap ${cap:,.0f} "
            f"({risk.max_position_pct:.0%} of ${account_usd:,.0f})",
        )
    )

    # 2. Total deployment cap — BLOCK.
    deployed = sum(p.collateral for p in book)
    dep_cap = risk.max_deployed_pct * account_usd
    checks.append(
        RuleCheck(
            rule="deployment-cap",
            passed=deployed + collateral_usd <= dep_cap,
            severity=Severity.BLOCK,
            detail=f"deployed ${deployed:,.0f} + new ${collateral_usd:,.0f} vs "
            f"cap ${dep_cap:,.0f} ({risk.max_deployed_pct:.0%})",
        )
    )

    # 3. Sector concentration — BLOCK.
    in_sector = sum(1 for p in book if p.sector == sector)
    checks.append(
        RuleCheck(
            rule="sector-concentration",
            passed=in_sector < risk.max_positions_per_sector,
            severity=Severity.BLOCK,
            detail=f"{in_sector} existing {sector!r} positions vs max "
            f"{risk.max_positions_per_sector}",
        )
    )

    # 4. Correlation to book — WARN (spec: a warning, not a hard block).
    if close_map is None:
        checks.append(
            RuleCheck(
                rule="correlation",
                passed=True,
                severity=Severity.WARN,
                detail="not evaluated — no price history supplied",
            )
        )
    else:
        avg = avg_abs_correlation_to_book(
            symbol, [p.symbol for p in book], close_map
        )
        if avg is None:
            checks.append(
                RuleCheck(
                    rule="correlation",
                    passed=True,
                    severity=Severity.WARN,
                    detail="book empty — nothing to correlate against",
                )
            )
        else:
            checks.append(
                RuleCheck(
                    rule="correlation",
                    passed=avg <= risk.correlation_warning,
                    severity=Severity.WARN,
                    detail=f"avg |rho| to book {avg:.2f} vs "
                    f"{risk.correlation_warning:.2f} threshold",
                )
            )

    # 5. VIX regime — BLOCK on freeze, WARN when size is halved.
    regime = classify_regime(vix)
    if regime.sizing_multiplier == 0.0:
        checks.append(
            RuleCheck(
                rule="vix-regime",
                passed=False,
                severity=Severity.BLOCK,
                detail=f"VIX {vix:.1f}: NEW-TRADE FREEZE "
                f"({regime.regime.value} regime)",
            )
        )
    elif regime.sizing_multiplier < 1.0:
        checks.append(
            RuleCheck(
                rule="vix-regime",
                passed=True,
                severity=Severity.WARN,
                detail=f"VIX {vix:.1f}: size halved ({regime.regime.value} regime)",
            )
        )
    else:
        checks.append(
            RuleCheck(
                rule="vix-regime",
                passed=True,
                severity=Severity.WARN,
                detail=f"VIX {vix:.1f}: normal sizing",
            )
        )

    return RuleVerdict(checks=checks)
