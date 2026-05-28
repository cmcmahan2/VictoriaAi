"""
Phase 1 - Business Discovery

Find BC businesses that have weak, outdated, or no web presence and are strong
candidates for a new website. Uses a tiered discovery strategy:

  Tier 1: Google Maps Places API     (requires GOOGLE_MAPS_API_KEY)
  Tier 2: Yelp Fusion API            (requires YELP_API_KEY - free at yelp.com/developers)
  Tier 3: Demo mode                  (DEMO_MODE=true - realistic fake data for UI testing)

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


def discover_businesses(
    city: str,
    business_type: str,
    radius_km: int = 15,
    max_results: int = 50,
) -> list[dict]:
    """
    Run the full Phase 1 discovery pipeline for a city + business type.
    Tries each tier in order, scoring and ranking all results.
    """
    google_key = os.getenv("GOOGLE_MAPS_API_KEY")
    yelp_key   = os.getenv("YELP_API_KEY")
    fsq_key    = os.getenv("FOURSQUARE_API_KEY")
    demo_mode  = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")

    businesses: list[dict] = []

    if google_key:
        print(f"[discovery] Tier 1 - Google Places API: {business_type} in {city}, BC")
        try:
            businesses = _discover_via_places_api(city, business_type, radius_km, max_results, google_key)
            print(f"[discovery] Google Places: {len(businesses)} results")
        except Exception as exc:
            print(f"[discovery] Google Places failed ({exc}) - trying next tier")

    if not businesses and yelp_key:
        print(f"[discovery] Tier 2 - Yelp Fusion API: {business_type} in {city}, BC")
        try:
            businesses = _discover_via_yelp(city, business_type, max_results, yelp_key)
            print(f"[discovery] Yelp: {len(businesses)} results")
        except Exception as exc:
            print(f"[discovery] Yelp API failed ({exc}) - trying next tier")

    if not businesses and fsq_key:
        print(f"[discovery] Tier 3 - Foursquare Places API: {business_type} in {city}, BC")
        try:
            businesses = _discover_via_foursquare(city, business_type, radius_km, max_results, fsq_key)
            print(f"[discovery] Foursquare: {len(businesses)} results")
        except Exception as exc:
            print(f"[discovery] Foursquare failed ({exc}) - trying next tier")

    if not businesses:
        print(f"[discovery] Tier 4 - OpenStreetMap: {business_type} in {city}, BC")
        try:
            businesses = _discover_via_openstreetmap(city, business_type, radius_km, max_results)
            print(f"[discovery] OpenStreetMap: {len(businesses)} real businesses found")
        except Exception as exc:
            print(f"[discovery] OpenStreetMap failed ({exc}) - falling back to demo")

    if not businesses:
        if demo_mode or True:
            print(f"[discovery] Demo mode - generating sample leads for {business_type} in {city}, BC")
            businesses = _demo_businesses(city, business_type)
        else:
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


def _discover_via_yelp(city, business_type, max_results, api_key):
    """
    Tier 2: Yelp Fusion API. Free tier: 500 calls/day.
    Get a free key at: https://www.yelp.com/developers/v3/manage_app
    """
    url      = "https://api.yelp.com/v3/businesses/search"
    location = f"{city}, BC, Canada"
    headers  = {"Authorization": f"Bearer {api_key}"}
    businesses = []
    offset = 0
    limit  = min(50, max_results)

    while len(businesses) < max_results:
        params = {"term": business_type, "location": location, "limit": limit, "offset": offset, "sort_by": "rating"}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("businesses", [])
        if not batch:
            break
        for b in batch:
            loc = b.get("location", {})
            address_parts = [loc.get("address1", ""), loc.get("city", ""), loc.get("state_code", "")]
            businesses.append({
                "name":             b.get("name", ""),
                "address":          ", ".join(p for p in address_parts if p),
                "phone":            b.get("display_phone", ""),
                "existing_website": None,
                "yelp_page":        b.get("url"),
                "rating":           b.get("rating"),
                "review_count":     b.get("review_count", 0),
                "photos_count":     1 if b.get("image_url") else 0,
                "category":         business_type,
                "city":             city,
                "source":           "yelp",
            })
        offset += len(batch)
        if offset >= data.get("total", 0) or len(businesses) >= max_results:
            break
        time.sleep(0.3)

    return businesses[:max_results]


def _discover_via_foursquare(city: str, business_type: str, radius_km: int, max_results: int, api_key: str) -> list[dict]:
    """
    Tier 3: Foursquare Places API v3.
    Free tier: 1000 calls/day. Sign up at foursquare.com/developer (Gmail OK).
    Add FOURSQUARE_API_KEY to .env
    """
    # Geocode city first using Nominatim
    geo_headers = {"User-Agent": "BCBuisWebBuilderTool/1.0 contact@victoriaai.ca"}
    geo = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": f"{city}, BC, Canada", "format": "json", "limit": 1},
        headers=geo_headers, timeout=10,
    ).json()
    if not geo:
        raise RuntimeError(f"Could not geocode {city}")
    lat, lon = geo[0]["lat"], geo[0]["lon"]

    url = "https://api.foursquare.com/v3/places/search"
    headers = {"Authorization": api_key, "Accept": "application/json"}
    businesses = []
    limit = min(50, max_results)

    params = {
        "query":  business_type,
        "ll":     f"{lat},{lon}",
        "radius": radius_km * 1000,
        "limit":  limit,
    }
    resp = requests.get(url, headers=headers, params=params, timeout=12)
    print(f"[discovery] Foursquare status: {resp.status_code}")
    resp.raise_for_status()
    results = resp.json().get("results", [])

    for r in results:
        loc = r.get("location", {})
        address = ", ".join(p for p in [
            loc.get("address", ""),
            loc.get("locality", city),
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


def _discover_via_openstreetmap(city: str, business_type: str, radius_km: int, max_results: int) -> list[dict]:
    """
    Tier 3: Real businesses from OpenStreetMap via Overpass API + Nominatim geocoding.
    Completely free, no API key required, returns real registered businesses.
    """
    # Step 1: geocode the city to lat/lon
    geo_headers = {"User-Agent": "BCBuisWebBuilderTool/1.0 contact@victoriaai.ca"}
    geo_resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": f"{city}, BC, Canada", "format": "json", "limit": 1},
        headers=geo_headers,
        timeout=10,
    )
    geo_resp.raise_for_status()
    geo_data = geo_resp.json()
    if not geo_data:
        raise RuntimeError(f"Could not geocode {city}, BC")
    lat = float(geo_data[0]["lat"])
    lon = float(geo_data[0]["lon"])

    # Step 2: map business_type to OSM tags
    tag_pairs = _osm_tags_for(business_type)
    radius_m  = radius_km * 1000

    tag_lines = ""
    for key, val in tag_pairs:
        tag_lines += f'  node["{key}"="{val}"](around:{radius_m},{lat},{lon});\n'
        tag_lines += f'  way["{key}"="{val}"](around:{radius_m},{lat},{lon});\n'

    query = f"[out:json][timeout:30];\n(\n{tag_lines});\nout center tags;"

    # Step 3: query Overpass
    over_resp = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        timeout=35,
    )
    over_resp.raise_for_status()
    elements = over_resp.json().get("elements", [])

    businesses = []
    for el in elements[:max_results]:
        tags   = el.get("tags", {})
        name   = tags.get("name", "").strip()
        if not name:
            continue

        # Build address from OSM addr tags
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

        businesses.append({
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
        })

    return businesses


def _osm_tags_for(business_type: str) -> list:
    """Map a plain-English business type to OpenStreetMap tag key/value pairs."""
    bt = business_type.lower()
    mapping = [
        (["plumb"],                         [("craft", "plumber")]),
        (["electr"],                        [("craft", "electrician")]),
        (["landscap", "garden", "lawn"],    [("craft", "gardener"), ("shop", "garden_centre")]),
        (["hvac", "heating", "cooling"],    [("craft", "hvac")]),
        (["roof"],                          [("craft", "roofer")]),
        (["paint"],                         [("craft", "painter")]),
        (["carpet", "floor"],               [("craft", "floorer")]),
        (["window", "glass"],               [("craft", "glaziery")]),
        (["restaurant", "dining"],          [("amenity", "restaurant")]),
        (["cafe", "coffee"],                [("amenity", "cafe")]),
        (["salon", "hair"],                 [("shop", "hairdresser")]),
        (["barber"],                        [("shop", "barber")]),
        (["nail"],                          [("shop", "nail_salon")]),
        (["spa", "massage"],                [("leisure", "spa"), ("amenity", "massage")]),
        (["dentist", "dental"],             [("amenity", "dentist")]),
        (["physio"],                        [("amenity", "physiotherapist")]),
        (["optician", "optical"],           [("shop", "optician")]),
        (["mechanic", "auto repair", "car repair"], [("shop", "car_repair")]),
        (["tire", "tyre"],                  [("shop", "tyres")]),
        (["bakery", "baker"],               [("shop", "bakery")]),
        (["butcher"],                       [("shop", "butcher")]),
        (["grocery", "grocer"],             [("shop", "supermarket"), ("shop", "convenience")]),
        (["pharmacy", "drug"],              [("amenity", "pharmacy")]),
        (["gym", "fitness"],                [("leisure", "fitness_centre")]),
        (["yoga"],                          [("leisure", "yoga")]),
        (["clean", "laundry"],              [("shop", "dry_cleaning"), ("shop", "laundry")]),
        (["accountant", "accounting"],      [("office", "accountant")]),
        (["lawyer", "legal"],               [("office", "lawyer")]),
        (["real estate", "realtor"],        [("office", "real_estate_agent")]),
        (["insurance"],                     [("office", "insurance")]),
        (["vet", "veterinar"],              [("amenity", "veterinary")]),
        (["pet", "dog groom"],              [("shop", "pet"), ("shop", "pet_grooming")]),
        (["photographer"],                  [("craft", "photographer")]),
        (["tattoo"],                        [("shop", "tattoo")]),
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
    """Score 0-10 on web presence weakness. Higher = better lead."""
    score = 0; flags = []
    health  = business.get("website_health")
    website = business.get("existing_website")
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
    if business.get("photos_count", 0) == 0:
        score += SCORE_NO_PHOTOS; flags.append("no_photos")
    if business.get("review_count", 0) < 10:
        score += SCORE_FEW_REVIEWS; flags.append("few_reviews")
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
