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

load_dotenv()

# Scoring weights
SCORE_NO_WEBSITE      = 4
SCORE_BROKEN_WEBSITE  = 3
SCORE_OUTDATED        = 2
SCORE_NO_SSL          = 1
SCORE_NOT_MOBILE      = 1
SCORE_NO_PHOTOS       = 1
SCORE_FEW_REVIEWS     = 1
SCORE_NO_BOOKING      = 1

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


# City input values that mean "search the whole province" instead of one city.
_PROVINCE_ALIASES = {
    "bc", "b.c.", "british columbia", "all of bc", "all bc", "province",
    "province-wide", "province wide", "provincewide", "all", "everywhere",
}

# BC municipalities swept (largest first) when running a province-wide search
# against city-based APIs like Google Places.
BC_CITIES = [
    "Vancouver", "Surrey", "Burnaby", "Richmond", "Abbotsford", "Coquitlam",
    "Kelowna", "Langley", "Saanich", "Delta", "Victoria", "Kamloops",
    "Nanaimo", "Chilliwack", "Maple Ridge", "Prince George", "New Westminster",
    "Port Coquitlam", "North Vancouver", "Vernon", "Courtenay", "Campbell River",
    "Penticton", "Mission", "Port Moody", "West Vancouver", "Duncan",
    "White Rock", "Salmon Arm", "Fort St. John", "Cranbrook", "Squamish",
    "Parksville", "Port Alberni", "Comox", "Terrace", "Powell River",
    "Sidney", "Quesnel", "Williams Lake", "Dawson Creek", "Nelson",
    "Sechelt", "Whistler", "Ladysmith", "Sooke",
]


def is_province_wide(city: str) -> bool:
    return (city or "").strip().lower() in _PROVINCE_ALIASES


