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

    if not businesses:
        if demo_mode or (not google_key and not yelp_key):
            print(f"[discovery] Demo mode - generating sample leads for {business_type} in {city}, BC")
            print("[discovery] (Set GOOGLE_MAPS_API_KEY or YELP_API_KEY in .env for real data)")
            businesses = _demo_businesses(city, business_type)
        else:
            print("[discovery] No API keys configured and demo mode is off - no results")
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
