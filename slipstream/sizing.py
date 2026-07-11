"""Stake sizing: fractional Kelly with a correlation rule.

- stake = kelly_fraction × ((odds−1)·p − (1−p)) / (odds−1) × bankroll
- Rows sharing player + match are ONE position: the position stake is the mean
  of the legs' individual Kelly stakes × 1.25 (imperfect correlation), split
  evenly across the legs.
- Rows under the EV floor get stake 0 and a flag (still shown, never dropped).
"""


def kelly_stake(win_prob_pct: float, odds: float, bankroll: float, kelly_fraction: float) -> float:
    if not odds or odds <= 1 or not win_prob_pct:
        return 0.0
    p = win_prob_pct / 100.0
    b = odds - 1.0
    edge = b * p - (1 - p)
    if edge <= 0:
        return 0.0
    return kelly_fraction * (edge / b) * bankroll


def suggest_stakes(rows: list[dict], cfg: dict) -> list[dict]:
    """Mutates each row in place: adds stake, correlation_group, flags."""
    bankroll = float(cfg.get("current_bankroll", 0) or 0)
    kf = float(cfg.get("kelly_fraction", 0.25) or 0.25)
    ev_floor = float(cfg.get("min_ev_floor_pct", 0) or 0)

    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (
            (row.get("player") or "").strip().lower(),
            (row.get("match") or "").strip().lower(),
        )
        groups.setdefault(key, []).append(row)

    for (player, match), legs in groups.items():
        correlated = len(legs) > 1 and player and match
        raw = [
            kelly_stake(leg.get("win_prob") or 0, leg.get("odds_decimal") or 0, bankroll, kf)
            for leg in legs
        ]
        if correlated:
            position = (sum(raw) / len(raw)) * 1.25
            per_leg = position / len(legs)
        for leg, k in zip(legs, raw):
            below_floor = (leg.get("ev_pct") is None) or (float(leg["ev_pct"]) < ev_floor)
            stake = per_leg if correlated else k
            leg["stake"] = 0.0 if below_floor else round(stake, 2)
            leg["below_ev_floor"] = below_floor
            leg["correlation_group"] = f"{player} @ {match}" if correlated else None
    return rows


def exposure_check(new_stakes_total: float, open_exposure: float, cfg: dict) -> dict:
    bankroll = float(cfg.get("current_bankroll", 0) or 0)
    cap_pct = float(cfg.get("max_open_exposure_pct", 100) or 100)
    cap = bankroll * cap_pct / 100.0
    projected = open_exposure + new_stakes_total
    return {
        "open_exposure": round(open_exposure, 2),
        "new_stakes": round(new_stakes_total, 2),
        "projected": round(projected, 2),
        "cap": round(cap, 2),
        "cap_pct": cap_pct,
        "over_cap": projected > cap and cap > 0,
    }
