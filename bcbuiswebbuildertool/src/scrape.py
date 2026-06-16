"""
Phase 2 - Business Intelligence Scraping

For each business (or a single target provided directly), build a complete
intelligence profile to feed the website builder and AI audit.

Gathered in parallel where possible:
  1. Existing website - content, structure, text, meta, contact info
  2. Google Maps / Places - description, photos, reviews, attributes
  3. Social media presence - detected from website links + name search
  4. Review platform data - Yelp API if key present, else parsed from site
  5. Competitor benchmarking - top 3 competitors from discovery

Output saved to ./research/{business_slug}/:
  profile.json      - all structured data
  screenshots/      - placeholder (desktop screenshots require Playwright)
  assets/           - downloaded logo / hero images
  competitors/      - competitor summaries
"""

import json
import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

from logging_config import get_logger

log = get_logger("scrape")

MAX_PHOTOS    = 10
MAX_REVIEWS   = 20
MAX_COMPETITORS = 3

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


def build_profile(business: dict, output_dir: str = "./research") -> Path:
    slug = _slugify(business.get("name", "unknown-business"))
    profile_dir = Path(output_dir) / slug
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "screenshots").mkdir(exist_ok=True)
    (profile_dir / "assets").mkdir(exist_ok=True)
    (profile_dir / "competitors").mkdir(exist_ok=True)

    log.info(f"[Phase 2] Building intelligence profile for: {business.get('name')}")
    log.info(f"[Phase 2] Output directory: {profile_dir}")

    profile = {
        "business": business,
        "scraped_at": datetime.now().isoformat(),
        "scrape_version": "2.0",
    }

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_analyze_existing_website, business, profile_dir): "website",
            pool.submit(_fetch_google_places_details, business, profile_dir): "google_places",
            pool.submit(_detect_social_media, business, profile_dir): "social_media",
            pool.submit(_aggregate_reviews, business): "reviews",
            pool.submit(_find_competitors, business, profile_dir): "competitors",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                result = future.result()
                profile[key] = result
                log.info(f"[Phase 2] done: {key}")
            except Exception as exc:
                log.warning(f"[Phase 2] warning: {key} - {exc}")
                profile[key] = {"error": str(exc)}

    profile["summary"] = _build_summary(profile)

    path = profile_dir / "profile.json"
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"[Phase 2] Profile complete: {path}")
    return profile_dir


