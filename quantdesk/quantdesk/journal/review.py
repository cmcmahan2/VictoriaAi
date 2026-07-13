"""The monthly review — the flagship feedback loop.

Four questions, answered from the journal every month:
  1. Did I follow the process? (rule-adherence %, every override listed)
  2. Was the insurance I sold actually overpriced? (avg IV sold vs
     realized vol over the holding period — the trader's 'closing line
     value')
  3. How did results compare to plan? (win rate, premium capture)
  4. What was my worst position and why? (autopsy)
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from quantdesk.journal.models import Journal, JournalTrade, TradeStatus


class WorstTrade(BaseModel):
    trade_id: int | None
    symbol: str
    pnl: float
    exit_reason: str | None
    autopsy: str


class MonthlyReview(BaseModel):
    year: int
    month: int
    n_opened: int
    n_closed: int
    total_pnl: float
    total_fees: float
    win_rate: float | None            # None when nothing closed
    premium_capture: float | None     # net P&L / gross credit on closed trades
    rule_adherence_pct: float | None  # 1 - overrides/opened
    overrides: list[str]
    avg_iv_sold: float | None
    avg_rv_realized: float | None
    vrp_captured: float | None        # avg IV sold - avg RV realized ('CLV')
    worst: WorstTrade | None


def monthly_review(journal: Journal, year: int, month: int) -> MonthlyReview:
    """Build the review for one calendar month from journal records."""
    opened = [
        t
        for t in journal.list_trades()
        if t.opened_at.year == year and t.opened_at.month == month
    ]
    closed = [
        t
        for t in journal.list_trades(TradeStatus.CLOSED)
        if t.closed_at is not None
        and t.closed_at.year == year
        and t.closed_at.month == month
    ]

    pnls = [t.realized_pnl for t in closed if t.realized_pnl is not None]
    total_pnl = sum(pnls)
    wins = [p for p in pnls if p > 0]
    gross_credit = sum(t.credit_total for t in closed)

    overrides = [
        f"#{t.id} {t.symbol}: {t.override_justification}"
        for t in opened
        if t.override_used
    ]

    ivs = [t.iv_at_entry for t in closed if t.iv_at_entry is not None]
    rvs = [t.rv_at_close for t in closed if t.rv_at_close is not None]
    paired = [
        (t.iv_at_entry, t.rv_at_close)
        for t in closed
        if t.iv_at_entry is not None and t.rv_at_close is not None
    ]
    avg_iv = sum(ivs) / len(ivs) if ivs else None
    avg_rv = sum(rvs) / len(rvs) if rvs else None
    vrp_captured = (
        sum(iv - rv for iv, rv in paired) / len(paired) if paired else None
    )

    worst: WorstTrade | None = None
    if closed:
        w = min(
            closed, key=lambda t: t.realized_pnl if t.realized_pnl is not None else 0.0
        )
        worst = WorstTrade(
            trade_id=w.id,
            symbol=w.symbol,
            pnl=w.realized_pnl or 0.0,
            exit_reason=w.exit_reason,
            autopsy=_autopsy(w),
        )

    return MonthlyReview(
        year=year,
        month=month,
        n_opened=len(opened),
        n_closed=len(closed),
        total_pnl=total_pnl,
        total_fees=sum(t.fees_total for t in closed),
        win_rate=len(wins) / len(pnls) if pnls else None,
        premium_capture=(total_pnl / gross_credit) if gross_credit > 0 else None,
        rule_adherence_pct=(
            1.0 - len(overrides) / len(opened) if opened else None
        ),
        overrides=overrides,
        avg_iv_sold=avg_iv,
        avg_rv_realized=avg_rv,
        vrp_captured=vrp_captured,
        worst=worst,
    )


def _autopsy(t: JournalTrade) -> str:
    """A blunt paragraph about the worst position of the month."""
    parts: list[str] = []
    if t.realized_pnl is not None and t.realized_pnl < 0:
        parts.append(
            f"Lost {abs(t.realized_pnl):,.2f} on {t.symbol} ({t.strategy}), "
            f"exit: {t.exit_reason or 'unrecorded'}."
        )
    else:
        parts.append(
            f"Worst position still made {t.realized_pnl or 0:,.2f} — a good month."
        )
    if t.override_used:
        parts.append(
            f"THIS TRADE WAS AN OVERRIDE ({t.override_justification}). "
            "Rule-breaking trades that lose money should hurt twice."
        )
    if t.iv_at_entry is not None and t.rv_at_close is not None:
        edge = t.iv_at_entry - t.rv_at_close
        if edge < 0:
            parts.append(
                f"Sold {t.iv_at_entry:.0%} IV, realized {t.rv_at_close:.0%} — "
                "the insurance was UNDERPRICED. Bad entry, not bad luck."
            )
        else:
            parts.append(
                f"Sold {t.iv_at_entry:.0%} IV vs {t.rv_at_close:.0%} realized — "
                "edge was there; the loss was within-plan variance."
            )
    if t.exit_reason == "stop-loss":
        parts.append("Stop respected — that is the process working, not failing.")
    return " ".join(parts)
