"""
Phase 3 - Website Generation

Build a production-ready website. Stack chosen by business type:
  Simple service (plumber, landscaper) -> Static HTML/CSS/JS
  Restaurant / cafe                    -> Static HTML
  Professional services (dental, legal)-> Next.js + Tailwind
  Retail                               -> Next.js + Snipcart
  Multi-location / franchise           -> Next.js + CMS

Required pages: Home, Services, About, Contact, Reviews
SEO: JSON-LD schema, sitemap.xml, robots.txt, OG tags, GA4 placeholder
"""

import json
from pathlib import Path
from typing import Literal

StackType = Literal["static", "nextjs", "nextjs-shopify", "nextjs-cms"]

STACK_BY_CATEGORY = {
    "plumber": "static", "electrician": "static", "painter": "static",
    "landscaper": "static", "handyman": "static", "hvac": "static",
    "cleaner": "static", "restaurant": "static", "cafe": "static",
    "dental": "nextjs", "dentist": "nextjs", "lawyer": "nextjs",
    "accounting": "nextjs", "accountant": "nextjs",
    "retail": "nextjs-shopify", "franchise": "nextjs-cms",
}


def build_website(profile_dir: str, output_dir: str = "./output") -> Path:
    """Entry point for Phase 3. Reads scraped profile and generates site."""
    profile_path = Path(profile_dir) / "profile.json"
    profile  = json.loads(profile_path.read_text())
    business = profile["business"]
    slug     = _slugify(business.get("name", "unknown-business"))
    site_dir = Path(output_dir) / slug
    site_dir.mkdir(parents=True, exist_ok=True)
    stack = STACK_BY_CATEGORY.get(business.get("category", "").lower(), "static")
    print(f"[build] Stack: {stack} for {business.get('name')}")
    if stack == "static":
        _build_static_site(business, profile, site_dir)
    else:
        _build_nextjs_site(business, profile, site_dir, stack)
    _write_sitemap(business, site_dir)
    _write_robots(site_dir)
    _write_readme(business, site_dir, stack)
    print(f"[build] Site built -> {site_dir}")
    return site_dir


def _build_static_site(business, profile, site_dir):
    (site_dir / "css").mkdir(exist_ok=True)
    (site_dir / "js").mkdir(exist_ok=True)
    (site_dir / "images").mkdir(exist_ok=True)
    # TODO: generate index.html, services.html, about.html, contact.html, reviews.html
    # TODO: generate css/style.css (mobile-first, industry colour palette)
    # TODO: generate js/main.js (nav toggle, form handling)
    # TODO: copy + optimise images from research/assets/
    # TODO: embed GA4 placeholder + OG tags in every page
    raise NotImplementedError("Static site generation not yet implemented")


def _build_nextjs_site(business, profile, site_dir, stack):
    # TODO: scaffold Next.js App Router + Tailwind
    # TODO: generate page components: Home, Services, About, Contact, Reviews
    # TODO: add Snipcart if nextjs-shopify, Sanity if nextjs-cms
    raise NotImplementedError("Next.js site generation not yet implemented")


def _write_sitemap(business, site_dir):
    # TODO: enumerate pages, write sitemap.xml with placeholder base URL
    raise NotImplementedError("Sitemap not yet implemented")


def _write_robots(site_dir):
    # TODO: write permissive robots.txt
    raise NotImplementedError("robots.txt not yet implemented")


def _write_readme(business, site_dir, stack):
    # TODO: write deployment README for the built site
    raise NotImplementedError("Site README not yet implemented")


def _slugify(name):
    return name.lower().replace(" ", "-").replace("/", "-")