def extract_business_from_url(url: str) -> dict:
    """Given ONLY a website URL, fetch the page and derive a best-effort
    ``business`` dict (name, phone, city, category, socials) suitable for
    feeding ``build_profile()`` / ``build_website()``.

    Powers the dashboard's "Import an existing site" flow: an operator pastes a
    prospect's current URL and the pipeline rebuilds it better, reusing their
    real photos and details. Always returns a usable dict — on fetch failure it
    falls back to a name derived from the domain so the operator can proceed.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    business: dict = {"existing_website": url}

    try:
        resp = _SESSION.get(url, timeout=12, allow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        log.warning(f"[import] Could not fetch {url}: {exc}")
        business["name"] = _name_from_domain(url)
        business["_fetch_error"] = str(exc)
        return business

    soup    = BeautifulSoup(resp.text, "lxml")
    meta    = _extract_meta(soup, resp.url)
    contact = _extract_contact_info(soup, resp.text)
    schemas = _flatten_schema(meta.get("schema_org") or [])

    business["existing_website"] = resp.url
    business["name"] = _derive_business_name(soup, meta, schemas, resp.url)

    phones = contact.get("tel_links") or contact.get("phones") or []
    if phones:
        business["phone"] = phones[0]

    emails = contact.get("mailto_links") or contact.get("emails") or []
    if emails:
        business["email"] = emails[0]

    address, city = _derive_address_city(schemas, contact)
    if address:
        business["address"] = address
    if city:
        business["city"] = city

    category = _derive_category(schemas, meta, soup, business.get("name", ""))
    if category:
        business["category"]      = category
        business["business_type"] = category

    business["social_links"] = _extract_social_links(soup, resp.url)
    log.info(
        f"[import] Derived business from {resp.url}: name={business.get('name')!r}, "
        f"category={business.get('category')!r}, city={business.get('city')!r}"
    )
    return business


def _name_from_domain(url: str) -> str:
    """Fallback business name from the domain, e.g.
    'https://derekselectric.ca/' -> 'Derekselectric'."""
    host = urlparse(url).netloc.lower()
    host = re.sub(r"^www\.", "", host)
    label = host.split(".")[0] if host else "Imported Site"
    return label.replace("-", " ").title() or "Imported Site"


def _flatten_schema(schemas: list) -> list:
    """Flatten JSON-LD blocks (which may nest under @graph or be lists) into a
    flat list of dicts so we can scan for name/address/type."""
    out: list = []

    def _walk(node):
        if isinstance(node, dict):
            if "@graph" in node and isinstance(node["@graph"], list):
                for child in node["@graph"]:
                    _walk(child)
            out.append(node)
        elif isinstance(node, list):
            for child in node:
                _walk(child)

    for s in schemas:
        _walk(s)
    return out


_GENERIC_TITLE_WORDS = {
    "home", "welcome", "homepage", "index", "official site", "official website",
}


def _derive_business_name(soup: BeautifulSoup, meta: dict, schemas: list,
                          url: str) -> str:
    """Best-effort business name. Priority: og:site_name > schema.org name >
    cleaned <title> > first <h1> > domain."""
    og_site = soup.find("meta", attrs={"property": "og:site_name"})
    if og_site and og_site.get("content", "").strip():
        return og_site["content"].strip()[:80]

    for s in schemas:
        t = s.get("@type", "")
        types = t if isinstance(t, list) else [t]
        if any("Organization" in str(x) or "Business" in str(x) or
               "Store" in str(x) or "Restaurant" in str(x) for x in types):
            nm = s.get("name")
            if isinstance(nm, str) and nm.strip():
                return nm.strip()[:80]

    title = (meta.get("title") or "").strip()
    if title:
        # Split on common separators and pick the most "brand-like" segment:
        # the shortest non-generic piece (taglines are usually longer).
        parts = [p.strip() for p in re.split(r"\s*[|\-–—·:]\s*", title) if p.strip()]
        parts = [p for p in parts if p.lower() not in _GENERIC_TITLE_WORDS]
        if parts:
            return min(parts, key=len)[:80]
        return title[:80]

    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)[:80]

    return _name_from_domain(url)


def _derive_address_city(schemas: list, contact: dict) -> tuple:
    """Pull a street address + city from schema.org PostalAddress if present."""
    for s in schemas:
        addr = s.get("address")
        if isinstance(addr, dict):
            street   = addr.get("streetAddress") or ""
            locality = addr.get("addressLocality") or ""
            region   = addr.get("addressRegion") or ""
            full = ", ".join(p for p in (street, locality, region) if p)
            return (full or None, locality or None)
    return (None, None)


_CATEGORY_KEYWORDS = {
    "plumber":     ["plumb"],
    "electrician": ["electric"],
    "landscaper":  ["landscap", "lawn care", "garden"],
    "painter":     ["paint"],
    "roofer":      ["roof"],
    "hvac":        ["hvac", "heating", "air conditioning", "furnace"],
    "cleaner":     ["cleaning", "janitorial", "maid"],
    "handyman":    ["handyman"],
    "restaurant":  ["restaurant", "bistro", "eatery", "diner"],
    "cafe":        ["cafe", "coffee"],
    "bakery":      ["bakery", "bakeshop"],
    "dentist":     ["dental", "dentist", "orthodont"],
    "lawyer":      ["law firm", "lawyer", "attorney", "legal services"],
    "accountant":  ["accounting", "accountant", "bookkeeping", "cpa"],
    "contractor":  ["contracting", "contractor", "renovation", "construction"],
}


def _derive_category(schemas: list, meta: dict, soup: BeautifulSoup,
                     name: str) -> str:
    """Best-effort trade/category from schema.org @type, then keyword scan over
    title + headings + name. Returns '' when nothing matches."""
    for s in schemas:
        t = s.get("@type", "")
        types = t if isinstance(t, list) else [t]
        for x in types:
            xl = str(x).lower()
            for cat, words in _CATEGORY_KEYWORDS.items():
                if cat in xl or any(w.replace(" ", "") in xl for w in words):
                    return cat

    haystack = " ".join([
        meta.get("title") or "",
        meta.get("description") or "",
        meta.get("keywords") or "",
        " ".join(meta.get("h1_tags") or []),
        " ".join(meta.get("h2_tags") or []),
        name,
    ]).lower()

    for cat, words in _CATEGORY_KEYWORDS.items():
        if any(w in haystack for w in words):
            return cat
    return ""


def _analyze_existing_website(business: dict, profile_dir: Path) -> dict:
    url = business.get("existing_website")
    if not url:
        return {"present": False, "reason": "no_website_found"}

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    result: dict = {
        "url": url,
        "present": True,
        "reachable": False,
        "ssl": url.startswith("https://"),
    }

    try:
        resp = _SESSION.get(url, timeout=10, allow_redirects=True)
        result["http_status"] = resp.status_code
        result["final_url"]   = resp.url
        result["ssl"]         = resp.url.startswith("https://")
        result["reachable"]   = resp.status_code < 400

        if not result["reachable"]:
            return result

        soup = BeautifulSoup(resp.text, "lxml")

        result["meta"]           = _extract_meta(soup, resp.url)
        result["text_content"]   = _extract_text_sections(soup)
        result["contact"]        = _extract_contact_info(soup, resp.text)
        result["social_links"]   = _extract_social_links(soup, resp.url)
        result["tech_signals"]   = _detect_tech_signals(soup, resp.text, resp.headers)
        result["weaknesses"]     = _detect_site_weaknesses(soup, resp.text, resp.url)
        result["page_inventory"] = _find_internal_pages(soup, resp.url)
        result["copyright_year"] = _detect_copyright_year(resp.text)

        images = _find_prominent_images(soup, resp.url)
        result["prominent_images"] = images[:5]

        logo_path = _download_logo(soup, resp.url, profile_dir)
        result["logo_downloaded"] = str(logo_path) if logo_path else None

    except requests.exceptions.SSLError:
        result["ssl"] = False
        result["reachable"] = False
        result["error"] = "SSL certificate error"
        try:
            http_url = url.replace("https://", "http://")
            resp2 = _SESSION.get(http_url, timeout=10, allow_redirects=True)
            result["http_fallback_status"] = resp2.status_code
            result["reachable"] = resp2.status_code < 400
        except Exception:
            pass
    except requests.exceptions.ConnectionError:
        result["reachable"] = False
        result["error"] = "Connection refused / DNS failure"
    except requests.exceptions.Timeout:
        result["reachable"] = False
        result["error"] = "Request timed out"
    except Exception as exc:
        result["error"] = str(exc)

    return result


def _extract_meta(soup: BeautifulSoup, base_url: str) -> dict:
    meta: dict = {}

    title_tag = soup.find("title")
    meta["title"] = title_tag.get_text(strip=True) if title_tag else None

    for name in ("description", "keywords", "author", "robots"):
        tag = soup.find("meta", attrs={"name": name})
        meta[name] = tag.get("content", "").strip() if tag else None

    for prop in ("og:title", "og:description", "og:image", "og:type", "og:url"):
        tag = soup.find("meta", attrs={"property": prop})
        meta[prop] = tag.get("content", "").strip() if tag else None

    canonical = soup.find("link", attrs={"rel": "canonical"})
    meta["canonical"] = canonical.get("href") if canonical else None

    viewport = soup.find("meta", attrs={"name": "viewport"})
    meta["has_viewport_meta"] = viewport is not None

    schema_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
    schemas = []
    for tag in schema_tags:
        try:
            schemas.append(json.loads(tag.string or "{}"))
        except Exception:
            pass
    meta["schema_org"] = schemas

    meta["h1_tags"] = [h.get_text(strip=True) for h in soup.find_all("h1")][:5]
    meta["h2_tags"] = [h.get_text(strip=True) for h in soup.find_all("h2")][:10]

    return meta


def _extract_text_sections(soup: BeautifulSoup) -> dict:
    sections: dict = {}

    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()

    keywords = {
        "about":    ["about", "our story", "who we are", "about us"],
        "services": ["services", "what we do", "our services", "offerings"],
        "contact":  ["contact", "reach us", "get in touch", "location"],
        "hours":    ["hours", "open", "schedule", "availability"],
    }

    all_headings = soup.find_all(["h1", "h2", "h3", "h4"])
    for heading in all_headings:
        text = heading.get_text(strip=True).lower()
        for section, terms in keywords.items():
            if any(t in text for t in terms):
                content_parts = []
                for sib in heading.find_next_siblings():
                    if sib.name in ("h1", "h2", "h3", "h4"):
                        break
                    content_parts.append(sib.get_text(" ", strip=True))
                sections[section] = " ".join(content_parts)[:1000]
                break

    body = soup.find("body")
    if body:
        sections["full_text_preview"] = body.get_text(" ", strip=True)[:3000]

    return sections


def _extract_contact_info(soup: BeautifulSoup, raw_html: str) -> dict:
    contact: dict = {}

    phone_pattern = re.compile(
        r"(?:\+?1[-.\s]?)?\(?([2-9]\d{2})\)?[-.\s]?([2-9]\d{2})[-.\s]?(\d{4})"
    )
    phones = phone_pattern.findall(raw_html)
    if phones:
        contact["phones"] = list(set(
            f"({a}) {b}-{c}" for a, b, c in phones
        ))[:3]

    email_pattern = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    )
    emails = email_pattern.findall(raw_html)
    if emails:
        contact["emails"] = [e for e in set(emails)
                             if not any(x in e.lower() for x in
                                        ["example.", "yourname", "youremail",
                                         "domain.", "email.com"])][:3]

    postal_pattern = re.compile(r"[VBCEKX]\d[A-Z]\s?\d[A-Z]\d", re.IGNORECASE)
    postal = postal_pattern.findall(raw_html)
    if postal:
        contact["postal_codes"] = list(set(postal))[:2]

    mailto_links = soup.find_all("a", href=re.compile(r"^mailto:", re.I))
    if mailto_links:
        contact["mailto_links"] = [
            a["href"].replace("mailto:", "").split("?")[0]
            for a in mailto_links
        ][:3]

    tel_links = soup.find_all("a", href=re.compile(r"^tel:", re.I))
    if tel_links:
        contact["tel_links"] = [a["href"].replace("tel:", "") for a in tel_links][:3]

    return contact


def _extract_social_links(soup: BeautifulSoup, base_url: str) -> dict:
    platforms = {
        "facebook":  r"facebook\.com/",
        "instagram": r"instagram\.com/",
        "twitter":   r"twitter\.com/|x\.com/",
        "linkedin":  r"linkedin\.com/",
        "youtube":   r"youtube\.com/",
        "tiktok":    r"tiktok\.com/",
        "pinterest": r"pinterest\.com/",
    }
    found: dict = {}
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        for platform, pattern in platforms.items():
            if platform not in found and re.search(pattern, href, re.I):
                found[platform] = href
    return found


def _detect_tech_signals(soup: BeautifulSoup, raw_html: str, headers: dict) -> dict:
    signals: dict = {}

    checks = {
        "wordpress":        ["wp-content", "wp-includes", "/wp-json/"],
        "wix":              ["static.wixstatic.com", "wix.com"],
        "squarespace":      ["static.squarespace.com", "squarespace.com"],
        "shopify":          ["cdn.shopify.com", "myshopify.com"],
        "weebly":           ["weebly.com", "editmysite.com"],
        "godaddy":          ["godaddy", "secureserver.net"],
        "google_analytics": ["gtag(", "UA-", "G-", "google-analytics.com"],
        "facebook_pixel":   ["fbq(", "connect.facebook.net"],
        "jquery":           ["jquery"],
        "bootstrap":        ["bootstrap.min.css", "bootstrap.css"],
        "tailwind":         ["tailwindcss", "tailwind.css"],
    }

    for tech, patterns in checks.items():
        if any(p.lower() in raw_html.lower() for p in patterns):
            signals[tech] = True

    server = headers.get("Server", "")
    if server:
        signals["server"] = server

    powered_by = headers.get("X-Powered-By", "")
    if powered_by:
        signals["x_powered_by"] = powered_by

    return signals


def _detect_site_weaknesses(soup: BeautifulSoup, raw_html: str, url: str) -> list:
    weaknesses = []

    if not soup.find("meta", attrs={"name": "viewport"}):
        weaknesses.append("no_viewport_meta")

    if not soup.find("meta", attrs={"name": "description"}):
        weaknesses.append("no_meta_description")

    if not soup.find("h1"):
        weaknesses.append("no_h1_tag")

    if not soup.find("script", attrs={"type": "application/ld+json"}):
        weaknesses.append("no_schema_markup")

    if not url.startswith("https://"):
        weaknesses.append("no_ssl")

    forms = soup.find_all("form")
    has_contact_form = any(
        re.search(r"contact|message|enquir|booking|appointment|quote|email",
                  str(f), re.I)
        for f in forms
    )
    if not has_contact_form:
        weaknesses.append("no_contact_form")

    images = soup.find_all("img")
    missing_alt = [img for img in images if not img.get("alt", "").strip()]
    if images and len(missing_alt) / len(images) > 0.5:
        weaknesses.append("poor_image_alt_text")

    inline_styles = soup.find_all(style=True)
    if len(inline_styles) > 20:
        weaknesses.append("excessive_inline_styles")

    if not _extract_social_links(soup, url):
        weaknesses.append("no_social_media_links")

    year = _detect_copyright_year(raw_html)
    if year and int(year) < datetime.now().year - 1:
        weaknesses.append(f"outdated_copyright_{year}")

    return weaknesses


def _find_internal_pages(soup: BeautifulSoup, base_url: str) -> list:
    parsed_base = urlparse(base_url)
    pages = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc == parsed_base.netloc:
            clean = parsed.scheme + "://" + parsed.netloc + parsed.path.rstrip("/")
            pages.add(clean)
    return sorted(pages)[:20]


def _detect_copyright_year(html: str) -> Optional[str]:
    match = re.search(r"[Cc]opyright\s*(20\d{2})", html)
    if match:
        return match.group(1)
    return None


def _find_prominent_images(soup: BeautifulSoup, base_url: str) -> list:
    images = []
    for img in soup.find_all("img", src=True):
        src = urljoin(base_url, img["src"])
        alt = img.get("alt", "")
        width  = img.get("width", "")
        height = img.get("height", "")
        try:
            if int(width) < 100 or int(height) < 100:
                continue
        except (ValueError, TypeError):
            pass
        images.append({"src": src, "alt": alt})
    return images


def _download_logo(soup: BeautifulSoup, base_url: str, profile_dir: Path) -> Optional[Path]:
    header = soup.find(["header", "nav"]) or soup
    candidates = []

    for img in header.find_all("img", src=True):
        src = img.get("src", "")
        alt = img.get("alt", "").lower()
        cls = " ".join(img.get("class", [])).lower()
        if any(k in src.lower() + alt + cls for k in ["logo", "brand", "header"]):
            candidates.append(urljoin(base_url, src))

    if not candidates:
        return None

    for src_url in candidates[:2]:
        try:
            r = _SESSION.get(src_url, timeout=8, stream=True)
            if r.status_code == 200:
                ct = r.headers.get("Content-Type", "")
                ext = ".png" if "png" in ct else ".jpg" if "jpeg" in ct else ".svg" if "svg" in ct else ".img"
                dest = profile_dir / "assets" / ("logo" + ext)
                dest.write_bytes(r.content)
                return dest
        except Exception:
            continue
    return None


def _fetch_google_places_details(business: dict, profile_dir: Path) -> dict:
    api_key  = os.getenv("GOOGLE_MAPS_API_KEY")
    place_id = business.get("place_id")
    maps_url = business.get("google_maps_url")

    result: dict = {"source": None, "place_id": place_id}

    if api_key and place_id:
        result.update(_places_api_details(api_key, place_id, profile_dir))
        result["source"] = "google_places_api"
        return result

    result["source"]        = "phase1_data"
    result["name"]          = business.get("name")
    result["address"]       = business.get("address")
    result["phone"]         = business.get("phone")
    result["rating"]        = business.get("rating")
    result["review_count"]  = business.get("review_count")
    result["categories"]    = business.get("categories", [])
    result["google_maps_url"] = maps_url
    result["note"] = (
        "Add GOOGLE_MAPS_API_KEY to .env for full Places data "
        "(opening hours, photos, reviews, Q&A, attributes)"
    )
    return result


def _places_api_details(api_key: str, place_id: str, profile_dir: Path) -> dict:
    fields = ",".join([
        "name", "formatted_address", "formatted_phone_number",
        "website", "rating", "user_ratings_total", "opening_hours",
        "photos", "reviews", "editorial_summary", "types",
        "business_status", "price_level", "url", "place_id",
    ])
    params = {
        "place_id": place_id,
        "fields":   fields,
        "key":      api_key,
        "language": "en",
    }
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params=params, timeout=10
        )
        data = resp.json()
        if data.get("status") != "OK":
            return {"error": "Places API: " + str(data.get("status"))}

        place = data.get("result", {})

        # Build photo URLs using the Places Photo API (maxwidth=800) and also
        # attempt to download local copies. Both the public URL and local path
        # are stored so build.py can use the URL directly without serving files.
        photos_urls = []
        photos_downloaded = []
        for photo_ref in place.get("photos", [])[:MAX_PHOTOS]:
            ref = photo_ref.get("photo_reference")
            if not ref:
                continue
            photo_url = (
                "https://maps.googleapis.com/maps/api/place/photo"
                "?maxwidth=800"
                "&photo_reference=" + str(ref) +
                "&key=" + api_key
            )
            photos_urls.append(photo_url)
            dest = profile_dir / "assets" / ("gmb_photo_" + str(len(photos_downloaded)+1) + ".jpg")
            try:
                pr = requests.get(photo_url, timeout=15, stream=True)
                if pr.status_code == 200:
                    dest.write_bytes(pr.content)
                    photos_downloaded.append(str(dest))
            except Exception:
                pass

        # Store up to 5 reviews in the shape expected by build.py:
        # {author_name, rating, text, relative_time_description}
        # build.py also normalises using _normalize_review which reads
        # "author" or "name" and "time" — we store both keys for compat.
        reviews = []
        for rv in place.get("reviews", [])[:5]:
            reviews.append({
                "author_name":              rv.get("author_name"),
                "author":                   rv.get("author_name"),
                "rating":                   rv.get("rating"),
                "text":                     rv.get("text", "")[:500],
                "relative_time_description": rv.get("relative_time_description"),
                "time":                     rv.get("relative_time_description"),
            })

        hours = place.get("opening_hours", {}).get("weekday_text", [])

        return {
            "name":               place.get("name"),
            "address":            place.get("formatted_address"),
            "phone":              place.get("formatted_phone_number"),
            "website":            place.get("website"),
            "rating":             place.get("rating"),
            "review_count":       place.get("user_ratings_total"),
            "opening_hours":      hours,
            "types":              place.get("types", []),
            "price_level":        place.get("price_level"),
            "editorial_summary":  place.get("editorial_summary", {}).get("overview"),
            "business_status":    place.get("business_status"),
            "google_maps_url":    place.get("url"),
            "place_id":           place.get("place_id") or place_id,
            # Public Google Places photo URLs (up to 5) — used directly in HTML
            "photos":             photos_urls[:5],
            # Local downloaded copies (may be fewer if downloads failed)
            "photos_downloaded":  photos_downloaded,
            # Top 5 real reviews from Google (pre-sorted by relevance)
            "reviews":            reviews,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _detect_social_media(business: dict, profile_dir: Path) -> dict:
    result: dict = {}
    website_url = business.get("existing_website")
    name        = business.get("name", "")

    if website_url:
        try:
            resp = _SESSION.get(website_url, timeout=8, allow_redirects=True)
            if resp.status_code < 400:
                soup = BeautifulSoup(resp.text, "lxml")
                links = _extract_social_links(soup, website_url)
                for platform, url in links.items():
                    result[platform] = {"found": True, "url": url, "source": "website_link"}
        except Exception:
            pass

    name_slug = re.sub(r"[^a-z0-9]", "", name.lower())

    guesses = {
        "facebook":  "https://www.facebook.com/" + name_slug,
        "instagram": "https://www.instagram.com/" + name_slug + "/",
        "linkedin":  "https://www.linkedin.com/company/" + name_slug,
    }

    for platform, guess_url in guesses.items():
        if platform not in result:
            result[platform] = {
                "found": False,
                "guessed_url": guess_url,
                "note": "Unverified - check manually",
            }

    return result


def _aggregate_reviews(business: dict) -> dict:
    yelp_key = os.getenv("YELP_API_KEY")
    result: dict = {
        "aggregate_rating": business.get("rating"),
        "total_reviews":    business.get("review_count", 0),
        "platforms":        {},
    }

    if yelp_key and business.get("name") and business.get("city"):
        yelp_data = _fetch_yelp_reviews(yelp_key, business)
        if yelp_data:
            result["platforms"]["yelp"] = yelp_data

    if business.get("rating"):
        result["platforms"]["google"] = {
            "rating":       business.get("rating"),
            "review_count": business.get("review_count", 0),
            "note":         "Add GOOGLE_MAPS_API_KEY for full review text",
        }

    total = result.get("total_reviews", 0)
    result["low_review_signal"] = total < 10
    return result


def _fetch_yelp_reviews(api_key: str, business: dict) -> Optional[dict]:
    try:
        headers = {"Authorization": "Bearer " + api_key}
        search_params = {
            "term":     business.get("name"),
            "location": business.get("city", "") + ", BC, Canada",
            "limit":    1,
        }
        r = requests.get(
            "https://api.yelp.com/v3/businesses/search",
            headers=headers, params=search_params, timeout=10
        )
        if r.status_code != 200:
            return None
        businesses = r.json().get("businesses", [])
        if not businesses:
            return None
        biz = businesses[0]
        return {
            "yelp_id":      biz["id"],
            "name":         biz.get("name"),
            "rating":       biz.get("rating"),
            "review_count": biz.get("review_count"),
            "url":          biz.get("url"),
            "categories":   [c["title"] for c in biz.get("categories", [])],
            "phone":        biz.get("phone"),
            "is_closed":    biz.get("is_closed", False),
        }
    except Exception:
        return None


def _find_competitors(business: dict, profile_dir: Path) -> list:
    from discovery import discover_businesses

    city          = business.get("city", "Victoria")
    business_type = business.get("business_type") or (business.get("categories") or [""])[0]
    own_name      = business.get("name", "").lower()

    log.info("[Phase 2] Finding competitors: " + str(business_type) + " in " + str(city) + "...")

    try:
        leads = discover_businesses(city, business_type, radius_km=10, max_results=10)
    except Exception as exc:
        return [{"error": "Discovery failed: " + str(exc)}]

    competitors = [
        b for b in leads
        if b.get("name", "").lower() != own_name
    ][:MAX_COMPETITORS]

    results = []
    for comp in competitors:
        comp_result = {
            "name":             comp.get("name"),
            "address":         comp.get("address"),
            "existing_website": comp.get("existing_website"),
            "rating":          comp.get("rating"),
            "review_count":    comp.get("review_count"),
            "weakness_score":  comp.get("weakness_score", 0),
        }

        comp_website = comp.get("existing_website")
        if comp_website:
            try:
                if not comp_website.startswith("http"):
                    comp_website = "https://" + comp_website
                r = _SESSION.get(comp_website, timeout=8, allow_redirects=True)
                if r.status_code < 400:
                    soup = BeautifulSoup(r.text, "lxml")
                    comp_result["site_features"] = {
                        "has_ssl":          comp_website.startswith("https://"),
                        "has_viewport":     bool(soup.find("meta", attrs={"name": "viewport"})),
                        "has_schema":       bool(soup.find("script", attrs={"type": "application/ld+json"})),
                        "has_contact_form": bool(re.search(r"contact|booking|appointment|quote", str(soup.find_all("form")), re.I)),
                        "social_links":     list(_extract_social_links(soup, comp_website).keys()),
                        "page_count":       len(_find_internal_pages(soup, comp_website)),
                    }
            except Exception as exc:
                comp_result["site_check_error"] = str(exc)

        results.append(comp_result)

    target_site = business.get("existing_website")
    if not target_site:
        for c in results:
            c["gap_notes"] = ["Target has no website - competitor ahead on all digital metrics"]
    else:
        for c in results:
            gaps = []
            cf = c.get("site_features", {})
            if cf.get("has_ssl") and not business.get("has_ssl"):
                gaps.append("Competitor has SSL; target does not")
            if cf.get("has_viewport") and business.get("weakness_flags", {}).get("not_mobile"):
                gaps.append("Competitor is mobile-optimised; target is not")
            if cf.get("has_contact_form") and business.get("weakness_flags", {}).get("no_booking"):
                gaps.append("Competitor has booking form; target does not")
            c["gap_notes"] = gaps or ["No significant gap detected on quick scan"]

    return results


def _build_summary(profile: dict) -> dict:
    business = profile.get("business", {})
    website  = profile.get("website", {})
    reviews  = profile.get("reviews", {})
    social   = profile.get("social_media", {})
    comps    = profile.get("competitors", [])

    active_social = sum(
        1 for v in social.values()
        if isinstance(v, dict) and v.get("found")
    )

    all_weaknesses = list(website.get("weaknesses", []))

    if reviews.get("low_review_signal"):
        all_weaknesses.append("low_review_count")
    if not reviews.get("platforms"):
        all_weaknesses.append("no_review_platform_presence")
    if active_social == 0:
        all_weaknesses.append("no_active_social_media")
    elif active_social < 2:
        all_weaknesses.append("limited_social_media_presence")

    score = min(10, len(all_weaknesses))

    comp_avg_score = 0
    if comps and isinstance(comps, list):
        scores = [c.get("weakness_score", 0) for c in comps if isinstance(c, dict)]
        comp_avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "business_name":           business.get("name"),
        "city":                    business.get("city"),
        "has_website":             website.get("present", False),
        "website_reachable":       website.get("reachable", False),
        "weaknesses":              all_weaknesses,
        "weakness_count":          len(all_weaknesses),
        "opportunity_score":       score,
        "active_social_platforms": active_social,
        "review_rating":           reviews.get("aggregate_rating"),
        "review_count":            reviews.get("total_reviews", 0),
        "competitor_count":        len(comps) if isinstance(comps, list) else 0,
        "competitor_avg_score":    comp_avg_score,
        "ready_for_phase3":        True,
        "scraped_at":              datetime.now().isoformat(),
    }


def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:60]
