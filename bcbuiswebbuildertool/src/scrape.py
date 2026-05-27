"""
Phase 2 - Business Intelligence Scraping

For each business, build a complete intelligence profile:
  1. Existing website - screenshots, text, colour palette, logo
  2. Google Maps listing - photos, reviews, attributes, Q&A
  3. Social media - Facebook, Instagram, LinkedIn (public only)
  4. Review platforms - Yelp, TripAdvisor, HomeStars, Google
  5. Competitor benchmarking - 3 competitors, homepage screenshots

Output: ./research/{business_slug}/
  profile.json, screenshots/, assets/, competitors/
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

MAX_PHOTOS = 10
MAX_REVIEWS = 20
MAX_COMPETITORS = 3


def build_profile(business: dict, output_dir: str = "./research") -> Path:
    """Entry point for Phase 2. Scrapes all sources and writes profile.json."""
    slug = _slugify(business.get("name", "unknown-business"))
    profile_dir = Path(output_dir) / slug
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "screenshots").mkdir(exist_ok=True)
    (profile_dir / "assets").mkdir(exist_ok=True)
    (profile_dir / "competitors").mkdir(exist_ok=True)

    with ThreadPoolExecutor(max_workers=5) as pool:
        tasks = {
            pool.submit(_scrape_existing_website, business, profile_dir): "website",
            pool.submit(_scrape_google_maps, business, profile_dir): "google_maps",
            pool.submit(_scrape_social_media, business, profile_dir): "social",
            pool.submit(_scrape_review_platforms, business, profile_dir): "reviews",
            pool.submit(_scrape_competitors, business, profile_dir): "competitors",
        }
        profile = {"business": business}
        for future in as_completed(tasks):
            key = tasks[future]
            try:
                profile[key] = future.result()
            except Exception as exc:
                print(f"[scrape] {key} failed: {exc} - continuing")
                profile[key] = {"error": str(exc)}

    path = profile_dir / "profile.json"
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    print(f"[scrape] Profile saved -> {path}")
    return profile_dir


def _scrape_existing_website(business, profile_dir):
    url = business.get("existing_website")
    if not url:
        return {"skipped": True, "reason": "no_website"}
    # TODO: Playwright screenshots (desktop + mobile)
    # TODO: extract text content by section
    # TODO: extract dominant colour palette
    # TODO: download logo
    # TODO: detect SSL, mobile responsive, booking form
    raise NotImplementedError("Website scraping not yet implemented")


def _scrape_google_maps(business, profile_dir):
    # TODO: Google Places Details API for photos, reviews, attributes
    # TODO: Playwright fallback for google_maps_url
    raise NotImplementedError("Google Maps scraping not yet implemented")


def _scrape_social_media(business, profile_dir):
    # TODO: Facebook Pages, Instagram, LinkedIn (public data only)
    raise NotImplementedError("Social media scraping not yet implemented")


def _scrape_review_platforms(business, profile_dir):
    # TODO: Yelp, TripAdvisor, HomeStars, Google aggregate ratings
    raise NotImplementedError("Review platform scraping not yet implemented")


def _scrape_competitors(business, profile_dir):
    # TODO: find 3 competitors, screenshot homepages, note feature gaps
    raise NotImplementedError("Competitor scraping not yet implemented")


def _slugify(name):
    return name.lower().replace(" ", "-").replace("/", "-")
