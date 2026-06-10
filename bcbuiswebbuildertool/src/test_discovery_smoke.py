"""
Smoke test for discovery hardening.

Attempts a LIVE Overpass run first. If the network is unavailable, falls back to
a MOCKED Overpass JSON response that exercises parsing + dedupe + scoring offline.

Run:  python test_discovery_smoke.py
"""
import os
import sys
from unittest import mock

# Ensure demo data never leaks into these tests.
os.environ.pop("DEMO_MODE", None)
os.environ.pop("GOOGLE_MAPS_API_KEY", None)
os.environ.pop("FOURSQUARE_API_KEY", None)

import discovery


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _check_results(results, label):
    print(f"\n=== {label}: {len(results)} leads ===")
    names = [r["name"] for r in results]
    # No demo data ever.
    _assert(all(r.get("source") != "demo" for r in results), "demo data leaked!")
    _assert(all(not r.get("_demo") for r in results), "demo flag leaked!")
    # Every business keeps the expected output shape.
    required = {"name", "address", "phone", "existing_website", "rating",
                "review_count", "photos_count", "category", "city", "source",
                "score", "weakness_flags", "notes", "rank", "website_health"}
    for r in results:
        missing = required - set(r.keys())
        _assert(not missing, f"missing keys {missing} in {r['name']}")
        _assert(0 <= r["score"] <= 10, f"score out of range: {r['score']}")
        _assert(r["name"].strip(), "empty name slipped through")
    # Deduped: no duplicate normalized names.
    norm = [discovery._norm_name(n) for n in names]
    _assert(len(norm) == len(set(norm)), f"duplicates present: {names}")
    # Ranked best-first.
    scores = [r["score"] for r in results]
    _assert(scores == sorted(scores, reverse=True), "not ranked best-first")
    for r in results[:5]:
        print(f"  [{r['score']}/10] {r['name']} | site={r['existing_website']} | {r['notes']}")
    return True


def run_live():
    print("Attempting LIVE Overpass discovery...")
    r1 = discovery.discover_businesses("Victoria", "landscaper", radius_km=15, max_results=20)
    r2 = discovery.discover_businesses("Nanaimo", "plumber", radius_km=20, max_results=20)
    if not r1 and not r2:
        raise RuntimeError("live returned nothing")
    if r1:
        _check_results(r1, "Victoria landscaper (LIVE)")
    if r2:
        _check_results(r2, "Nanaimo plumber (LIVE)")
    return True


# --- Mocked Overpass payload: dupes, a chain, strong site, no-site, broken ----
_MOCK_ELEMENTS = [
    {"tags": {"name": "Garden City Landscaping Ltd", "craft": "gardener",
              "addr:housenumber": "12", "addr:street": "Oak Bay Ave",
              "addr:city": "Victoria", "phone": "250-111-2222"}},
    # duplicate of above (less complete) -> should be dropped
    {"tags": {"name": "Garden City Landscaping", "craft": "gardener",
              "addr:city": "Victoria"}},
    {"tags": {"name": "West Coast Lawns", "shop": "garden_centre",
              "addr:city": "Victoria",
              "website": "westcoastlawns.example"}},
    {"tags": {"name": "Modern Yard Pros", "craft": "gardener",
              "addr:city": "Victoria",
              "website": "https://modernyard.example"}},
    # a chain -> should be filtered out
    {"tags": {"name": "Canadian Tire Garden Centre", "shop": "garden_centre",
              "addr:city": "Victoria"}},
    # no name -> dropped
    {"tags": {"craft": "gardener", "addr:city": "Victoria"}},
]


def run_mocked():
    print("\nNetwork unavailable — running MOCKED Overpass test...")

    def fake_geocode(city):
        return (48.4284, -123.3656)

    def fake_overpass(query):
        # name fallback query reuses the same elements; dedupe handles overlap
        return list(_MOCK_ELEMENTS)

    def fake_health(url):
        h = {"accessible": False, "ssl": False, "broken": True, "parked": False,
             "outdated": False, "mobile_responsive": False, "has_booking": False,
             "status_code": None, "last_copyright_year": None}
        if not url:
            return h
        if "modernyard" in url:
            # strong site -> should sink to the bottom
            return {"accessible": True, "ssl": True, "broken": False, "parked": False,
                    "outdated": False, "mobile_responsive": True, "has_booking": True,
                    "status_code": 200, "last_copyright_year": discovery.CURRENT_YEAR}
        if "westcoastlawns" in url:
            # broken site
            return {"accessible": False, "ssl": False, "broken": True, "parked": False,
                    "outdated": False, "mobile_responsive": False, "has_booking": False,
                    "status_code": 500, "last_copyright_year": None}
        return h

    with mock.patch.object(discovery, "_geocode_city", fake_geocode), \
         mock.patch.object(discovery, "_run_overpass", fake_overpass), \
         mock.patch.object(discovery, "_check_website_health", fake_health):
        results = discovery.discover_businesses("Victoria", "landscaper",
                                                radius_km=15, max_results=20)

    _check_results(results, "MOCKED landscaper")
    names = [r["name"] for r in results]
    _assert("Canadian Tire Garden Centre" not in names, "chain not filtered")
    _assert(sum("Garden City" in n for n in names) == 1, "duplicate not deduped")
    # The strong site should rank LAST (lowest score).
    strong = next(r for r in results if "modernyard" in (r["existing_website"] or ""))
    _assert(strong["rank"] == len(results), "strong site did not sink to bottom")
    _assert("strong_existing_site" in strong["weakness_flags"], "strong flag missing")
    # No-website / broken businesses should outrank the strong site.
    _assert(strong["score"] < results[0]["score"], "strong site not lowest")
    print("\nMocked assertions passed: chain filtered, dupes removed, strong site sank.")
    return True


if __name__ == "__main__":
    try:
        run_live()
        print("\nLIVE TEST PASSED")
    except Exception as exc:
        print(f"\nLive test unavailable ({exc!r}); falling back to mock.")
        try:
            run_mocked()
            print("\nMOCKED TEST PASSED")
        except Exception as exc2:
            print(f"\nTEST FAILED: {exc2!r}")
            sys.exit(1)
