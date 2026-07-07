import datetime as dt

import pytest

from polyfunnel.costs import CostModel


@pytest.fixture()
def model() -> CostModel:
    return CostModel.load()


def test_fee_symmetric_around_half(model: CostModel):
    assert model.taker_fee("crypto", 100, 0.30) == pytest.approx(
        model.taker_fee("crypto", 100, 0.70)
    )


def test_fee_max_at_half_matches_documented_table(model: CostModel):
    # docs: sports $0.75 / politics $1.00 / economics $1.25 per 100 shares at p=0.5
    assert model.taker_fee("sports", 100, 0.5) == pytest.approx(0.75)
    assert model.taker_fee("politics", 100, 0.5) == pytest.approx(1.00)
    assert model.taker_fee("economics", 100, 0.5) == pytest.approx(1.25)
    # crypto: sources disagree $1.75 (rate .07) vs $1.80 (rate .072); yaml holds .07
    assert model.taker_fee("crypto", 100, 0.5) == pytest.approx(1.75)


def test_geopolitics_fee_free(model: CostModel):
    assert model.taker_fee("geopolitics", 100, 0.5) == 0.0


def test_unknown_category_falls_back_to_other(model: CostModel):
    assert model.taker_fee("space-lasers", 100, 0.5) == model.taker_fee("other", 100, 0.5)


def test_price_bounds_rejected(model: CostModel):
    with pytest.raises(ValueError):
        model.taker_fee("crypto", 100, 0.0)
    with pytest.raises(ValueError):
        model.taker_fee("crypto", 100, 1.0)


def test_staleness_gate_blocks_unverified(model: CostModel):
    # fresh checkout: last_verified_live is null -> trusted runs must be blocked
    assert model.staleness_ok(dt.date(2026, 7, 6)) is False
