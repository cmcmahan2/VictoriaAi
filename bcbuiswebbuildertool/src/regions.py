"""
Region registry + resolver for Canada-wide discovery.

Reads regions.json (provinces -> cities, each tagged with a population tier)
and turns a free-text "region" input from the dashboard into a concrete,
ordered list of cities to sweep plus the ISO codes needed for OpenStreetMap
area queries.

Resolution rules for the input string:
  - A country alias ("Canada", "All of Canada", "nationwide") -> every
    province, ordered by priority (British Columbia first), each province's
    cities ordered by tier.
  - A province name/code/alias ("BC", "All of BC", "Alberta", "CA-ON") ->
    just that province.
  - Anything else (e.g. "Victoria") -> None, meaning "treat as a single city".

max_tier filters how deep each province is swept:
  1 = top metros only, 2 = metros + mid-size, 3 = everything (default).
"""

import json
from functools import lru_cache
from pathlib import Path

_REGIONS_PATH = Path(__file__).parent / "regions.json"

_COUNTRY_ALIASES = {
    "canada", "all of canada", "all canada", "ca", "can",
    "nationwide", "national", "country-wide", "country wide",
}


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(_REGIONS_PATH.read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _province_cities(prov: dict, max_tier: int) -> list[str]:
    """City names for a province, tier-filtered and ordered by tier (stable, so
    population order within a tier is preserved from the JSON)."""
    ordered = sorted(prov["cities"], key=lambda c: c["tier"])
    return [c["name"] for c in ordered if c["tier"] <= max_tier]


def _province_aliases(prov: dict) -> set[str]:
    base = {_norm(prov["name"]), _norm(prov["code"])}
    base |= {_norm(a) for a in prov.get("aliases", [])}
    # Accept "all of <X>" / "all <X>" for the name AND every alias, so both
    # "All of British Columbia" and "All of BC" resolve.
    expanded = set(base)
    for a in base:
        expanded.add(f"all of {a}")
        expanded.add(f"all {a}")
    return expanded


def resolve_region(region_input: str, max_tier: int = 3) -> dict | None:
    """Resolve a region input string. Returns a descriptor dict or None if the
    input should be treated as a single city.

    Descriptor shape:
      {
        "kind": "country" | "province",
        "label": "Canada" | "British Columbia",
        "provinces": [{"label": ..., "iso": "CA-BC", "cities": [...]}, ...],
        "cities": [<flattened, in sweep order>],
      }
    """
    data = _data()
    q = _norm(region_input)
    if not q:
        return None

    if q in _COUNTRY_ALIASES:
        provinces = []
        for p in sorted(data["provinces"], key=lambda p: p["priority"]):
            provinces.append({
                "label": p["name"],
                "iso": p["code"],
                "cities": _province_cities(p, max_tier),
            })
        flat = [c for prov in provinces for c in prov["cities"]]
        return {"kind": "country", "label": data["country"],
                "provinces": provinces, "cities": flat}

    for p in data["provinces"]:
        if q in _province_aliases(p):
            cities = _province_cities(p, max_tier)
            return {"kind": "province", "label": p["name"],
                    "provinces": [{"label": p["name"], "iso": p["code"], "cities": cities}],
                    "cities": cities}

    return None


def region_label(region_input: str, max_tier: int = 3) -> str:
    """Friendly description for logs/UI: the region name + city count, or the
    raw city string when it's a single-city search."""
    r = resolve_region(region_input, max_tier)
    if not r:
        return f"{region_input}"
    return f"{r['label']} ({len(r['cities'])} cities)"


def list_regions() -> list[dict]:
    """Lightweight list of selectable regions for the dashboard dropdown:
    Canada first, then every province (priority order)."""
    data = _data()
    out = [{"label": f"All of {data['country']}", "value": "All of Canada",
            "kind": "country"}]
    for p in sorted(data["provinces"], key=lambda p: p["priority"]):
        out.append({"label": f"All of {p['name']}", "value": f"All of {p['name']}",
                    "kind": "province", "code": p["code"],
                    "city_count": len(p["cities"])})
    return out