def discover_businesses(
    city: str,
    business_type: str,
    radius_km: int = 15,
    max_results: int = 50,
) -> list[dict]:
    """
    Run the full Phase 1 discovery pipeline for a city + business type.
    Tries each tier in order, scoring and ranking all results.

    Province-wide mode: pass city as "British Columbia" / "All of BC" / "BC"
    to search the entire province (Google sweeps BC_CITIES city by city;
    OpenStreetMap runs one query over the BC provincial boundary).
    """
    google_key = os.getenv("GOOGLE_MAPS_API_KEY")
    fsq_key    = os.getenv("FOURSQUARE_API_KEY")
    demo_mode  = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
    province   = is_province_wide(city)

    businesses: list[dict] = []

    if google_key:
        if province:
            print(f"[discovery] Tier 1 - Google Places API: {business_type} province-wide ({len(BC_CITIES)} BC cities)")
            try:
                businesses = _discover_province_via_places_api(business_type, max_results, google_key)
                print(f"[discovery] Google Places (province-wide): {len(businesses)} results")
            except Exception as exc:
                print(f"[discovery] Google Places failed ({exc}) - trying next tier")
        else:
            print(f"[discovery] Tier 1 - Google Places API: {business_type} in {city}, BC")
            try:
                businesses = _discover_via_places_api(city, business_type, radius_km, max_results, google_key)
                print(f"[discovery] Google Places: {len(businesses)} results")
            except Exception as exc:
                print(f"[discovery] Google Places failed ({exc}) - trying next tier")

    if not businesses:
        if province:
            print(f"[discovery] Tier 2 - OpenStreetMap: {business_type} across all of BC")
            try:
                businesses = _discover_province_via_openstreetmap(business_type, max_results)
                print(f"[discovery] OpenStreetMap (province-wide): {len(businesses)} real businesses found")
            except Exception as exc:
                print(f"[discovery] OpenStreetMap failed ({exc}) - trying next tier")
        else:
            print(f"[discovery] Tier 2 - OpenStreetMap: {business_type} in {city}, BC")
            try:
                businesses = _discover_via_openstreetmap(city, business_type, radius_km, max_results)
                print(f"[discovery] OpenStreetMap: {len(businesses)} real businesses found")
            except Exception as exc:
                print(f"[discovery] OpenStreetMap failed ({exc}) - trying next tier")

    if not businesses and fsq_key:
        print(f"[discovery] Tier 3 - Foursquare Places API: {business_type} in {city}, BC")
        try:
            businesses = _discover_via_foursquare(city, business_type, radius_km, max_results, fsq_key)
            print(f"[discovery] Foursquare: {len(businesses)} results")
        except Exception as exc:
            print(f"[discovery] Foursquare failed ({exc}) - no more tiers")

    if not businesses:
        if demo_mode:
            print(f"[discovery] Demo mode - generating sample leads for {business_type} in {city}, BC")
            businesses = _demo_businesses(city, business_type)
        else:
            print(
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
            print(f"[discovery] Deduped/filtered {before} -> {len(businesses)} businesses")

    if not businesses:
        print(
            f"[discovery] All candidates for '{business_type}' in {city}, BC were "
            f"duplicates or chains — try a broader business type or a larger radius."
        )
        return []

    print(f"[discovery] Checking website health for {len(businesses)} businesses...")
    businesses = _check_all_websites(businesses)
    businesses = _enrich(businesses)

    scored = [_score_business(b) for b in businesses]
    ranked = sorted(scored, key=lambda b: b["score"], reverse=True)
    for i, b in enumerate(ranked, start=1):
        b["rank"] = i

    top = ranked[:max_results]
    if top:
        print(f"[discovery] Done - {len(top)} leads ranked. Top score: {top[0]['score']}/10 ({top[0]['name']})")
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
        print(f"[discovery] Google Places: cache hit for {business_type} in {city} ({len(results)} cached)")
        return results[:max_results]
    results = _discover_via_places_api_live(city, business_type, radius_km, max_results, api_key)
    if results:
        cache.set("places", key, {"requested": max_results, "results": results})
    return results


def _discover_via_places_api_live(city, business_type, radius_km, max_results, api_key):
    """Tier 1: Google Maps Text Search + Place Details."""
    query      = f"{business_type} in {city}, BC, Canada"
    search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    detail_url = "https://maps.googleapis.com/maps/api/place/details/json"
    fields     = "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,photos,opening_hours,business_status"

    place_ids = []
    params = {"query": query, "key": api_key}

    while len(place_ids) < max_results:
        resp = requests.get(search_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            raise RuntimeError(f"Places API: {status} - {data.get('error_message', '')}")
        for r in data.get("results", []):
            place_ids.append(r["place_id"])
            if len(place_ids) >= max_results:
                break
        token = data.get("next_page_token")
        if not token or len(place_ids) >= max_results:
            break
        time.sleep(2)
        params = {"pagetoken": token, "key": api_key}

    print(f"[discovery] Fetching details for {len(place_ids)} places...")
    businesses = []
    for i, pid in enumerate(place_ids):
        try:
            r = requests.get(detail_url, params={"place_id": pid, "fields": fields, "key": api_key}, timeout=10).json().get("result", {})
            businesses.append({
                "name":             r.get("name", ""),
                "address":          r.get("formatted_address", ""),
                "phone":            r.get("formatted_phone_number", ""),
                "existing_website": r.get("website"),
                "rating":           r.get("rating"),
                "review_count":     r.get("user_ratings_total", 0),
                "photos_count":     len(r.get("photos", [])),
                "category":         business_type,
                "city":             city,
                "source":           "google_places",
            })
            if (i + 1) % 5 == 0:
                print(f"[discovery] Place details: {i + 1}/{len(place_ids)}")
            time.sleep(0.1)
        except Exception as exc:
            print(f"[discovery] Detail fetch failed for {pid}: {exc}")

    return businesses



def _discover_province_via_places_api(business_type, max_results, api_key):
    """Province-wide Tier 1: sweep BC_CITIES with Google Places, city by city,
    deduping as we go, until max_results unique businesses are collected.
    Each city costs ~1 text-search call + 1 details call per new business."""
    collected: dict[str, dict] = {}
    # Over-collect slightly so chain-filtering/deduping downstream still
    # leaves a full page of leads.
    target = int(max_results * 1.3) + 5

    for i, c in enumerate(BC_CITIES, 1):
        if len(collected) >= target:
            break
        remaining = target - len(collected)
        # Cap per-city pulls so one big city doesn't eat the whole budget and
        # the sweep still reaches smaller towns (often the weakest web presence).
        per_city = min(remaining, max(5, max_results // 4))
        print(f"[discovery] [{i}/{len(BC_CITIES)}] {c}: searching (have {len(collected)}/{target})...")
        try:
            found = _discover_via_places_api(c, business_type, 15, per_city, api_key)
        except Exception as exc:
            print(f"[discovery] {c} failed ({exc}) - skipping")
            continue
        added = 0
        for b in found:
            key = _norm_name(b.get("name", ""))
            if key and key not in collected and not _is_chain(b.get("name", "")):
                collected[key] = b
                added += 1
        if added:
            print(f"[discovery] {c}: +{added} new businesses")

    return list(collected.values())


def _discover_province_via_openstreetmap(business_type, max_results):
    """Cached province-wide Tier 2 wrapper. The underlying Overpass query can take
    up to 180s, so caching it is a big win for repeat BC-wide sweeps."""
    key = business_type.strip().lower()
    cached = cache.get("osm_province", key)
    if cached and cached.get("requested", 0) >= max_results:
        results = cached.get("results", [])
        print(f"[discovery] OSM province-wide: cache hit ({len(results)} cached)")
        return results[:max_results]
    results = _discover_province_via_openstreetmap_live(business_type, max_results)
    if results:
        cache.set("osm_province", key, {"requested": max_results, "results": results})
    return results


def _discover_province_via_openstreetmap_live(business_type, max_results):
    """Province-wide Tier 2: one Overpass query over the entire BC provincial
    boundary instead of a radius around a single city. Free, no key."""
    tag_pairs = _osm_tags_for(business_type)
    tag_lines = ""
    for key, val in tag_pairs:
        tag_lines += f'  node["{key}"="{val}"](area.bc);\n'
        tag_lines += f'  way["{key}"="{val}"](area.bc);\n'
    tag_query = (
        '[out:json][timeout:180];\n'
        'area["ISO3166-2"="CA-BC"]->.bc;\n'
        f"(\n{tag_lines});\nout center tags;"
    )

    elements = []
    try:
        elements = _run_overpass(tag_query)
    except RuntimeError as exc:
        print(f"[discovery] Province-wide structured OSM search failed: {exc}")

    businesses = []
    for el in elements:
        b = _osm_element_to_business(el, business_type, "BC")
        if b:
            businesses.append(b)
    print(f"[discovery] OSM province-wide structured search: {len(businesses)} results")

    # Name-regex fallback across the whole province — only when the structured
    # search came up short, since this is a heavier query.
    if len(businesses) < max_results:
        keywords = _osm_name_keywords(business_type)
        regex = "|".join(keywords)
        name_lines = ""
        for typ in ("node", "way"):
            for kv in ("shop", "craft", "office", "amenity", "leisure"):
                name_lines += f'  {typ}["{kv}"]["name"~"{regex}",i](area.bc);\n'
        name_query = (
            '[out:json][timeout:180];\n'
            'area["ISO3166-2"="CA-BC"]->.bc;\n'
            f"(\n{name_lines});\nout center tags;"
        )
        try:
            name_elements = _run_overpass(name_query)
            added = 0
            for el in name_elements:
                b = _osm_element_to_business(el, business_type, "BC")
                if b:
                    businesses.append(b)
                    added += 1
            print(f"[discovery] OSM province-wide name fallback: {added} additional candidates")
        except RuntimeError as exc:
            print(f"[discovery] Province-wide name fallback failed: {exc}")

    if not businesses:
        raise RuntimeError(
            f"No OSM results for '{business_type}' anywhere in BC. "
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
            print(f"[discovery] Foursquare status: {r.status_code} ({ep['url'].split('/')[2]})")
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
            print(f"[discovery] Overpass mirror failed ({mirror.split('/')[2]}): {exc}")
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


def _discover_via_openstreetmap(city: str, business_type: str, radius_km: int, max_results: int) -> list[dict]:
    """Cached Tier 2 wrapper around the live OSM/Overpass search (see below)."""
    key = f"{city.strip().lower()}|{business_type.strip().lower()}|{radius_km}"
    cached = cache.get("osm", key)
    if cached and cached.get("requested", 0) >= max_results:
        results = cached.get("results", [])
        print(f"[discovery] OpenStreetMap: cache hit for {business_type} in {city} ({len(results)} cached)")
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
        print(f"[discovery] Structured OSM search failed: {exc}")

    businesses = []
    for el in elements:
        b = _osm_element_to_business(el, business_type, city)
        if b:
            businesses.append(b)
    print(f"[discovery] OSM structured search: {len(businesses)} results")

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
            print(f"[discovery] OSM name fallback: {added} additional candidates")
        except RuntimeError as exc:
            print(f"[discovery] Name fallback search failed: {exc}")

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
                    print(f"[discovery] Website checks: {i}/{len(to_check)}")
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


def _score_business(business):
    """Score 0-10 on web presence weakness. Higher = better lead.

    A business with a genuinely strong existing site (accessible, SSL,
    mobile-responsive, recent copyright, booking) should score very low and
    sink to the bottom. No-website / broken / outdated businesses rise to the
    top. Photo/review weakness only counts as a tie-breaker when the website
    itself isn't already a clear weakness, so a strong-site business can't be
    pushed up the ranking purely by missing photos/reviews.
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

    # Photo/review weakness: only a meaningful signal when the website isn't
    # already strong. For a strong-site business these stay off so it can't be
    # lifted up the ranking by data we don't even reliably have for OSM leads.
    if not site_is_strong:
        if business.get("photos_count", 0) == 0:
            score += SCORE_NO_PHOTOS; flags.append("no_photos")
        if business.get("review_count", 0) < 10:
            score += SCORE_FEW_REVIEWS; flags.append("few_reviews")

    if site_is_strong:
        flags.append("strong_existing_site")

    business["score"]          = min(score, 10)
    business["weakness_flags"] = flags
    business["notes"]          = " - ".join(f.replace("_", " ") for f in flags) or "Minimal issues"
    return business


def save_leads(leads, output_dir="./output"):
    """Write ranked leads to {output_dir}/leads.json."""
    out  = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "leads.json"
    path.write_text(json.dumps(leads, indent=2, ensure_ascii=False))
    print(f"[discovery] Saved {len(leads)} leads -> {path}")
    return path
