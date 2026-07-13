"""Journal lifecycle round-trip and monthly-review tests (spec acceptance)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from quantdesk.journal.models import (
    Journal,
    JournalLeg,
    JournalTrade,
    TradeStatus,
)
from quantdesk.journal.review import monthly_review

JULY = dt.date(2026, 7, 6)


def make_trade(
    symbol: str = "SHOP",
    credit_per_share: float = 0.90,
    override: bool = False,
    why: str | None = None,
    iv: float | None = 0.32,
) -> JournalTrade:
    return JournalTrade(
        symbol=symbol,
        strategy="csp",
        opened_at=JULY,
        legs=[
            JournalLeg(
                action="sell",
                option_type="put",
                strike=95.0,
                expiry=JULY + dt.timedelta(days=37),
                entry_price=credit_per_share,
            )
        ],
        credit_total=credit_per_share * 100.0,
        fees_total=1.50,
        override_used=override,
        override_justification=why,
        iv_at_entry=iv,
    )


class TestLifecycle:
    def test_open_adjust_close_round_trip(self, tmp_path: Path) -> None:
        journal = Journal(tmp_path / "j.db")
        trade_id = journal.open_trade(make_trade())

        journal.adjust(
            trade_id, JULY + dt.timedelta(days=10),
            "rolled down 95 -> 92.5 for extra credit", cash_flow=25.0,
        )
        journal.add_note(trade_id, JULY + dt.timedelta(days=11), "vol crush after CPI")
        closed = journal.close_trade(
            trade_id, JULY + dt.timedelta(days=20), close_cost=45.0,
            exit_reason="take-profit", rv_at_close=0.22,
        )
        # P&L = 90 credit + 25 roll - 45 close - 1.50 fees = 68.50, computed not typed.
        assert closed.realized_pnl == pytest.approx(68.50)
        assert closed.status == TradeStatus.CLOSED
        assert closed.exit_reason == "take-profit"

        # Round-trips through a fresh Journal instance (real persistence).
        again = Journal(tmp_path / "j.db").get(trade_id)
        assert again.realized_pnl == pytest.approx(68.50)
        assert len(again.adjustments) == 1
        assert len(again.notes) == 1
        assert again.iv_at_entry == 0.32
        assert again.rv_at_close == 0.22

    def test_assignment_keeps_credit(self, tmp_path: Path) -> None:
        journal = Journal(tmp_path / "j.db")
        trade_id = journal.open_trade(make_trade())
        closed = journal.assign(trade_id, JULY + dt.timedelta(days=37))
        assert closed.exit_reason == "assigned"
        assert closed.realized_pnl == pytest.approx(90.0 - 1.50)

    def test_override_requires_justification(self, tmp_path: Path) -> None:
        journal = Journal(tmp_path / "j.db")
        with pytest.raises(ValueError, match="justification"):
            journal.open_trade(make_trade(override=True, why=None))

    def test_override_recorded_permanently(self, tmp_path: Path) -> None:
        journal = Journal(tmp_path / "j.db")
        tid = journal.open_trade(
            make_trade(override=True, why="earnings play, I know the rules say no")
        )
        t = Journal(tmp_path / "j.db").get(tid)
        assert t.override_used
        assert t.override_justification is not None

    def test_double_close_rejected(self, tmp_path: Path) -> None:
        journal = Journal(tmp_path / "j.db")
        tid = journal.open_trade(make_trade())
        journal.close_trade(tid, JULY, 10.0, "take-profit")
        with pytest.raises(ValueError, match="not open"):
            journal.close_trade(tid, JULY, 10.0, "take-profit")

    def test_missing_trade_raises(self, tmp_path: Path) -> None:
        with pytest.raises(KeyError):
            Journal(tmp_path / "j.db").get(999)

    def test_list_filters_by_status(self, tmp_path: Path) -> None:
        journal = Journal(tmp_path / "j.db")
        a = journal.open_trade(make_trade("AAA"))
        journal.open_trade(make_trade("BBB"))
        journal.close_trade(a, JULY, 10.0, "take-profit")
        assert [t.symbol for t in journal.list_trades(TradeStatus.OPEN)] == ["BBB"]
        assert len(journal.list_trades()) == 2


class TestMonthlyReview:
    def build_month(self, tmp_path: Path) -> Journal:
        journal = Journal(tmp_path / "j.db")
        # Winner: sold 32% IV, realized 22% — insurance was overpriced.
        w = journal.open_trade(make_trade("WIN", credit_per_share=0.90, iv=0.32))
        journal.close_trade(w, JULY + dt.timedelta(days=14), 30.0,
                            "take-profit", rv_at_close=0.22)
        # Loser + override: sold 25% IV, realized 45% — underpriced insurance.
        lo = journal.open_trade(
            make_trade("LOSE", credit_per_share=1.20, iv=0.25,
                       override=True, why="felt strongly")
        )
        journal.close_trade(lo, JULY + dt.timedelta(days=18), 360.0,
                            "stop-loss", rv_at_close=0.45)
        return journal

    def test_review_numbers(self, tmp_path: Path) -> None:
        r = monthly_review(self.build_month(tmp_path), 2026, 7)
        assert r.n_opened == 2 and r.n_closed == 2
        # WIN: 90 - 30 - 1.5 = 58.5; LOSE: 120 - 360 - 1.5 = -241.5
        assert r.total_pnl == pytest.approx(58.5 - 241.5)
        assert r.win_rate == 0.5
        assert r.rule_adherence_pct == 0.5
        assert len(r.overrides) == 1 and "felt strongly" in r.overrides[0]
        assert r.avg_iv_sold == pytest.approx((0.32 + 0.25) / 2)
        assert r.avg_rv_realized == pytest.approx((0.22 + 0.45) / 2)
        assert r.vrp_captured == pytest.approx(((0.32 - 0.22) + (0.25 - 0.45)) / 2)

    def test_worst_trade_autopsy(self, tmp_path: Path) -> None:
        r = monthly_review(self.build_month(tmp_path), 2026, 7)
        assert r.worst is not None
        assert r.worst.symbol == "LOSE"
        assert "OVERRIDE" in r.worst.autopsy
        assert "UNDERPRICED" in r.worst.autopsy
        assert "Stop respected" in r.worst.autopsy

    def test_empty_month(self, tmp_path: Path) -> None:
        r = monthly_review(Journal(tmp_path / "j.db"), 2026, 1)
        assert r.n_opened == 0 and r.n_closed == 0
        assert r.win_rate is None and r.worst is None
