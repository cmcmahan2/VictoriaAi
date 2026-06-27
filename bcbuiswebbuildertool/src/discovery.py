"""
Phase 1 - Business Discovery

Find BC businesses that have weak, outdated, or no web presence and are strong
candidates for a new website. Uses a tiered discovery strategy:

  Tier 1: Google Maps Places API     (requires GOOGLE_MAPS_API_KEY)
  Tier 2: OpenStreetMap Overpass API (free, no key needed, real businesses)
  Tier 3: Foursquare Places API      (requires FOURSQUARE_API_KEY)
  Tier 4: Demo mode                  (DEMO_MODE=true - realistic fake data for UI testing)

Each discovered business is scored 1-10 on web presence weakness. Higher = better lead.
Results are written to ./output/leads.json, ranked highest score first.
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv

import cache
import regions
from logging_config import get_logger

load_dotenv()

log = get_logger("discovery")

# Scoring weights
SCORE_NO_WEBSITE      = 4
SCORE_BROKEN_WEBSITE  = 3
SCORE_OUTDATED        = 2
SCORE_NO_SSL          = 1
SCORE_NOT_MOBILE      = 1
SCORE_NO_PHOTOS       = 1
SCORE_FEW_REVIEWS     = 1
SCORE_NO_BOOKING      = 1
SCORE_NO_REVIEWS      = 1   # zero reviews at all = effectively invisible online
SCORE_STALE_REVIEWS   = 1   # newest review older than the staleness window
SCORE_INDUSTRY_HIGH   = 2   # high-LTV trades/professional services (can pay more)
SCORE_INDUSTRY_MED    = 1   # mid-LTV services

# A review is "stale" once the newest one is older than this many days.
STALE_REVIEW_DAYS = int(os.getenv("STALE_REVIEW_DAYS", "180"))

# Only run the expensive website-health HTTP check on leads whose cheap,
# metadata-only prescore is at least this high. Set to 0 to check every lead
# that has a URL (the old behaviour).
PRESCORE_HTTP_THRESHOLD = int(os.getenv("PRESCORE_HTTP_THRESHOLD", "3"))

CURRENT_YEAR = datetime.now().year

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
}

_PARKED_SIGNALS  = [
    "domain for sale", "buy this domain", "this domain is parked",
    "domain parking", "godaddy.com/domains", "namecheap.com",
    "sedo.com", "hugedomains.com", "dan.com",
]
_BOOKING_SIGNALS = [
    "book now", "book online", "book an appointment", "schedule",
    "appointment", "calendly", "acuity", "booker", "mindbody",
    "request a quote", "get a quote", "free estimate",
]


def is_province_wide(city: str) -> bool:
    """True when the input names a whole region (a province or all of Canada)
    rather than a single city. Backed by the region registry (regions.json)."""
    return regions.resolve_region(city) is not None


ANY_BUSINESS_TERMS = {"", "any", "all", "any business", "anything", "everything", "*"}


def discover_businesses(
    city: str,
    business_type: str,
    radius_km: int = 15,
    max_results: int = 50,
    max_tier: int = 3,
) -> list[dict]:
    """
    Run the full Phase 1 discovery pipeline for a city/region + business type.
    Tries each tier in order, scoring and ranking all results.

    Region mode: pass `city` as a province ("British Columbia", "All of BC",
    "Alberta", "CA-ON") or the whole country ("All of Canada") to sweep many
    cities at once. The region registry (regions.json) resolves it to an ordered
    city list (BC first), and `max_tier` controls how deep each province is
    swept (1 = top metros, 2 = + mid-size, 3 = everything). Google sweeps the
    cities; OpenStreetMap runs one area query per province in the region.
    """
    google_key = os.getenv("GOOGLE_MAPS_API_KEY")
    fsq_key    = os.getenv("FOURSQUARE_API_KEY")
    demo_mode  = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
    region     = regions.resolve_region(city, max_tier=max_tier)

    businesses: list[dict] = []

    # "any business" search: Google text-search needs a specific type, so skip
    # Tier 1 and let the broad OpenStreetMap search (below) handle it.
    if google_key and business_type.strip().lower() not in ANY_BUSINESS_TERMS:
        if region:
            cities = region["cities"]
            log.info(f"[discovery] Tier 1 - Google Places API: {business_type} across {region['label']} ({len(cities)} cities, tier<= {max_tier})")
            try:
                businesses = _sweep_cities_via_places_api(cities, business_type, max_results, google_key)
                log.info(f"[discovery] Google Places ({region['label']}): {len(businesses)} results")
            except Exception as exc:
                log.warning(f"[discovery] Google Places failed ({exc}) - trying next tier")
        else:
            log.info(f"[discovery] Tier 1 - Google Places API: {business_type} in {city}, BC")
            try:
                businesses = _discover_via_places_api(city, business_type, radius_km, max_results, google_key)
                log.info(f"[discovery] Google Places: {len(businesses)} results")
            except Exception as exc:
                log.warning(f"[discovery] Google Places failed ({exc}) - trying next tier")

    if not businesses:
        if region:
            log.info(f"[discovery] Tier 2 - OpenStreetMap: {business_type} across {region['label']} ({len(region['provinces'])} province area(s))")
            try:
                businesses = _sweep_region_via_openstreetmap(region, business_type, max_results)
                log.info(f"[discovery] OpenStreetMap ({region['label']}): {len(businesses)} real businesses found")
            except Exception as exc:
                log.warning(f"[discovery] OpenStreetMap failed ({exc}) - trying next tier")
        else:
            log.info(f"[discovery] Tier 2 - OpenStreetMap: {business_type} in {city}, BC")
            try:
                businesses = _discover_via_openstreetmap(city, business_type, radius_km, max_results)
                log.info(f"[discovery] OpenStreetMap: {len(businesses)} real businesses found")
            except Exception as exc:
                log.warning(f"[discovery] OpenStreetMap failed ({exc}) - trying next tier")

    if not businesses and fsq_key:
        log.info(f"[discovery] Tier 3 - Foursquare Places API: {business_type} in {city}, BC")
        try:
            businesses = _discover_via_foursquare(city, business_type, radius_km, max_results, fsq_key)
            log.info(f"[discovery] Foursquare: {len(businesses)} results")
        except Exception as exc:
            log.warning(f"[discovery] Foursquare failed ({exc}) - no more tiers")

    if not businesses:
        if demo_mode:
            log.info(f"[discovery] Demo mode - generating sample leads for {business_type} in {city}, BC")
            businesses = _demo_businesses(city, business_type)
        else:
            log.info(
                f"[discovery] No real results for '{business_type}' in {city}, BC — "
                f"try a broader business type or a larger radius (current: {radius_km}km). "
                f"Returning empty (demo data is disabled; set DEMO_MODE=true to enable it)."
            )
            return []

    # Dedupe + drop chains/franchises for every real source (demo data is already
    # curated, so leave it untouched). This guarantees no junk/duplicate leads.
    if not (demo_mode and businesses and businesses[0].get("_demo")):
        before = len(businesses)
        businesses = _dedupe_businesses(businesses)
        if before != len(businesses):
            log.info(f"[discovery] Deduped/filtered {before} -> {len(businesses)} businesses")

    if not businesses:
        log.info(
            f"[discovery] All candidates for '{business_type}' in {city}, BC were "
            f"duplicates or chains — try a broader business type or a larger radius."
        )
        return []

    businesses = _enrich(businesses)

    # Score-first, check-second: compute a cheap metadata-only prescore, then
    # spend the expensive (8s) website-health HTTP check only on leads that have
    # a URL AND already look promising. Leads with no website are top leads that
    # need no check; established-looking businesses fall below the threshold and
    # are left unchecked (ranked on metadata alone). Tune via PRESCORE_HTTP_THRESHOLD.
    for b in businesses:
        b["_prescore"] = _prescore_business(b)
    to_check = [b for b in businesses
                if b.get("existing_website") and b["_prescore"] >= PRESCORE_HTTP_THRESHOLD
                and b.get("website_health") is None]
    skipped = len(businesses) - len(to_check)
    log.info(f"[discovery] Pre-scored {len(businesses)} leads - {len(to_check)} qualify for website check, "
          f"{skipped} skipped (no URL or below threshold {PRESCORE_HTTP_THRESHOLD})")
    if to_check:
        _check_all_websites(to_check)  # mutates each dict in place with website_health

    scored = [_score_business(b) for b in businesses]
    ranked = sorted(scored, key=lambda b: b["score"], reverse=True)
    for i, b in enumerate(ranked, start=1):
        b["rank"] = i

    top = ranked[:max_results]
    if top:
        log.info(f"[discovery] Done - {len(top)} leads ranked. Top score: {top[0]['score']}/10 ({top[0]['name']})")
    return top


def _discover_via_places_api(city, business_type, radius_km, max_results, api_key):
    """Cached Tier 1 wrapper. Serves from the SQLite cache when a previous run
    for the same city/type/radius requested at least as many results (so we know
    we already pulled everything available up to that count). The province sweep
    benefits automatically since it calls this per city."""
    key = f"{city.strip().lower()}|{business_type.strip().lower()}|{radius_km}"
    cached = cache.get("places", key)
    if cached and cached.get("requested", 0) >= max_results:
        results = cached.get("results", [])
        log.info(f"[discovery] Google Places: cache hit for {business_type} in {city} ({len(results)} cached)")
        return results[:max_results]
    results = _discover_via_places_api_live(city, business_type, radius_km, max_results, api_key)
    if results:
        cache.set("places", key, {"requested": max_results, "results": results})
    return results


def _discover_via_places_api_live(city, business_type, radius_km, max_results, api_key):
    """Tier 1: Google Places API (New) Text Search.

    Migrated from the legacy Places API (disabled on this account) to the v1
    places:searchText endpoint, which returns the place fields directly (no
    separate Place Details round-trip). Output shape is unchanged for the rest
    of the pipeline; `places.reviews` rides along for the recency signal.
    """
    # city carries its own province via the registry sweep, so anchor to Canada.
    query = f"{business_type} in {city}, Canada"
    url   = "https://places.googleapis.com/v1/places:searchText"
    field_mask = ",".join([
        "places.id", "places.displayName", "places.formattedAddress",
        "places.nationalPhoneNumber", "places.internationalPhoneNumber",
        "places.websiteUri", "places.rating", "places.userRatingCount",
        "places.photos", "places.reviews", "places.businessStatus",
        "nextPageToken",
    ])
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }

    def _review_unix(rv):
        pt = rv.get("publishTime")
        if not pt:
            return None
        try:
            from datetime import datetime
            return datetime.fromisoformat(pt.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None

    businesses = []
    page_token = None
    while len(businesses) < max_results:
        body = {"textQuery": query, "pageSize": min(20, max_results - len(businesses))}
        if page_token:
            body["pageToken"] = page_token
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        if resp.status_code != 200:
            try:
                err = resp.json().get("error", {}).get("message", resp.text[:200])
            except Exception:
                err = resp.text[:200]
            raise RuntimeError(f"Places API (New): HTTP {resp.status_code} - {err}")
        data = resp.json()
        for p in data.get("places", []):
            phone = p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber") or ""
            revs  = [{"time": _review_unix(rv)} for rv in (p.get("reviews") or [])]
            businesses.append({
                "name":             (p.get("displayName") or {}).get("text", ""),
                "address":          p.get("formattedAddress", ""),
                "phone":            phone,
                "existing_website": p.get("websiteUri"),
                "rating":           p.get("rating"),
                "review_count":     p.get("userRatingCount", 0),
                "photos_count":     len(p.get("photos", []) or []),
                "latest_review_age_days": _latest_review_age_days(revs),
                "place_id":         p.get("id", ""),
                "category":         business_type,
                "city":             city,
                "source":           "google_places",
            })
            if len(businesses) >= max_results:
                break
        page_token = data.get("nextPageToken")
        if not page_token or len(businesses) >= max_results:
            break
        time.sleep(2)  # next-page token needs a moment to become valid

    log.info(f"[discovery] Google Places (New): {len(businesses)} businesses in {city}")
    return businesses



def _sweep_cities_via_places_api(cities, business_type, max_results, api_key):
    """Region Tier 1: sweep an ordered list of cities with Google Places, city by
    city, deduping as we go until max_results unique businesses are collected.
    Each per-city call is cached (see _discover_via_places_api), so re-running a
    sweep is nearly free and resumes instantly from the cache. Cities are visited
    in the order given (the registry puts BC and bigger metros first)."""
    collected: dict[str, dict] = {}
    # Over-collect slightly so chain-filtering/deduping downstream still
    # leaves a full page of leads.
    target = int(max_results * 1.3) + 5
    total = len(cities)

    for i, c in enumerate(cities, 1):
        if len(collected) >= target:
            break
        remaining = target - len(collected)
        # Cap per-city pulls so one big city doesn't eat the whole budget and
        # the sweep still reaches smaller towns (often the weakest web presence).
        per_city = min(remaining, max(5, max_results // 4))
        log.info(f"[discovery] [{i}/{total}] {c}: searching (have {len(collected)}/{target})...")
        try:
            found = _discover_via_places_api(c, business_type, 15, per_city, api_key)
        except Exception as exc:
            log.warning(f"[discovery] {c} failed ({exc}) - skipping")
            continue
        added = 0
        for b in found:
            key = _norm_name(b.get("name", ""))
            if key and key not in collected and not _is_chain(b.get("name", "")):
                collected[key] = b
                added += 1
        if added:
            log.info(f"[discovery] {c}: +{added} new businesses")

    return list(collected.values())


def _sweep_region_via_openstreetmap(region, business_type, max_results):
    """Region Tier 2: run one Overpass area query per province in the region,
    concatenating and deduping the results. For a single-province region this is
    one query; for 'All of Canada' it iterates every province (BC first) until
    max_results is reached. Each province query is cached independently."""
    collected: list[dict] = []
    seen: set[str] = set()
    for prov in region["provinces"]:
        if len(collected) >= max_results:
            break
        try:
            found = _discover_area_via_openstreetmap(prov["iso"], business_type, max_results)
        except RuntimeError as exc:
            log.warning(f"[discovery] OSM area {prov['label']} failed ({exc}) - skipping")
            continue
        added = 0
        for b in found:
            key = _norm_name(b.get("name", ""))
            if key and key not in seen:
                seen.add(key)
                collected.append(b)
                added += 1
        if added:
            log.info(f"[discovery] OSM {prov['label']}: +{added} businesses")

    if not collected:
        raise RuntimeError(
            f"No OSM results for '{business_type}' across {region['label']}. "
            f"Try a broader business type."
        )
    return collected


def _discover_area_via_openstreetmap(iso, business_type, max_results):
    """Cached Tier 2 wrapper for a province-level Overpass area query. The
    underlying query can take up to 180s, so caching it is a big win for repeat
    sweeps. Keyed by ISO 3166-2 code + business type."""
    key = f"{iso}|{business_type.strip().lower()}"
    cached = cache.get("osm_area", key)
    if cached and cached.get("requested", 0) >= max_results:
        results = cached.get("results", [])
        log.info(f"[discovery] OSM {iso}: cache hit ({len(results)} cached)")
        return results[:max_results]
    results = _discover_area_via_openstreetmap_live(iso, business_type, max_results)
    if results:
        cache.set("osm_area", key, {"requested": max_results, "results": results})
    return results


def _discover_area_via_openstreetmap_live(iso, business_type, max_results):
    """Tier 2: one Overpass query over a whole province (by ISO 3166-2 code, e.g.
    'CA-BC') instead of a radius around a single city. Free, no key."""
    tag_pairs = _osm_tags_for(business_type)
    tag_lines = ""
    for key, val in tag_pairs:
        tag_lines += f'  node["{key}"="{val}"](area.reg);\n'
        tag_lines += f'  way["{key}"="{val}"](area.reg);\n'
    tag_query = (
        '[out:json][timeout:180];\n'
        f'area["ISO3166-2"="{iso}"]->.reg;\n'
        f"(\n{tag_lines});\nout center tags;"
    )

    elements = []
    try:
        elements = _run_overpass(tag_query)
    except RuntimeError as exc:
        log.warning(f"[discovery] Area ({iso}) structured OSM search failed: {exc}")

    businesses = []
    for el in elements:
        b = _osm_element_to_business(el, business_type, iso.split("-")[-1])
        if b:
            businesses.append(b)
    log.info(f"[discovery] OSM area ({iso}) structured search: {len(businesses)} results")

    # Name-regex fallback across the whole area — only when the structured
    # search came up short, since this is a heavier query.
    if len(businesses) < max_results:
        keywords = _osm_name_keywords(business_type)
        regex = "|".join(keywords)
        name_lines = ""
        for typ in ("node", "way"):
            for kv in ("shop", "craft", "office", "amenity", "leisure"):
                name_lines += f'  {typ}["{kv}"]["name"~"{regex}",i](area.reg);\n'
        name_query = (
            '[out:json][timeout:180];\n'
            f'area["ISO3166-2"="{iso}"]->.reg;\n'
            f"(\n{name_lines});\nout center tags;"
        )
        try:
            name_elements = _run_overpass(name_query)
            added = 0
            for el in name_elements:
                b = _osm_element_to_business(el, business_type, iso.split("-")[-1])
                if b:
                    businesses.append(b)
                    added += 1
            log.info(f"[discovery] OSM area ({iso}) name fallback: {added} additional candidates")
        except RuntimeError as exc:
            log.warning(f"[discovery] Area ({iso}) name fallback failed: {exc}")

    if not businesses:
        raise RuntimeError(
            f"No OSM results for '{business_type}' in {iso}. "
            f"Try a broader business type."
        )

    return _dedupe_businesses(businesses)


def _discover_via_foursquare(city: str, business_type: str, radius_km: int, max_results: int, api_key: str) -> list[dict]:
    """
    Tier 3: Foursquare Places API v3.
    Free tier: ~1000 calls/day. Key from developer.foursquare.com (starts with fsq3...).
    Add FOURSQUARE_API_KEY to .env
    """
    # Geocode city first using Nominatim
    lat, lon = _geocode_city(city)

    # Try Places API v3 first (standard free developer keys)
    endpoints = [
        {
            "url": "https://api.foursquare.com/v3/places/search",
            "headers": {
                "Authorization": api_key,  # v3: no Bearer prefix
                "Accept": "application/json",
            },
            "result_key": "results",
        },
        {
            "url": "https://places-api.foursquare.com/places/search",
            "headers": {
                "Authorization": f"Bearer {api_key}",
                "X-Places-Api-Version": "2025-06-17",
                "Accept": "application/json",
            },
            "result_key": "results",
        },
    ]

    limit = min(50, max_results)
    params = {
        "query":  business_type,
        "ll":     f"{lat},{lon}",
        "radius": radius_km * 1000,
        "limit":  limit,
    }

    resp = None
    results = []
    for ep in endpoints:
        try:
            r = requests.get(ep["url"], headers=ep["headers"], params=params, timeout=12)
            log.info(f"[discovery] Foursquare status: {r.status_code} ({ep['url'].split('/')[2]})")
            if r.status_code == 200:
                resp = r
                results = r.json().get(ep["result_key"], [])
                break
            elif r.status_code in (401, 403, 410):
                continue  # try next endpoint
            else:
                r.raise_for_status()
        except requests.HTTPError:
            continue

    if not results:
        raise RuntimeError("Foursquare: all endpoints failed (check your API key at developer.foursquare.com)")

    businesses = []
    for r in results:
        loc = r.get("location", {})
        address = ", ".join(p for p in [
            loc.get("address", loc.get("formatted_address", "")),
            loc.get("locality", loc.get("city", city)),
            loc.get("region", "BC"),
        ] if p)
        businesses.append({
            "name":             r.get("name", ""),
            "address":          address or f"{city}, BC",
            "phone":            r.get("tel", ""),
            "existing_website": r.get("website"),
            "rating":           r.get("rating"),
            "review_count":     0,
            "photos_count":     0,
            "category":         business_type,
            "city":             city,
            "source":           "foursquare",
        })

    return businesses[:max_results]


def _geocode_city(city: str):
    """Geocode '<city>, BC, Canada' to (lat, lon) via Nominatim. Raises with a
    clear message if the city cannot be resolved."""
    geo_headers = {"User-Agent": "BCBuisWebBuilderTool/1.0 contact@victoriaai.ca"}
    try:
        geo_resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city}, BC, Canada", "format": "json", "limit": 1},
            headers=geo_headers,
            timeout=10,
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"Geocoding failed for '{city}, BC' (Nominatim error: {exc}). "
            f"Check the city spelling and network connectivity."
        )
    if not geo_data:
        raise RuntimeError(
            f"Could not geocode '{city}, BC' — Nominatim returned no match. "
            f"Check the city spelling (it must be a real BC city/town)."
        )
    return float(geo_data[0]["lat"]), float(geo_data[0]["lon"])


_OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def _run_overpass(query: str) -> list:
    """POST an Overpass QL query, rotating across mirrors with retries/backoff.
    Returns the list of elements. Raises RuntimeError if ALL mirrors fail."""
    over_headers = {
        "User-Agent": "BCBuisWebBuilderTool/1.0 (contact@victoriaai.ca)",
        "Accept": "application/json",
    }
    last_exc = None
    for attempt, mirror in enumerate(_OVERPASS_MIRRORS):
        try:
            over_resp = requests.post(
                mirror, data={"data": query},
                headers=over_headers, timeout=40,
            )
            # 429 / 504 = rate-limited or overloaded; back off and try next mirror
            if over_resp.status_code in (429, 502, 503, 504):
                raise RuntimeError(f"mirror {mirror} returned {over_resp.status_code}")
            over_resp.raise_for_status()
            return over_resp.json().get("elements", [])
        except Exception as exc:
            last_exc = exc
            log.warning(f"[discovery] Overpass mirror failed ({mirror.split('/')[2]}): {exc}")
            time.sleep(min(2 ** attempt, 8))
            continue
    raise RuntimeError(
        f"All {len(_OVERPASS_MIRRORS)} Overpass mirrors failed (last error: {last_exc}). "
        f"The Overpass API may be rate-limiting or unreachable — retry shortly."
    )


def _osm_element_to_business(el: dict, business_type: str, city: str):
    """Convert one Overpass element to a business dict, or None if no usable name."""
    tags = el.get("tags", {})
    name = tags.get("name", "").strip()
    if not name:
        return None

    house  = tags.get("addr:housenumber", "")
    street = tags.get("addr:street", "")
    city_t = tags.get("addr:city", city)
    if house and street:
        address = f"{house} {street}, {city_t}, BC"
    elif street:
        address = f"{street}, {city_t}, BC"
    else:
        address = f"{city_t}, BC"

    phone   = tags.get("phone", tags.get("contact:phone", ""))
    website = tags.get("website", tags.get("contact:website", None))
    if website and not website.startswith("http"):
        website = "https://" + website

    return {
        "name":             name,
        "address":          address,
        "phone":            phone,
        "existing_website": website,
        "rating":           None,
        "review_count":     0,
        "photos_count":     0,
        "category":         business_type,
        "city":             city,
        "source":           "openstreetmap",
    }


def _discover_any_osm(city, lat, lon, radius_m, max_results):
    """Broad OSM search across ALL business categories (the 'any business'
    search) — surfaces every named local business so the weakness scoring can
    flag the ones with no/weak website. Free, no API key."""
    amenities = ("restaurant|cafe|bar|pub|fast_food|veterinary|dentist|doctors|"
                 "clinic|pharmacy|car_repair|car_wash|fuel|bank|fitness_centre")
    parts = []
    for typ in ("node", "way"):
        for kv in ("shop", "craft", "office"):
            parts.append(f'  {typ}["{kv}"]["name"](around:{radius_m},{lat},{lon});')
        parts.append(f'  {typ}["amenity"~"^({amenities})$"]["name"](around:{radius_m},{lat},{lon});')
    query = "[out:json][timeout:60];\n(\n" + "\n".join(parts) + "\n);\nout center tags;"
    elements = _run_overpass(query)
    businesses = []
    for el in elements:
        b = _osm_element_to_business(el, "business", city)
        if b:
            businesses.append(b)
    log.info(f"[discovery] OSM 'any business' search: {len(businesses)} businesses")
    if not businesses:
        raise RuntimeError(f"No OSM businesses found near {city}. Try a larger radius.")
    return _dedupe_businesses(businesses)


def _discover_via_openstreetmap(city: str, business_type: str, radius_km: int, max_results: int) -> list[dict]:
    """Cached Tier 2 wrapper around the live OSM/Overpass search (see below)."""
    key = f"{city.strip().lower()}|{business_type.strip().lower()}|{radius_km}"
    cached = cache.get("osm", key)
    if cached and cached.get("requested", 0) >= max_results:
        results = cached.get("results", [])
        log.info(f"[discovery] OpenStreetMap: cache hit for {business_type} in {city} ({len(results)} cached)")
        return results[:max_results]
    results = _discover_via_openstreetmap_live(city, business_type, radius_km, max_results)
    if results:
        cache.set("osm", key, {"requested": max_results, "results": results})
    return results


def _discover_via_openstreetmap_live(city: str, business_type: str, radius_km: int, max_results: int) -> list[dict]:
    """
    Tier 2: Real businesses from OpenStreetMap via Overpass API + Nominatim geocoding.
    Completely free, no API key required, returns real registered businesses.

    Strategy: a structured tag search (precise) combined with a name-regex
    fallback (broad — catches businesses tagged inconsistently in OSM). Results
    are merged and deduped.
    """
    lat, lon = _geocode_city(city)
    radius_m = radius_km * 1000

    # "any business" → broad all-category search
    if business_type.strip().lower() in ANY_BUSINESS_TERMS:
        return _discover_any_osm(city, lat, lon, radius_m, max_results)

    # --- Structured tag search -------------------------------------------------
    tag_pairs = _osm_tags_for(business_type)
    tag_lines = ""
    for key, val in tag_pairs:
        tag_lines += f'  node["{key}"="{val}"](around:{radius_m},{lat},{lon});\n'
        tag_lines += f'  way["{key}"="{val}"](around:{radius_m},{lat},{lon});\n'
    tag_query = f"[out:json][timeout:40];\n(\n{tag_lines});\nout center tags;"

    elements = []
    try:
        elements = _run_overpass(tag_query)
    except RuntimeError as exc:
        # Surface mirror failures, but still attempt the name fallback below.
        log.warning(f"[discovery] Structured OSM search failed: {exc}")

    businesses = []
    for el in elements:
        b = _osm_element_to_business(el, business_type, city)
        if b:
            businesses.append(b)
    log.info(f"[discovery] OSM structured search: {len(businesses)} results")

    # --- Name-based fallback ---------------------------------------------------
    # When the structured search returns few results, many real businesses are
    # simply tagged inconsistently. Search by name regex for each keyword.
    if len(businesses) < max_results:
        keywords = _osm_name_keywords(business_type)
        regex = "|".join(keywords)
        # Limit fallback to plausible business-like objects (shop/craft/office/amenity).
        name_lines = ""
        for typ in ("node", "way"):
            for kv in ("shop", "craft", "office", "amenity", "leisure"):
                name_lines += (
                    f'  {typ}["{kv}"]["name"~"{regex}",i]'
                    f"(around:{radius_m},{lat},{lon});\n"
                )
        name_query = f"[out:json][timeout:40];\n(\n{name_lines});\nout center tags;"
        try:
            name_elements = _run_overpass(name_query)
            added = 0
            for el in name_elements:
                b = _osm_element_to_business(el, business_type, city)
                if b:
                    businesses.append(b)
                    added += 1
            log.info(f"[discovery] OSM name fallback: {added} additional candidates")
        except RuntimeError as exc:
            log.warning(f"[discovery] Name fallback search failed: {exc}")

    if not businesses:
        raise RuntimeError(
            f"No OSM results for '{business_type}' in {city}, BC "
            f"(radius {radius_km}km). Try a broader business type or a larger radius."
        )

    businesses = _dedupe_businesses(businesses)
    return businesses


# Words that signal a national chain / franchise — these are NOT good leads for a
# bespoke website build (they already have corporate sites).
_CHAIN_SIGNALS = {
    "mcdonald", "starbucks", "tim hortons", "subway", "walmart", "costco",
    "shoppers drug", "save-on-foods", "safeway", "a&w", "wendy", "kfc",
    "dairy queen", "boston pizza", "white spot", "7-eleven", "shell", "esso",
    "petro-canada", "chevron", "canadian tire", "home depot", "rona", "lowe",
    "best buy", "staples", "dollarama", "london drugs", "jiffy lube",
    "great clips", "domino", "pizza hut", "dominos",
}


def _norm_name(name: str) -> str:
    """Normalize a business name for dedupe/chain matching."""
    n = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    # Drop common legal/marketing suffixes that vary between listings.
    n = re.sub(r"\b(ltd|inc|llc|co|corp|company|limited|services|service)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _is_chain(name: str) -> bool:
    low = (name or "").lower()
    return any(sig in low for sig in _CHAIN_SIGNALS)


def _dedupe_businesses(businesses: list[dict]) -> list[dict]:
    """Remove duplicates by normalized name (and same name+address). When two
    entries collide, keep the one with the most complete data (website/phone)."""
    def completeness(b: dict) -> int:
        score = 0
        if b.get("existing_website"):
            score += 2
        if b.get("phone"):
            score += 1
        if b.get("address") and not b["address"].strip().startswith(","):
            score += 1
        return score

    best: dict[str, dict] = {}
    for b in businesses:
        name = b.get("name", "").strip()
        if not name or _is_chain(name):
            continue
        key = _norm_name(name)
        if not key:
            continue
        if key not in best or completeness(b) > completeness(best[key]):
            best[key] = b
    return list(best.values())


def _osm_name_keywords(business_type: str) -> list:
    """Keyword stems used for the Overpass name-regex fallback search."""
    bt = business_type.lower()
    mapping = [
        (["plumb"],                         ["plumb"]),
        (["electr"],                        ["electric", "electrical"]),
        (["landscap", "garden", "lawn"],    ["landscap", "garden", "lawn", "yard", "nursery"]),
        (["hvac", "heating", "cooling"],    ["hvac", "heating", "furnace", "air condition"]),
        (["roof"],                          ["roof"]),
        (["paint"],                         ["paint"]),
        (["carpet", "floor"],               ["floor", "carpet", "tile"]),
        (["window", "glass"],               ["window", "glass", "glaz"]),
        (["restaurant", "dining"],          ["restaurant", "grill", "bistro", "eatery"]),
        (["cafe", "coffee"],                ["cafe", "coffee", "espresso"]),
        (["salon", "hair"],                 ["salon", "hair"]),
        (["barber"],                        ["barber"]),
        (["nail"],                          ["nail"]),
        (["spa", "massage"],                ["spa", "massage", "wellness"]),
        (["dentist", "dental"],             ["dental", "dentist"]),
        (["physio"],                        ["physio", "physical therapy"]),
        (["optician", "optical"],           ["optic", "eyewear", "vision"]),
        (["mechanic", "auto repair", "car repair"], ["auto", "mechanic", "automotive", "car repair"]),
        (["tire", "tyre"],                  ["tire", "tyre"]),
        (["bakery", "baker"],               ["baker", "bread", "pastry"]),
        (["butcher"],                       ["butcher", "meat"]),
        (["grocery", "grocer"],             ["grocer", "market", "food"]),
        (["pharmacy", "drug"],              ["pharmacy", "drug"]),
        (["gym", "fitness"],                ["gym", "fitness", "crossfit"]),
        (["yoga"],                          ["yoga"]),
        (["clean", "laundry"],              ["clean", "laundry", "janitorial", "maid"]),
        (["accountant", "accounting"],      ["account", "bookkeep", "cpa"]),
        (["lawyer", "legal"],               ["law", "legal", "attorney", "notary"]),
        (["real estate", "realtor"],        ["realty", "real estate", "realtor"]),
        (["insurance"],                     ["insurance"]),
        (["vet", "veterinar"],              ["vet", "animal"]),
        (["pet", "dog groom"],              ["pet", "groom", "kennel"]),
        (["photographer"],                  ["photo"]),
        (["tattoo"],                        ["tattoo", "ink"]),
        (["contractor", "construction"],    ["contract", "construction", "renovation", "reno", "build"]),
        (["handyman", "handy"],             ["handyman", "handy", "repair"]),
        (["mov", "haul"],                   ["moving", "movers", "haul"]),
    ]
    for keywords, stems in mapping:
        if any(k in bt for k in keywords):
            return stems
    # Generic: use the words of the business type itself.
    words = [w for w in re.split(r"\s+", bt) if len(w) > 2]
    return words or [bt]


def _osm_tags_for(business_type: str) -> list:
    """Map a plain-English business type to OpenStreetMap tag key/value pairs."""
    bt = business_type.lower()
    mapping = [
        (["plumb"],                         [("craft", "plumber"), ("trade", "plumber"), ("shop", "plumber")]),
        (["electr"],                        [("craft", "electrician"), ("trade", "electrician")]),
        (["landscap", "garden", "lawn"],    [("craft", "gardener"), ("shop", "garden_centre"),
                                             ("landuse", "plant_nursery"), ("shop", "nursery"),
                                             ("trade", "gardener")]),
        (["hvac", "heating", "cooling"],    [("craft", "hvac"), ("trade", "hvac"), ("craft", "heating_engineer")]),
        (["roof"],                          [("craft", "roofer"), ("trade", "roofer")]),
        (["paint"],                         [("craft", "painter"), ("trade", "painter")]),
        (["carpet", "floor"],               [("craft", "floorer"), ("trade", "floorer"), ("shop", "flooring")]),
        (["window", "glass"],               [("craft", "glaziery"), ("craft", "window_construction"), ("shop", "glaziery")]),
        (["restaurant", "dining"],          [("amenity", "restaurant")]),
        (["cafe", "coffee"],                [("amenity", "cafe")]),
        (["salon", "hair"],                 [("shop", "hairdresser"), ("shop", "beauty")]),
        (["barber"],                        [("shop", "barber"), ("shop", "hairdresser")]),
        (["nail"],                          [("shop", "nail_salon"), ("shop", "beauty"), ("beauty", "nails")]),
        (["spa", "massage"],                [("leisure", "spa"), ("amenity", "massage"),
                                             ("shop", "massage"), ("healthcare", "physiotherapist")]),
        (["dentist", "dental"],             [("amenity", "dentist"), ("healthcare", "dentist")]),
        (["physio"],                        [("amenity", "physiotherapist"), ("healthcare", "physiotherapist")]),
        (["optician", "optical"],           [("shop", "optician")]),
        (["mechanic", "auto repair", "car repair"], [("shop", "car_repair")]),
        (["tire", "tyre"],                  [("shop", "tyres")]),
        (["bakery", "baker"],               [("shop", "bakery"), ("shop", "pastry"), ("craft", "bakery")]),
        (["butcher"],                       [("shop", "butcher")]),
        (["grocery", "grocer"],             [("shop", "supermarket"), ("shop", "convenience"), ("shop", "greengrocer")]),
        (["pharmacy", "drug"],              [("amenity", "pharmacy")]),
        (["gym", "fitness"],                [("leisure", "fitness_centre"), ("leisure", "sports_centre")]),
        (["yoga"],                          [("leisure", "yoga"), ("sport", "yoga")]),
        (["clean", "laundry"],              [("shop", "dry_cleaning"), ("shop", "laundry"),
                                             ("craft", "cleaning"), ("office", "cleaning")]),
        (["accountant", "accounting"],      [("office", "accountant"), ("office", "tax_advisor")]),
        (["lawyer", "legal"],               [("office", "lawyer"), ("office", "notary")]),
        (["real estate", "realtor"],        [("office", "real_estate_agent")]),
        (["insurance"],                     [("office", "insurance")]),
        (["vet", "veterinar"],              [("amenity", "veterinary")]),
        (["pet", "dog groom"],              [("shop", "pet"), ("shop", "pet_grooming")]),
        (["photographer"],                  [("craft", "photographer"), ("shop", "photo")]),
        (["tattoo"],                        [("shop", "tattoo")]),
        (["contractor", "construction"],    [("craft", "builder"), ("craft", "carpenter"),
                                             ("office", "construction_company"), ("trade", "builder")]),
        (["handyman", "handy"],             [("craft", "handyman"), ("craft", "carpenter")]),
        (["mov", "haul"],                   [("shop", "moving_company"), ("office", "moving_company")]),
    ]
    for keywords, tags in mapping:
        if any(k in bt for k in keywords):
            return tags
    # Generic fallback — search by name keyword (less precise but broad)
    return [("shop", business_type), ("craft", business_type), ("amenity", business_type)]


def _demo_businesses(city, business_type):
    """Realistic fake BC business data for UI testing when no API keys are set."""
    templates = [
        {"name": f"{city} {business_type.title()} Pro",          "has_site": False, "ssl": False, "mobile": False, "reviews": 3,  "photos": 0, "booking": False},
        {"name": f"Pacific {business_type.title()} Services",    "has_site": True,  "ssl": False, "mobile": False, "reviews": 5,  "photos": 0, "booking": False, "site_age": 5},
        {"name": f"West Coast {business_type.title()}",          "has_site": True,  "ssl": False, "mobile": True,  "reviews": 8,  "photos": 1, "booking": False, "site_age": 4},
        {"name": f"Island {business_type.title()} Co.",          "has_site": False, "ssl": False, "mobile": False, "reviews": 2,  "photos": 0, "booking": False},
        {"name": f"Cascade {business_type.title()} Solutions",   "has_site": True,  "ssl": True,  "mobile": False, "reviews": 12, "photos": 2, "booking": False, "site_age": 3},
        {"name": f"Coastal {business_type.title()} Ltd.",        "has_site": True,  "ssl": True,  "mobile": True,  "reviews": 7,  "photos": 0, "booking": False, "site_age": 2},
        {"name": f"Mountain View {business_type.title()}",       "has_site": False, "ssl": False, "mobile": False, "reviews": 1,  "photos": 0, "booking": False},
        {"name": f"BC {business_type.title()} Experts",          "has_site": True,  "ssl": True,  "mobile": True,  "reviews": 22, "photos": 5, "booking": True,  "site_age": 1},
        {"name": f"Harbour {business_type.title()} Group",       "has_site": True,  "ssl": False, "mobile": False, "reviews": 4,  "photos": 1, "booking": False, "site_age": 6},
        {"name": f"Mainland {business_type.title()} & Repair",  "has_site": True,  "ssl": True,  "mobile": True,  "reviews": 31, "photos": 8, "booking": False, "site_age": 0},
    ]
    phones = ["250-382-4411","250-475-0920","250-388-7733","250-881-2210","250-744-6632","250-590-3341","250-721-0087","250-380-1955","250-475-8823","250-383-6640"]
    results = []
    for i, t in enumerate(templates):
        site_year = CURRENT_YEAR - t.get("site_age", 0) if t.get("has_site") else None
        health = {
            "accessible": t["has_site"], "ssl": t.get("ssl", False),
            "broken": False, "parked": False,
            "outdated": t.get("site_age", 0) >= 3,
            "mobile_responsive": t.get("mobile", False),
            "has_booking": t.get("booking", False),
            "status_code": 200 if t["has_site"] else None,
            "last_copyright_year": site_year,
        } if t["has_site"] else None
        results.append({
            "name":             t["name"],
            "address":          f"{100 + i * 111} Oak St, {city}, BC",
            "phone":            phones[i],
            "existing_website": f"http://www.{t['name'].lower().replace(' ','').replace('.','')}.ca" if t["has_site"] else None,
            "rating":           round(3.2 + (i % 5) * 0.4, 1),
            "review_count":     t["reviews"],
            "photos_count":     t["photos"],
            "category":         business_type,
            "city":             city,
            "source":           "demo",
            "website_health":   health,
            "_demo":            True,
        })
    return results


def _check_all_websites(businesses):
    """Run website health checks in parallel (skips businesses already checked in demo mode)."""
    to_check = [b for b in businesses if b.get("website_health") is None]
    already  = [b for b in businesses if b.get("website_health") is not None]

    def check(biz):
        url = biz.get("existing_website")
        biz["website_health"] = _check_website_health(url) if url else None
        return biz

    checked = []
    if to_check:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(check, b): b for b in to_check}
            for i, f in enumerate(as_completed(futures), 1):
                try:
                    checked.append(f.result())
                except Exception:
                    checked.append(futures[f])
                if i % 5 == 0:
                    log.info(f"[discovery] Website checks: {i}/{len(to_check)}")
    return checked + already


def _check_website_health(url):
    """Cached HTTP health check. Results are cached for the default TTL keyed by
    URL, so the same site is never re-fetched across discovery runs. Only "real"
    results (we actually reached the site) are cached - transient failures
    (timeout/DNS) are left uncached so they get retried next time."""
    if not url:
        return _check_website_health_uncached(url)
    key = url.strip().lower().rstrip("/")
    cached = cache.get("health", key)
    if cached is not None:
        return cached
    health = _check_website_health_uncached(url)
    if health.get("status_code") is not None or health.get("accessible"):
        cache.set("health", key, health)
    return health


def _check_website_health_uncached(url):
    """HTTP-level health check: SSL, broken, parked, outdated, mobile, booking."""
    health = {"accessible": False, "ssl": False, "broken": True, "parked": False,
              "outdated": False, "mobile_responsive": False, "has_booking": False,
              "status_code": None, "last_copyright_year": None}
    if not url:
        return health
    if not url.startswith("http"):
        url = "https://" + url
    health["ssl"] = url.startswith("https://")
    try:
        resp = requests.get(url, timeout=8, allow_redirects=True, headers=_HEADERS, verify=False)
        health["status_code"] = resp.status_code
        health["broken"]      = resp.status_code >= 400
        if resp.status_code < 400:
            health["accessible"] = True
            text = resp.text.lower()
            health["parked"]            = any(s in text for s in _PARKED_SIGNALS)
            health["mobile_responsive"] = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', resp.text, re.I))
            health["has_booking"]       = any(s in text for s in _BOOKING_SIGNALS)
            years = re.findall(r"(?:copyright|\xa9)\s*(?:\d{4}\s*[-]\s*)?(\d{4})", text)
            if years:
                latest = max((int(y) for y in years if 1990 < int(y) <= CURRENT_YEAR + 1), default=None)
                if latest:
                    health["last_copyright_year"] = latest
                    health["outdated"] = (CURRENT_YEAR - latest) >= 3
    except requests.exceptions.SSLError:
        health["ssl"] = False; health["accessible"] = True; health["broken"] = False
    except Exception:
        pass
    return health


def _enrich(businesses):
    """Normalise phone, extract city from address, flag for BC Registry check."""
    for b in businesses:
        if not b.get("city"):
            m = re.search(r",\s*([A-Za-z\s]+),?\s*BC", b.get("address", ""))
            b["city"] = m.group(1).strip() if m else "BC"
        phone = re.sub(r"[^\d]", "", b.get("phone", ""))
        if len(phone) == 10:
            b["phone"] = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
        elif len(phone) == 11 and phone[0] == "1":
            b["phone"] = f"{phone[1:4]}-{phone[4:7]}-{phone[7:]}"
        if not b.get("existing_website"):
            b["bc_registry_check_needed"] = True
    return businesses


def _latest_review_age_days(reviews) -> int | None:
    """Age in days of the newest review, from a Google Places `reviews` list
    (each item has a unix `time`). None when there are no usable timestamps."""
    if not reviews:
        return None
    times = [r.get("time") for r in reviews if isinstance(r.get("time"), (int, float))]
    if not times:
        return None
    newest = max(times)
    return max(0, int((time.time() - newest) / 86400))


# High-LTV industries that can comfortably afford recurring web/marketing
# retainers ($300-1500/mo) - these make the best leads.
_INDUSTRY_HIGH = (
    "plumb", "electric", "hvac", "heating", "roof", "contractor", "construction",
    "renovation", "landscap", "dentist", "dental", "lawyer", "legal", "attorney",
    "notary", "accountant", "accounting", "real estate", "realtor", "insurance",
    "chiropract", "physio", "cosmetic", "medical", "clinic", "law",
)
# Mid-LTV service businesses.
_INDUSTRY_MED = (
    "salon", "spa", "barber", "hair", "nail", "beauty", "mechanic", "auto",
    "tire", "gym", "fitness", "yoga", "vet", "veterinar", "pet", "groom",
    "painter", "painting", "clean", "floor", "carpet", "window", "glass",
    "photographer", "tattoo", "handyman", "moving",
)


def _industry_score(business) -> tuple[int, str | None]:
    """Ability-to-pay signal from the business category/name. Returns
    (points, flag). High-LTV trades/professional services score highest."""
    hay = f"{business.get('category', '')} {business.get('name', '')}".lower()
    if any(k in hay for k in _INDUSTRY_HIGH):
        return SCORE_INDUSTRY_HIGH, "high_value_industry"
    if any(k in hay for k in _INDUSTRY_MED):
        return SCORE_INDUSTRY_MED, "mid_value_industry"
    return 0, None


def _value_signals(business) -> tuple[int, list[str]]:
    """Cheap, metadata-only lead signals (no HTTP): missing photos/reviews,
    stale reviews, and industry ability-to-pay. Shared by the prescore gate and
    the final score so both stay consistent."""
    score = 0
    flags: list[str] = []
    if business.get("photos_count", 0) == 0:
        score += SCORE_NO_PHOTOS; flags.append("no_photos")
    reviews = business.get("review_count", 0) or 0
    if reviews == 0:
        score += SCORE_NO_REVIEWS; flags.append("no_reviews")
    elif reviews < 10:
        score += SCORE_FEW_REVIEWS; flags.append("few_reviews")
    age = business.get("latest_review_age_days")
    if age is not None and age > STALE_REVIEW_DAYS:
        score += SCORE_STALE_REVIEWS; flags.append("stale_reviews")
    ipts, iflag = _industry_score(business)
    if ipts:
        score += ipts
        flags.append(iflag)
    return score, flags


def _prescore_business(business) -> int:
    """Cheap metadata-only estimate of lead quality, used to decide whether a
    lead is worth the expensive website-health HTTP check. Knows about the
    no-website win and the value signals, but not site health (which is exactly
    what the HTTP check resolves)."""
    score = 0
    if not business.get("existing_website"):
        score += SCORE_NO_WEBSITE
    pts, _ = _value_signals(business)
    score += pts
    return min(score, 10)


def _score_business(business):
    """Score 0-10 on web presence weakness. Higher = better lead.

    A business with a genuinely strong existing site (accessible, SSL,
    mobile-responsive, recent copyright, booking) should score very low and
    sink to the bottom. No-website / broken / outdated businesses rise to the
    top. Photo/review/industry signals only count as tie-breakers when the
    website itself isn't already strong, so a strong-site business can't be
    pushed up the ranking purely by metadata.
    """
    score = 0; flags = []
    health  = business.get("website_health")
    website = business.get("existing_website")

    site_is_strong = False
    if not website:
        score += SCORE_NO_WEBSITE; flags.append("no_website")
    elif health:
        if health.get("broken") or health.get("parked"):
            score += SCORE_BROKEN_WEBSITE
            flags.append("broken_website" if health.get("broken") else "parked_domain")
        if health.get("outdated"):    score += SCORE_OUTDATED;    flags.append("outdated_website")
        if not health.get("ssl"):     score += SCORE_NO_SSL;      flags.append("no_ssl")
        if not health.get("mobile_responsive"): score += SCORE_NOT_MOBILE; flags.append("not_mobile_responsive")
        if not health.get("has_booking"): score += SCORE_NO_BOOKING; flags.append("no_booking_form")

        # A site is "strong" if it's accessible, secure, mobile-friendly, not
        # broken/parked/outdated, and ideally has booking + a recent copyright.
        recent = True
        cy = health.get("last_copyright_year")
        if cy is not None:
            recent = (CURRENT_YEAR - cy) < 3
        site_is_strong = (
            health.get("accessible")
            and health.get("ssl")
            and health.get("mobile_responsive")
            and not health.get("broken")
            and not health.get("parked")
            and not health.get("outdated")
            and recent
        )
    else:
        # Has a website URL but we skipped the HTTP check (low prescore). We
        # don't know the site's quality, so we add no website points and flag it
        # for transparency - it ranks on metadata signals alone.
        flags.append("site_unchecked")

    # Value signals (missing photos/reviews, stale reviews, industry) only count
    # when the website isn't already strong, so a strong-site business can't be
    # lifted up the ranking by metadata we may not even reliably have.
    if not site_is_strong:
        vpts, vflags = _value_signals(business)
        score += vpts; flags += vflags
    else:
        flags.append("strong_existing_site")

    business["score"]          = min(score, 10)
    business["weakness_flags"] = flags
    business["notes"]          = " - ".join(f.replace("_", " ") for f in flags) or "Minimal issues"
    # Normalise the output schema: a lead whose site was never checked (no URL,
    # or skipped by the prescore gate) still carries the key, set to None, so
    # downstream consumers (leads.json, dashboard) see a consistent shape.
    business.setdefault("website_health", None)
    return business


def save_leads(leads, output_dir="./output"):
    """Write ranked leads to {output_dir}/leads.json."""
    out  = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "leads.json"
    path.write_text(json.dumps(leads, indent=2, ensure_ascii=False))
    log.info(f"[discovery] Saved {len(leads)} leads -> {path}")
    return path
