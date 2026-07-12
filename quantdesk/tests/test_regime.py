"""Tests for the VIX regime classifier and sizing multipliers."""

from __future__ import annotations

import pytest

from quantdesk.analytics.regime import TermStructure, VolRegime, classify_regime


class TestLevels:
    @pytest.mark.parametrize(
        "vix,regime,multiplier",
        [
            (12.0, VolRegime.LOW, 1.0),
            (14.99, VolRegime.LOW, 1.0),
            (15.0, VolRegime.NORMAL, 1.0),
            (19.99, VolRegime.NORMAL, 1.0),
            (20.0, VolRegime.ELEVATED, 1.0),
            (29.99, VolRegime.ELEVATED, 1.0),
            (30.0, VolRegime.HIGH, 0.5),     # VIX > 30 -> halve size
            (39.99, VolRegime.HIGH, 0.5),
            (40.0, VolRegime.EXTREME, 0.0),  # VIX > 40 -> freeze
            (85.0, VolRegime.EXTREME, 0.0),  # March-2020 style print
        ],
    )
    def test_thresholds(
        self, vix: float, regime: VolRegime, multiplier: float
    ) -> None:
        a = classify_regime(vix)
        assert a.regime == regime
        assert a.sizing_multiplier == multiplier

    def test_freeze_note_present(self) -> None:
        a = classify_regime(45.0)
        assert any("FREEZE" in n for n in a.notes)

    def test_invalid_vix_raises(self) -> None:
        with pytest.raises(ValueError):
            classify_regime(0.0)


class TestTermStructure:
    def test_contango(self) -> None:
        a = classify_regime(16.0, vix_3m=18.0)
        assert a.term_structure == TermStructure.CONTANGO

    def test_backwardation_warns(self) -> None:
        a = classify_regime(28.0, vix_3m=24.0)
        assert a.term_structure == TermStructure.BACKWARDATION
        assert any("BACKWARDATION" in n for n in a.notes)

    def test_unknown_without_vix3m(self) -> None:
        assert classify_regime(18.0).term_structure == TermStructure.UNKNOWN
