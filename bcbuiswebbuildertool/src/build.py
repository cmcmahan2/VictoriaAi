"""
Phase 3 - Website Generation

Builds a complete, production-ready static website for the business.
Uses Claude API to generate real copy from the Phase 2 profile, then
renders it into clean HTML/CSS/JS files ready for Netlify deploy.

Pages generated:
  index.html, services.html, about.html, contact.html, reviews.html

SEO included:
  JSON-LD LocalBusiness schema, sitemap.xml, robots.txt,
  Open Graph tags, meta description, GA4 placeholder.

Output: ./output/{business_slug}/
"""

import json
import os
import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv

load_dotenv()

StackType = Literal["static", "nextjs", "nextjs-shopify", "nextjs-cms"]

STACK_BY_CATEGORY: dict[str, StackType] = {
    "plumber": "static", "plumbing": "static",
    "electrician": "static", "electrical": "static",
    "painter": "static", "painting": "static",
    "landscaper": "static", "landscaping": "static",
    "handyman": "static", "cleaner": "static", "cleaning": "static",
    "hvac": "static", "roofing": "static", "roofer": "static",
    "restaurant": "static", "cafe": "static", "bakery": "static",
    "dental": "nextjs", "dentist": "nextjs",
    "lawyer": "nextjs", "legal": "nextjs",
    "accounting": "nextjs", "accountant": "nextjs",
    "retail": "nextjs-shopify",
    "franchise": "nextjs-cms",
}


# ── Visual themes (trade-specific look & feel) ─────────────────────────────────
#
# Each theme overrides the CSS :root palette + the hero treatment + display
# font, so an electrician's site does not look identical to a landscaper's.
# Every page inherits the palette automatically through the CSS variables.

THEMES: dict[str, dict] = {
    # Default: cool, modern, dark "tech" look. Good for trades / service pros.
    "modern": {
        "name": "modern",
        "display_font": "'Space Grotesk', var(--font)",
        "radius": "16px",
        "palette": {
            "--green": "#1fb574", "--green2": "#169a61",
            "--navy": "#1a3a5c", "--dark": "#0a1622", "--dark2": "#0f2236",
            "--light": "#f5f8fb", "--muted": "#64809e",
            "--text": "#16232f", "--border": "#e3eaf2",
            "--on-accent": "#ffffff",
        },
        "hero_overlay": "linear-gradient(135deg, rgba(15,30,48,0.86) 0%, rgba(26,58,92,0.86) 100%)",
        "css": "",
    },
    # Fresh / organic: natural greens, elegant serif headings, photo-forward
    # hero, Before/After slider. Template structure inspired by Blossom
    # Vancouver. Built for landscapers, gardeners, nurseries.
    "fresh": {
        "name": "fresh",
        "display_font": "'Fraunces', Georgia, serif",
        "radius": "22px",
        "palette": {
            "--green": "#3a9d5d", "--green2": "#2c7d47",
            "--navy": "#1f3d2a", "--dark": "#11271a", "--dark2": "#16331f",
            "--light": "#f2f7ee", "--muted": "#5e7567",
            "--text": "#1b2a20", "--border": "#dde7d8",
            "--on-accent": "#ffffff",
        },
        # Lighter overlay so the greenery photography shows through.
        "hero_overlay": "linear-gradient(180deg, rgba(17,39,26,0.38) 0%, rgba(17,39,26,0.72) 100%)",
        "css": (
            ".theme-fresh .hero::after{display:none}"
            ".theme-fresh .hero::before{background:"
            "radial-gradient(520px 380px at 15% 20%, rgba(58,157,93,0.28), transparent 70%),"
            "radial-gradient(520px 380px at 85% 30%, rgba(120,175,90,0.20), transparent 70%);}"
            ".theme-fresh .page-hero::after{background:radial-gradient(420px 260px at 80% 0%, rgba(58,157,93,0.22), transparent 65%);}"
            # Before/After slider component styles
            ".ba-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:2rem;margin-top:2.5rem}"
            ".ba-wrap{position:relative;overflow:hidden;border-radius:var(--radius);cursor:col-resize;touch-action:none;user-select:none;box-shadow:var(--shadow-lg)}"
            ".ba-wrap>img{width:100%;height:340px;object-fit:cover;display:block}"
            ".ba-after{position:absolute;top:0;left:0;bottom:0;overflow:hidden;width:50%}"
            ".ba-after img{position:absolute;top:0;left:0;height:100%;max-width:none;object-fit:cover}"
            ".ba-handle{position:absolute;top:0;bottom:0;left:50%;transform:translateX(-50%);width:4px;background:#fff;pointer-events:none}"
            ".ba-btn{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:40px;height:40px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;font-size:1.1rem;box-shadow:0 2px 12px rgba(0,0,0,0.25)}"
            ".ba-label{position:absolute;bottom:1rem;padding:0.3rem 0.75rem;border-radius:99px;font-size:0.78rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;color:#fff;background:rgba(0,0,0,0.42);backdrop-filter:blur(4px)}"
            ".ba-label-before{left:1rem}"
            ".ba-label-after{right:1rem}"
            "@media(max-width:560px){.ba-wrap>img{height:240px}}"
        ),
    },
    # Warm / appetising: terracotta + deep brown, serif headings. For food.
    "warm": {
        "name": "warm",
        "display_font": "'Fraunces', Georgia, serif",
        "radius": "18px",
        "palette": {
            "--green": "#d9763c", "--green2": "#b85c28",
            "--navy": "#3a2418", "--dark": "#1c120c", "--dark2": "#261810",
            "--light": "#faf5ef", "--muted": "#8a7565",
            "--text": "#2a1d14", "--border": "#ece2d6",
            "--on-accent": "#ffffff",
        },
        "hero_overlay": "linear-gradient(180deg, rgba(28,18,12,0.42) 0%, rgba(28,18,12,0.74) 100%)",
        "css": (
            ".theme-warm .hero::after{display:none}"
            ".theme-warm .hero::before{background:"
            "radial-gradient(520px 380px at 15% 20%, rgba(217,118,60,0.26), transparent 70%),"
            "radial-gradient(520px 380px at 85% 30%, rgba(180,92,40,0.18), transparent 70%);}"
            ".theme-warm .page-hero::after{background:radial-gradient(420px 260px at 80% 0%, rgba(217,118,60,0.22), transparent 65%);}"
        ),
    },
    # Coastal: airy Pacific blue. For pools, marine, cleaning, spas.
    "coastal": {
        "name": "coastal",
        "display_font": "'Poppins', system-ui, sans-serif",
        "radius": "18px",
        "palette": {
            "--green": "#2596be", "--green2": "#1b7a9e",
            "--navy": "#14425a", "--dark": "#0c2c3d", "--dark2": "#103a4f",
            "--light": "#f3f8fa", "--muted": "#5d7d8a",
            "--text": "#16323f", "--border": "#d9e8ee",
            "--on-accent": "#ffffff",
        },
        "hero_overlay": "linear-gradient(180deg, rgba(12,44,61,0.55) 0%, rgba(12,44,61,0.82) 100%)",
        "css": (
            ".theme-coastal .hero::after{display:none}"
            ".theme-coastal .hero::before{background:"
            "radial-gradient(520px 380px at 15% 20%, rgba(37,150,190,0.30), transparent 70%),"
            "radial-gradient(520px 380px at 85% 30%, rgba(27,122,158,0.22), transparent 70%);}"
            ".theme-coastal .page-hero::after{background:radial-gradient(420px 260px at 80% 0%, rgba(37,150,190,0.22), transparent 65%);}"
        ),
    },
    # Slate: industrial charcoal + amber. For mechanics, welding, construction.
    "slate": {
        "name": "slate",
        "display_font": "'Barlow Condensed', system-ui, sans-serif",
        "radius": "6px",
        "palette": {
            "--green": "#e8920c", "--green2": "#c8780a",
            "--navy": "#2a2d31", "--dark": "#16181b", "--dark2": "#202327",
            "--light": "#f4f4f5", "--muted": "#71757a",
            "--text": "#1c1e21", "--border": "#dcdee0",
            "--on-accent": "#1c1e21",
        },
        "hero_overlay": "linear-gradient(135deg, rgba(22,24,27,0.84) 0%, rgba(42,45,49,0.84) 100%)",
        "css": (
            ".theme-slate .hero::after{display:none}"
            ".theme-slate .hero::before{background:"
            "radial-gradient(520px 380px at 15% 20%, rgba(232,146,12,0.24), transparent 70%),"
            "radial-gradient(520px 380px at 85% 30%, rgba(200,120,10,0.18), transparent 70%);}"
            ".theme-slate .page-hero::after{background:radial-gradient(420px 260px at 80% 0%, rgba(232,146,12,0.20), transparent 65%);}"
        ),
    },
    # Luxe: elegant black + gold. For salons, med spas, jewellery, luxury.
    "luxe": {
        "name": "luxe",
        "display_font": "'Playfair Display', Georgia, serif",
        "radius": "4px",
        "palette": {
            "--green": "#c9a44c", "--green2": "#a8863a",
            "--navy": "#1a1a1a", "--dark": "#0a0a0a", "--dark2": "#141414",
            "--light": "#f7f5f0", "--muted": "#8a8478",
            "--text": "#1a1813", "--border": "#e6e1d6",
            "--on-accent": "#1a1813",
        },
        "hero_overlay": "linear-gradient(180deg, rgba(10,10,10,0.55) 0%, rgba(10,10,10,0.86) 100%)",
        "css": (
            ".theme-luxe .hero::after{display:none}"
            ".theme-luxe .hero::before{background:"
            "radial-gradient(520px 380px at 15% 20%, rgba(201,164,76,0.28), transparent 70%),"
            "radial-gradient(520px 380px at 85% 30%, rgba(168,134,58,0.20), transparent 70%);}"
            ".theme-luxe .page-hero::after{background:radial-gradient(420px 260px at 80% 0%, rgba(201,164,76,0.22), transparent 65%);}"
        ),
    },
    # Bloom: soft rose + cream. For florists, nail, beauty, boutiques.
    "bloom": {
        "name": "bloom",
        "display_font": "'Cormorant Garamond', Georgia, serif",
        "radius": "24px",
        "palette": {
            "--green": "#d96a8f", "--green2": "#c2517a",
            "--navy": "#5e2740", "--dark": "#3d182a", "--dark2": "#4a1f33",
            "--light": "#fdf4f7", "--muted": "#9c7585",
            "--text": "#3a2230", "--border": "#f3dde5",
            "--on-accent": "#ffffff",
        },
        "hero_overlay": "linear-gradient(180deg, rgba(61,24,42,0.48) 0%, rgba(61,24,42,0.80) 100%)",
        "css": (
            ".theme-bloom .hero::after{display:none}"
            ".theme-bloom .hero::before{background:"
            "radial-gradient(520px 380px at 15% 20%, rgba(217,106,143,0.28), transparent 70%),"
            "radial-gradient(520px 380px at 85% 30%, rgba(194,81,122,0.20), transparent 70%);}"
            ".theme-bloom .page-hero::after{background:radial-gradient(420px 260px at 80% 0%, rgba(217,106,143,0.22), transparent 65%);}"
        ),
    },
    # Trust: corporate blue + white. For lawyers, accountants, dentists, clinics.
    "trust": {
        "name": "trust",
        "display_font": "'Inter', system-ui, sans-serif",
        "radius": "10px",
        "palette": {
            "--green": "#2563c4", "--green2": "#1d4fa3",
            "--navy": "#16335e", "--dark": "#0d2244", "--dark2": "#11294f",
            "--light": "#f4f7fb", "--muted": "#5e7390",
            "--text": "#16243a", "--border": "#dce4ef",
            "--on-accent": "#ffffff",
        },
        "hero_overlay": "linear-gradient(135deg, rgba(13,34,68,0.86) 0%, rgba(22,51,94,0.86) 100%)",
        "css": (
            ".theme-trust h1, .theme-trust h2, .theme-trust h3, .theme-trust .nav-logo{letter-spacing:-0.03em;}"
            ".theme-trust .hero::after{display:none}"
            ".theme-trust .hero::before{background:"
            "radial-gradient(520px 380px at 15% 20%, rgba(37,99,196,0.28), transparent 70%),"
            "radial-gradient(520px 380px at 85% 30%, rgba(29,79,163,0.20), transparent 70%);}"
            ".theme-trust .page-hero::after{background:radial-gradient(420px 260px at 80% 0%, rgba(37,99,196,0.22), transparent 65%);}"
        ),
    },
    # Bold: high-contrast black/white + electric yellow. For gyms, barbers.
    "bold": {
        "name": "bold",
        "display_font": "'Anton', system-ui, sans-serif",
        "radius": "0px",
        "palette": {
            "--green": "#ffd400", "--green2": "#e6c000",
            "--navy": "#1a1a1a", "--dark": "#000000", "--dark2": "#111111",
            "--light": "#f5f5f5", "--muted": "#6b6b6b",
            "--text": "#111111", "--border": "#e0e0e0",
            "--on-accent": "#111111",
        },
        "hero_overlay": "linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.85) 100%)",
        "css": (
            ".theme-bold h1, .theme-bold h2, .theme-bold h3{text-transform:uppercase;letter-spacing:0.01em;}"
            ".theme-bold .hero::after{display:none}"
            ".theme-bold .hero::before{background:"
            "radial-gradient(520px 380px at 15% 20%, rgba(255,212,0,0.26), transparent 70%),"
            "radial-gradient(520px 380px at 85% 30%, rgba(230,192,0,0.18), transparent 70%);}"
            ".theme-bold .page-hero::after{background:radial-gradient(420px 260px at 80% 0%, rgba(255,212,0,0.20), transparent 65%);}"
        ),
    },
    # Earth: natural olive/clay. For yoga, wellness, organic, artisan, craft.
    "earth": {
        "name": "earth",
        "display_font": "'Spectral', Georgia, serif",
        "radius": "14px",
        "palette": {
            "--green": "#97864e", "--green2": "#7c6e3d",
            "--navy": "#3a3528", "--dark": "#211e16", "--dark2": "#2a261c",
            "--light": "#f6f3ec", "--muted": "#837c6a",
            "--text": "#2a2619", "--border": "#e5ded0",
            "--on-accent": "#1a1813",
        },
        "hero_overlay": "linear-gradient(180deg, rgba(33,30,22,0.50) 0%, rgba(33,30,22,0.82) 100%)",
        "css": (
            ".theme-earth .hero::after{display:none}"
            ".theme-earth .hero::before{background:"
            "radial-gradient(520px 380px at 15% 20%, rgba(151,134,78,0.28), transparent 70%),"
            "radial-gradient(520px 380px at 85% 30%, rgba(124,110,61,0.20), transparent 70%);}"
            ".theme-earth .page-hero::after{background:radial-gradient(420px 260px at 80% 0%, rgba(151,134,78,0.22), transparent 65%);}"
        ),
    },
}

THEME_BY_CATEGORY: dict[str, str] = {
    "landscap": "fresh", "garden": "fresh", "nursery": "fresh",
    "lawn": "fresh", "tree": "fresh",
    "restaurant": "warm", "cafe": "warm", "coffee": "warm",
    "bakery": "warm", "bistro": "warm", "catering": "warm",
    # Coastal — water / cleaning / spa
    "pool": "coastal", "marine": "coastal", "boat": "coastal",
    "cleaning": "coastal", "janitorial": "coastal", "window cleaning": "coastal",
    "spa": "coastal",
    # Slate — heavy trades / auto
    "mechanic": "slate", "auto": "slate", "automotive": "slate",
    "welding": "slate", "construction": "slate", "contractor": "slate",
    "concrete": "slate", "excavat": "slate",
    # Luxe — salons / aesthetics / luxury
    "salon": "luxe", "med spa": "luxe", "medspa": "luxe", "aesthetic": "luxe",
    "jewel": "luxe", "luxury": "luxe",
    # Bloom — florists / beauty / boutiques
    "florist": "bloom", "flower": "bloom", "nail": "bloom", "beauty": "bloom",
    "boutique": "bloom", "esthetic": "bloom",
    # Trust — professional services
    "lawyer": "trust", "legal": "trust", "accountant": "trust", "accounting": "trust",
    "dentist": "trust", "dental": "trust", "clinic": "trust", "medical": "trust",
    "insurance": "trust", "financial": "trust", "notary": "trust",
    # Bold — fitness / barbers
    "gym": "bold", "fitness": "bold", "crossfit": "bold", "barber": "bold",
    "boxing": "bold", "martial": "bold",
    # Earth — wellness / organic / craft
    "yoga": "earth", "wellness": "earth", "organic": "earth", "artisan": "earth",
    "craft": "earth", "pottery": "earth", "holistic": "earth",
}


def _load_customize(site_dir: Path) -> dict:
    """Load the per-client customization layer if present, else return {}."""
    path = Path(site_dir) / "customize.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            print(f"[build] customize.json unreadable ({exc}) - ignoring")
    return {}


def _normalize_review(r: dict, city: str = "BC") -> dict:
    """Map a customize-layer review {name,rating,text,location} to the internal
    review shape {author,rating,text,location,time} used by the renderers."""
    if not isinstance(r, dict):
        return {"author": "Google Reviewer", "rating": 5, "text": str(r),
                "location": f"{city}, BC"}
    try:
        rating = int(r.get("rating") or 5)
    except (TypeError, ValueError):
        rating = 5
    rating = max(1, min(5, rating))
    return {
        "author":   r.get("name") or r.get("author") or "Google Reviewer",
        "rating":   rating,
        "text":     r.get("text") or "Great service!",
        "location": r.get("location") or f"{city}, BC",
        "time":     r.get("time") or "",
    }


def _select_theme(business: dict) -> dict:
    cats = business.get("categories") or [business.get("category", "")]
    for cat in cats:
        key = (cat or "").lower().strip()
        for needle, theme_name in THEME_BY_CATEGORY.items():
            if needle in key:
                return THEMES[theme_name]
    return THEMES["modern"]



# ── Entry point ───────────────────────────────────────────────────────────────

def build_website(profile_dir: str, output_dir: str = "./output") -> Path:
    """
    Phase 3 entry point. Reads the scraped profile and generates a
    complete website into ./output/{business_slug}/.
    """
    profile_path = Path(profile_dir) / "profile.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"No profile.json found in {profile_dir}. Run Phase 2 first.")

    profile  = json.loads(profile_path.read_text(encoding="utf-8", errors="replace"))
    business = profile.get("business", {})

    slug     = _slugify(business.get("name", "unknown-business"))
    site_dir = Path(output_dir) / slug
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "css").mkdir(exist_ok=True)
    (site_dir / "js").mkdir(exist_ok=True)
    (site_dir / "images").mkdir(exist_ok=True)

    stack = _select_stack(business)
    print(f"[build] Stack: {stack} for {business.get('name')}")

    # Load optional per-client customization layer (output/{slug}/customize.json)
    customize = _load_customize(site_dir)
    if customize:
        print(f"[build] Customizations found for {slug}")

    # Theme: customize override takes precedence over category-based selection
    theme = None
    ctheme = customize.get("theme")
    if ctheme and ctheme in THEMES:
        theme = THEMES[ctheme]
        print(f"[build] Theme overridden by customize: {theme['name']}")
    if theme is None:
        theme = _select_theme(business)
    business["_theme"] = theme
    print(f"[build] Theme: {theme['name']}")

    # Generate content via Claude (or fall back to templates)
    print("[build] Generating page content...")
    content = _generate_content(business, profile, customize)

    print("[build] Building static site...")
    _write_css(site_dir, content, theme)
    _write_js(site_dir)
    _write_index(business, profile, content, site_dir, customize)
    _write_services(business, content, site_dir)
    _write_about(business, content, site_dir)
    _write_contact(business, content, site_dir)
    _write_reviews(business, profile, content, site_dir, customize)
    _write_sitemap(business, site_dir)
    _write_robots(site_dir)
    _copy_logo(profile_dir, site_dir)

    print(f"[build] Site complete: {site_dir}")
    print(f"[build] Pages: index, services, about, contact, reviews")
    return site_dir


# ── Stack selection ───────────────────────────────────────────────────────────

def _select_stack(business: dict) -> StackType:
    cats = business.get("categories") or [business.get("category", "")]
    for cat in cats:
        key = cat.lower().strip()
        if key in STACK_BY_CATEGORY:
            return STACK_BY_CATEGORY[key]
        for k, v in STACK_BY_CATEGORY.items():
            if k in key or key in k:
                return v
    return "static"


# ── AI content generation ─────────────────────────────────────────────────────

def _generate_content(business: dict, profile: dict, customize: dict | None = None) -> dict:
    """
    Call Claude API to generate tailored copy for the site.
    Falls back to template content if no API key.
    """
    customize = customize or {}
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_anthropic_api_key_here":
        print("[build] No ANTHROPIC_API_KEY - using template content")
        return _template_content(business, profile)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        name     = business.get("name", "Our Business")
        city     = business.get("city", "British Columbia")
        cats     = business.get("categories") or [business.get("category", "service")]
        category = cats[0] if cats else "service"
        phone    = business.get("phone", "")
        address  = business.get("address", "")
        rating   = business.get("rating", "")
        reviews  = business.get("review_count", 0)

        # Pull any real text from Phase 2
        website_text = ""
        w = profile.get("website", {})
        if isinstance(w, dict) and w.get("text_content"):
            tc = w["text_content"]
            website_text = tc.get("full_text_preview", "")[:800]

        # Owner-supplied facts and brand voice from the customize layer
        facts = (customize.get("facts") or "").strip()
        voice = (customize.get("voice") or "").strip()
        extra = ""
        if facts:
            extra += f"\nOwner-provided facts (use these — they are authoritative):\n{facts[:1200]}\n"
        if voice:
            extra += f"\nBrand voice / tone to write in:\n{voice[:600]}\n"

        prompt = f"""You are writing website copy for a local BC business.

Business: {name}
City: {city}, BC, Canada
Category: {category}
Phone: {phone or "TBD"}
Address: {address or "TBD"}
Rating: {rating} stars ({reviews} reviews)
Existing site text snippet: {website_text or "None available"}
{extra}
Generate JSON with these exact keys:
{{
  "headline": "Short punchy hero headline (max 8 words, no quotes)",
  "tagline": "One sentence value proposition mentioning {city}",
  "about_paragraph": "2-3 sentences about the business, local focus, Canadian English",
  "services": [
    {{"name": "Service Name", "description": "One sentence description", "icon": "emoji"}},
    ... (4-6 services typical for {category})
  ],
  "cta_text": "Primary call-to-action button text (max 5 words)",
  "trust_line": "Short trust signal line (e.g. '15+ years serving {city} families')",
  "faq": [
    {{"q": "Question?", "a": "Answer in 1-2 sentences."}},
    ... (3-4 common questions for {category})
  ],
  "meta_description": "SEO meta description, 150-160 chars, mention {city} and {category}"
}}

Return only valid JSON, no markdown, no explanation."""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
        print("[build] Claude content generated successfully")
        return data

    except Exception as exc:
        print(f"[build] Claude API failed ({exc}) - using template content")
        return _template_content(business, profile)


def _template_content(business: dict, profile: dict) -> dict:
    """Fallback template content when Claude API is unavailable."""
    name     = business.get("name", "Our Business")
    city     = business.get("city", "Victoria")
    cats     = business.get("categories") or [business.get("category", "services")]
    category = cats[0] if cats else "services"

    service_map = {
        "plumber": [
            {"name": "Emergency Repairs", "description": "Fast response for burst pipes, leaks, and urgent plumbing emergencies.", "icon": "🚨"},
            {"name": "Drain Cleaning", "description": "Professional drain clearing for clogs of all kinds.", "icon": "🔧"},
            {"name": "Water Heater Service", "description": "Installation, repair, and replacement of all water heater types.", "icon": "🌡️"},
            {"name": "Fixture Installation", "description": "Sinks, toilets, showers, and faucets installed right the first time.", "icon": "🚿"},
            {"name": "Pipe Repair", "description": "Expert repair and re-piping services for residential and commercial.", "icon": "🔩"},
        ],
        "electrician": [
            {"name": "Panel Upgrades", "description": "Safe, code-compliant electrical panel upgrades for your home.", "icon": "⚡"},
            {"name": "Wiring & Rewiring", "description": "New wiring installations and rewiring for older properties.", "icon": "🔌"},
            {"name": "Outlet & Switch Installation", "description": "Add outlets, switches, and USB ports wherever you need them.", "icon": "💡"},
            {"name": "EV Charger Installation", "description": "Level 2 EV charger installation for your home or business.", "icon": "🚗"},
            {"name": "Emergency Service", "description": "24/7 emergency electrical service for urgent situations.", "icon": "🚨"},
        ],
        "landscaper": [
            {"name": "Lawn Care & Maintenance", "description": "Regular mowing, edging, and seasonal lawn care to keep your yard looking its best.", "icon": "🌱"},
            {"name": "Garden Design", "description": "Custom garden and planting design tailored to your space and climate.", "icon": "🌷"},
            {"name": "Hardscaping", "description": "Patios, walkways, retaining walls, and stonework built to last.", "icon": "🧱"},
            {"name": "Tree & Shrub Care", "description": "Pruning, trimming, and planting to keep your greenery healthy.", "icon": "🌳"},
            {"name": "Irrigation Systems", "description": "Efficient sprinkler and irrigation installation and repair.", "icon": "💧"},
            {"name": "Seasonal Cleanup", "description": "Spring and fall cleanups to refresh and protect your property.", "icon": "🍂"},
        ],
        "garden": [
            {"name": "Plants & Nursery Stock", "description": "A wide selection of healthy trees, shrubs, perennials, and annuals.", "icon": "🌿"},
            {"name": "Soil & Mulch", "description": "Quality soils, composts, and mulches for every garden project.", "icon": "🪴"},
            {"name": "Garden Supplies", "description": "Tools, pots, fertilizers, and everything you need to grow.", "icon": "🛠️"},
            {"name": "Expert Advice", "description": "Friendly, knowledgeable staff to help you choose the right plants.", "icon": "💬"},
            {"name": "Delivery", "description": "Convenient local delivery for bulk and large orders.", "icon": "🚚"},
        ],
        "default": [
            {"name": "Consultation", "description": "Free professional consultation to assess your needs.", "icon": "💬"},
            {"name": "Quality Service", "description": "Expert service delivered on time and on budget.", "icon": "⭐"},
            {"name": "Maintenance", "description": "Ongoing maintenance plans to keep everything running smoothly.", "icon": "🔧"},
            {"name": "Emergency Response", "description": "Fast response when you need us most.", "icon": "🚨"},
            {"name": "Free Estimates", "description": "No-obligation estimates for all projects.", "icon": "📋"},
        ],
    }

    cat_key = category.lower()
    services = service_map["default"]
    for key in service_map:
        if key != "default" and key in cat_key:
            services = service_map[key]
            break

    # Normalise person-nouns to trade nouns so headlines read naturally:
    # "landscaper" -> "Landscaping", "plumber" -> "Plumbing", etc.
    trade_nouns = {
        "landscaper": "Landscaping", "plumber": "Plumbing",
        "electrician": "Electrical", "roofer": "Roofing",
        "painter": "Painting", "mechanic": "Auto Repair",
        "contractor": "Contracting", "barber": "Barber",
    }
    trade = next((v for k, v in trade_nouns.items() if k in cat_key), category.title())
    # Avoid awkward doubling like "Trusted Services Services in ..."
    headline = (f"Trusted {trade} in {city}"
                if ("service" in cat_key or "service" in trade.lower())
                else f"Trusted {trade} Services in {city}")

    service_noun = trade.lower()
    return {
        "headline": headline,
        "tagline": f"Professional, reliable {service_noun} serving {city} and the surrounding area.",
        "about_paragraph": f"{name} proudly serves the {city} community with top-quality {service_noun}. Our experienced team delivers honest, dependable work at fair prices. We treat every customer like a neighbour.",
        "services": services,
        "cta_text": "Get a Free Quote",
        "trust_line": f"Proudly serving {city}, BC and surrounding areas",
        "faq": [
            {"q": "Do you offer free estimates?", "a": "Yes, we provide free, no-obligation estimates for all projects."},
            {"q": "Are you licensed and insured?", "a": "Absolutely. We are fully licensed and insured for your peace of mind."},
            {"q": "How quickly can you respond?", "a": "We offer prompt scheduling and fast response for urgent jobs."},
            {"q": "What areas do you serve?", "a": f"We serve {city} and the surrounding region. Contact us to confirm service in your area."},
        ],
        "meta_description": f"{name} - {category.title()} in {city}, BC. Trusted by locals. Call for a free quote today.",
    }


# ── CSS ───────────────────────────────────────────────────────────────────────

def _write_css(site_dir: Path, content: dict, theme: dict | None = None) -> None:
    theme = theme or THEMES["modern"]
    css = _theme_css(theme) + """\
/* ── Reset ─────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; -webkit-text-size-adjust: 100%; }

body {
  font-family: var(--font);
  color: var(--text);
  background: var(--white);
  line-height: 1.7;
  font-size: 1rem;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  overflow-x: hidden;
}

section p, .about-content p, .section-head p {
  max-width: 68ch;
}

img { max-width: 100%; height: auto; display: block; }
a   { color: var(--green); text-decoration: none; }
a:hover { color: var(--green2); }

/* ── Typography ─────────────────────────────────────────────────────────── */
h1, h2, h3, .nav-logo, .footer-brand, .stat-num {
  font-family: var(--font-display);
  letter-spacing: -0.02em;
}
h1 { font-size: clamp(2.1rem, 6vw, 3.6rem); font-weight: 700; line-height: 1.08; }
h2 { font-size: clamp(1.7rem, 3.5vw, 2.6rem); font-weight: 700; line-height: 1.18; margin-bottom: 0.85rem; }
@media (min-width: 881px) { h2 { font-size: clamp(1.9rem, 3.5vw, 2.8rem); } }
h3 { font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem; }
p  { margin-bottom: 1rem; }
.eyebrow {
  display: inline-block;
  font-family: var(--font);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--green);
  margin-bottom: 0.85rem;
}
.section-head { max-width: 640px; margin: 0 auto 0; text-align: center; }
.section-head p { color: var(--muted); font-size: 1.05rem; }

/* ── Layout ─────────────────────────────────────────────────────────────── */
.container { max-width: 1140px; margin: 0 auto; padding: 0 1.5rem; }
.section    { padding: 5.5rem 0; }
.section-alt { background: var(--light); }
.section-dark { background: var(--dark); color: var(--white); }

/* ── Scroll reveal ──────────────────────────────────────────────────────── */
.reveal { opacity: 0; transform: translateY(26px); transition: opacity 0.7s var(--ease), transform 0.7s var(--ease); will-change: opacity, transform; }
.reveal.in { opacity: 1; transform: none; }
@media (prefers-reduced-motion: reduce) {
  .reveal { opacity: 1; transform: none; transition: none; }
  html { scroll-behavior: auto; }
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.95rem 2rem;
  border-radius: 999px;
  font-weight: 600;
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  border: none;
  transition: transform 0.2s var(--ease), box-shadow 0.2s var(--ease), background 0.2s;
  text-align: center;
  min-height: 52px;
}
.btn:hover { transform: translateY(-2px); }
.btn-primary  { background: var(--green); color: var(--on-accent); box-shadow: 0 8px 22px rgba(31,181,116,0.35); }
.btn-primary:hover { background: var(--green2); box-shadow: 0 12px 30px rgba(31,181,116,0.45); color: var(--on-accent); }
.btn-outline  { background: rgba(255,255,255,0.04); color: #fff; border: 1.5px solid rgba(255,255,255,0.3); backdrop-filter: blur(6px); }
.btn-outline:hover { background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.6); color:#fff; }
.btn-white    { background: #fff; color: var(--dark); box-shadow: var(--shadow); }
.btn-white:hover { background: var(--light); color: var(--dark); }
.btn-lg { padding: 1.1rem 2.6rem; font-size: 1.08rem; min-height: 58px; }
.btn-sm { padding: 0.65rem 1.3rem; font-size: 0.9rem; min-height: 44px; }

/* ── Nav (glass) ───────────────────────────────────────────────────────── */
nav {
  position: sticky;
  top: 0;
  z-index: 100;
  padding: 1.1rem 0;
  background: rgba(10,22,34,0.72);
  backdrop-filter: saturate(160%) blur(14px);
  -webkit-backdrop-filter: saturate(160%) blur(14px);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  transition: padding 0.3s var(--ease), background 0.3s;
}
nav.scrolled { padding: 0.65rem 0; background: rgba(10,22,34,0.92); }
.nav-inner { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.nav-logo { font-weight: 700; font-size: 1.25rem; color: var(--white); }
.nav-logo span { color: var(--green); }
.nav-links { display: flex; align-items: center; gap: 1.8rem; list-style: none; }
.nav-links a { color: rgba(255,255,255,0.78); font-size: 0.92rem; font-weight: 500; transition: color 0.2s; }
.nav-links a:hover { color: var(--white); }
.nav-cta { margin-left: 0.5rem; }
.nav-toggle {
  display: none; background: none; border: none; cursor: pointer;
  padding: 0.5rem; flex-direction: column; gap: 5px; z-index: 110;
}
.nav-toggle span { display: block; width: 26px; height: 2px; background: #fff; border-radius: 2px; transition: all 0.3s var(--ease); }
.nav-toggle.open span:nth-child(1) { transform: translateY(7px) rotate(45deg); }
.nav-toggle.open span:nth-child(2) { opacity: 0; }
.nav-toggle.open span:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }

/* ── Hero ─────────────────────────────────────────────────────────────────── */
@keyframes heroPulse {
  0%   { box-shadow: 0 8px 22px rgba(31,181,116,0.35), 0 0 0 0 rgba(31,181,116,0.5); }
  50%  { box-shadow: 0 8px 22px rgba(31,181,116,0.35), 0 0 0 14px rgba(31,181,116,0); }
  100% { box-shadow: 0 8px 22px rgba(31,181,116,0.35), 0 0 0 0 rgba(31,181,116,0); }
}
.hero {
  position: relative;
  color: var(--white);
  min-height: 100svh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  overflow: hidden;
  background: radial-gradient(1200px 600px at 50% -10%, #16344f 0%, var(--dark) 60%);
}
.hero::before {
  content: "";
  position: absolute; inset: 0;
  background:
    radial-gradient(520px 380px at 15% 20%, rgba(31,181,116,0.28), transparent 70%),
    radial-gradient(520px 380px at 85% 30%, rgba(56,128,255,0.22), transparent 70%),
    radial-gradient(700px 400px at 50% 100%, rgba(26,58,92,0.4), transparent 70%);
  pointer-events: none;
}
.hero::after {
  content: "";
  position: absolute; inset: 0;
  background-image: linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
  background-size: 54px 54px;
  -webkit-mask-image: radial-gradient(circle at 50% 35%, #000 0%, transparent 75%);
          mask-image: radial-gradient(circle at 50% 35%, #000 0%, transparent 75%);
  pointer-events: none;
}
.hero .container { position: relative; z-index: 1; padding-top: 3rem; padding-bottom: 2rem; }
.hero h1 { color: var(--white); margin-bottom: 1.4rem; }
.hero h1 span { color: var(--green); }
.hero-eyebrow {
  display: inline-block;
  background: rgba(255,255,255,0.1);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 999px;
  padding: 0.4rem 1.1rem;
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: rgba(255,255,255,0.92);
  margin-bottom: 1.2rem;
}
.hero-eyebrow .hero-star { color: #f5c842; margin-right: 0.2rem; }
.hero-sub { font-size: clamp(1.05rem, 2vw, 1.25rem); color: rgba(255,255,255,0.82); max-width: 620px; margin: 0 auto 2.2rem; }
.hero-actions { display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }
.hero-actions .btn-primary { animation: heroPulse 1.2s ease-out 0.4s 2; }
.trust-bar {
  position: relative; z-index: 1;
  border-top: 1px solid rgba(255,255,255,0.1);
  padding: 1.4rem 0; margin-top: 3.5rem;
  font-size: 0.92rem; color: rgba(255,255,255,0.72);
}
.trust-items { display: flex; justify-content: center; gap: 2.2rem; flex-wrap: wrap; }
.trust-item { display: flex; align-items: center; gap: 0.5rem; }
.trust-item .check { color: var(--green); font-size: 1.05rem; }

/* ── Service cards ─────────────────────────────────────────────────────── */
.services-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1.6rem;
  margin-top: 3rem;
}
/* 2-col layout for the services page */
.services-grid-2col {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.6rem;
  margin-top: 3rem;
}
@media (max-width: 640px) {
  .services-grid-2col { grid-template-columns: 1fr; }
}
.service-card {
  position: relative;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: transform 0.3s var(--ease), box-shadow 0.3s var(--ease), border-color 0.3s;
}
.service-card::before {
  content: "";
  position: absolute;
  top: 0; left: 0;
  height: 4px;
  width: 40%;
  background: var(--green);
  border-radius: var(--radius) 0 0 0;
  transition: width 0.35s var(--ease);
  z-index: 2;
}
.service-card:hover::before { width: 100%; border-radius: 0; }
.service-card:hover { transform: translateY(-6px); box-shadow: var(--shadow-lg); border-color: rgba(31,181,116,0.4); }
.service-img { width: 100%; height: 190px; object-fit: cover; display: block; background: var(--border); transition: transform 0.5s var(--ease); }
.service-card:hover .service-img { transform: scale(1.05); }
.service-card-body { padding: 1.6rem; display: flex; flex-direction: column; }
.service-icon {
  font-size: 1.65rem; margin-bottom: 0.75rem;
  width: 58px; height: 58px; display: flex; align-items: center; justify-content: center;
  background: rgba(31,181,116,0.12);
  border-radius: 50%;
  margin-top: -3.8rem;
  position: relative;
  border: 4px solid var(--white);
  box-shadow: 0 0 0 3px rgba(31,181,116,0.2);
}
.service-card h3 { color: var(--navy); }
.service-card p  { color: var(--muted); font-size: 0.96rem; flex: 1; }
.service-learn-more {
  display: inline-flex; align-items: center; gap: 0.3rem;
  font-size: 0.88rem; font-weight: 600; color: var(--green);
  margin-top: 1rem; transition: gap 0.2s;
}
.service-learn-more:hover { gap: 0.55rem; color: var(--green2); }

/* ── Stats strip ─────────────────────────────────────────────────────────── */
.stats-strip {
  background: var(--dark);
  padding: 3.5rem 0;
  border-top: 1px solid rgba(255,255,255,0.06);
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 2rem;
  text-align: center;
}
.stats-grid .stat-num {
  font-size: clamp(2.2rem, 4vw, 3rem);
  font-weight: 700;
  color: var(--green);
  display: block;
  line-height: 1;
  margin-bottom: 0.4rem;
  font-family: var(--font-display);
  letter-spacing: -0.03em;
}
.stats-grid .stat-label {
  font-size: 0.88rem;
  color: rgba(255,255,255,0.55);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 500;
}

/* ── Testimonials strip ──────────────────────────────────────────────────── */
.testimonials-strip { background: var(--light); }
.testimonials-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
  gap: 1.6rem;
  margin-top: 3rem;
}
.testimonial-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 2rem 1.75rem 1.75rem;
  box-shadow: var(--shadow);
  transition: transform 0.3s var(--ease), box-shadow 0.3s var(--ease);
  position: relative;
}
.testimonial-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-lg); }
.testimonial-quote {
  font-size: 1rem;
  line-height: 1.65;
  color: var(--text);
  margin-bottom: 1.25rem;
  border-left: 4px solid var(--green);
  padding-left: 1rem;
  font-style: italic;
}
.testimonial-stars { color: #f5a623; font-size: 1rem; letter-spacing: 2px; margin-bottom: 0.75rem; }
.testimonial-meta { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; }
.testimonial-author { font-weight: 700; font-size: 0.9rem; color: var(--navy); }
.testimonial-location { font-size: 0.8rem; color: var(--muted); }
.testimonial-g-badge {
  width: 26px; height: 26px; border-radius: 50%;
  background: #4285F4;
  color: #fff; font-size: 0.8rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}

/* ── About teaser split ──────────────────────────────────────────────────── */
.about-split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4rem;
  align-items: center;
}
.about-split-img-wrap {
  position: relative;
}
.about-split-img {
  width: 100%;
  height: 420px;
  object-fit: cover;
  border-radius: var(--radius);
  display: block;
  box-shadow: var(--shadow-lg);
}
.about-split-badge {
  position: absolute;
  bottom: -1.25rem;
  right: -1.25rem;
  background: var(--green);
  color: var(--on-accent);
  padding: 0.85rem 1.4rem;
  border-radius: var(--radius);
  font-weight: 700;
  font-size: 0.9rem;
  text-align: center;
  line-height: 1.3;
  box-shadow: var(--shadow-lg);
  border: 3px solid var(--white);
}
.about-split-content .eyebrow { margin-bottom: 0.6rem; }
.about-checklist { list-style: none; margin: 1.25rem 0 1.75rem; }
.about-checklist li {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  padding: 0.45rem 0;
  font-size: 0.97rem;
  color: var(--text);
}
.about-checklist li .check-icon {
  color: var(--green);
  font-size: 1rem;
  margin-top: 2px;
  flex-shrink: 0;
}

/* ── CTA banner (upgraded) ──────────────────────────────────────────────── */
.cta-banner {
  position: relative; overflow: hidden;
  background: linear-gradient(135deg, var(--navy) 0%, var(--dark) 100%);
  color: white; text-align: center; padding: 5.5rem 0;
}
.cta-banner::before {
  content: ""; position: absolute; inset: 0;
  background:
    radial-gradient(600px 300px at 20% 0%, rgba(255,255,255,0.12), transparent 60%),
    radial-gradient(400px 300px at 80% 100%, rgba(31,181,116,0.12), transparent 60%);
  pointer-events: none;
}
.cta-banner .container { position: relative; z-index: 1; }
.cta-banner h2 { color: white; }
.cta-banner .cta-phone {
  display: block;
  font-size: clamp(1.6rem, 3vw, 2.2rem);
  font-weight: 700;
  color: var(--green);
  margin: 0.5rem 0 1.5rem;
  font-family: var(--font-display);
  letter-spacing: -0.02em;
  text-decoration: none;
}
.cta-banner .cta-phone:hover { color: #fff; }
.cta-banner p  { color: rgba(255,255,255,0.85); max-width: 540px; margin: 0 auto 2rem; }
.cta-actions { display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }
.cta-trust-note {
  margin-top: 1.25rem;
  font-size: 0.85rem;
  color: rgba(255,255,255,0.5);
  letter-spacing: 0.04em;
}

/* ── Why choose us ─────────────────────────────────────────────────────── */
.why-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.6rem;
  margin-top: 3rem;
}
.why-item {
  text-align: center; padding: 2rem 1.5rem;
  background: var(--white); border: 1px solid var(--border);
  border-radius: var(--radius); transition: transform 0.3s var(--ease), box-shadow 0.3s var(--ease);
}
.why-item:hover { transform: translateY(-4px); box-shadow: var(--shadow); }
.why-icon { font-size: 2.4rem; margin-bottom: 0.6rem; }
.why-item h3 { color: var(--navy); margin-bottom: 0.3rem; }
.why-item p  { color: var(--muted); font-size: 0.92rem; margin: 0; }

/* ── CTA banner ─────────────────────────────────────────────────────────── */
.cta-banner {
  position: relative; overflow: hidden;
  background: linear-gradient(120deg, var(--green2) 0%, var(--navy) 100%);
  color: white; text-align: center; padding: 5rem 0;
}
.cta-banner::before {
  content: ""; position: absolute; inset: 0;
  background: radial-gradient(600px 300px at 20% 0%, rgba(255,255,255,0.16), transparent 60%);
  pointer-events: none;
}
.cta-banner .container { position: relative; z-index: 1; }
.cta-banner h2 { color: white; }
.cta-banner p  { color: rgba(255,255,255,0.9); max-width: 540px; margin: 0 auto 2rem; }

/* ── Reviews ─────────────────────────────────────────────────────────────── */
.reviews-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
  gap: 1.6rem;
  margin-top: 3rem;
}
.review-card {
  position: relative;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 2rem 1.75rem 1.75rem;
  box-shadow: var(--shadow);
  transition: transform 0.3s var(--ease), box-shadow 0.3s var(--ease);
}
.review-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-lg); }
.review-card::before {
  content: "\\201C"; position: absolute; top: 0.4rem; right: 1.2rem;
  font-family: var(--font-display); font-size: 3.5rem; line-height: 1;
  color: rgba(31,181,116,0.18);
}
.stars { color: #f5a623; font-size: 1.1rem; margin-bottom: 0.6rem; letter-spacing: 2px; }
.review-text { color: var(--text); margin-bottom: 0.85rem; font-size: 0.98rem; line-height: 1.6; }
.review-author { font-weight: 600; font-size: 0.9rem; color: var(--navy); }

/* ── About ────────────────────────────────────────────────────────────── */
.about-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3.5rem;
  align-items: center;
}
.about-image {
  position: relative; overflow: hidden;
  background: linear-gradient(135deg, var(--navy), var(--green));
  border-radius: var(--radius);
  height: 360px;
  display: flex; align-items: center; justify-content: center;
  font-size: 4rem; box-shadow: var(--shadow-lg);
}
.about-image::after {
  content: ""; position: absolute; inset: 0;
  background: radial-gradient(400px 300px at 80% 20%, rgba(255,255,255,0.22), transparent 60%);
}
.stat-row { display: flex; gap: 2.5rem; margin-top: 2rem; flex-wrap: wrap; }
.stat { text-align: center; }
.stat-num { font-size: 2.4rem; font-weight: 700; color: var(--green); display: block; line-height: 1; }
.stat-label { font-size: 0.85rem; color: var(--muted); margin-top: 0.3rem; }

/* ── Contact ─────────────────────────────────────────────────────────────── */
.contact-grid {
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: 3rem;
  margin-top: 2.5rem;
  align-items: start;
}
.contact-info { list-style: none; }
.contact-info li {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.9rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.97rem;
}
.contact-info li:last-child { border-bottom: none; }
.ci-icon { font-size: 1.2rem; margin-top: 2px; flex-shrink: 0; }
.ci-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
.ci-value { font-weight: 600; }

/* ── Form ─────────────────────────────────────────────────────────────────── */
.form-card {
  background: var(--light);
  border-radius: var(--radius);
  padding: 2rem;
}
.form-card h3 { margin-bottom: 1.25rem; color: var(--navy); }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.form-group { margin-bottom: 1rem; }
.form-group label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  margin-bottom: 0.35rem;
}
.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 1rem;
  font-family: var(--font);
  background: var(--white);
  color: var(--text);
  transition: border-color 0.2s;
}
.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: var(--green);
  box-shadow: 0 0 0 3px rgba(34,162,98,0.12);
}
.form-group textarea { resize: vertical; min-height: 110px; }
.form-success {
  display: none;
  background: rgba(34,162,98,0.1);
  border: 1px solid var(--green);
  border-radius: 8px;
  padding: 1rem;
  color: var(--green);
  font-weight: 600;
  text-align: center;
  margin-top: 1rem;
}
.form-note { font-size:0.85rem; color:var(--muted); margin-top:0.5rem; text-align:center; }

/* ── FAQ ─────────────────────────────────────────────────────────────────── */
.faq-list { margin-top: 2rem; }
.faq-item {
  border-bottom: 1px solid var(--border);
  padding: 1.25rem 0;
}
.faq-q {
  font-weight: 600;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--navy);
  user-select: none;
}
.faq-q .arrow { transition: transform 0.25s; font-size: 0.85rem; color: var(--muted); }
.faq-item.open .faq-q .arrow { transform: rotate(180deg); }
.faq-a { display: none; padding-top: 0.75rem; color: var(--muted); font-size: 0.97rem; }
.faq-item.open .faq-a { display: block; }

/* ── Contact info panel ──────────────────────────────────────────────────── */
.contact-info-panel {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 2rem;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  height: 100%;
}
.contact-info-panel h3 { color: var(--navy); margin-bottom: 0.25rem; }
.contact-phone {
  display: block;
  font-size: clamp(1.4rem, 3vw, 1.9rem);
  font-weight: 700;
  color: var(--green);
  font-family: var(--font-display);
  letter-spacing: -0.02em;
  text-decoration: none;
  transition: color 0.2s;
}
.contact-phone:hover { color: var(--green2); }
.map-placeholder {
  height: 200px;
  background: var(--light);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 0.5rem;
  color: var(--muted);
  border: 1px solid var(--border);
  text-align: center;
  font-size: 0.95rem;
}
.map-placeholder a { color: var(--green); font-weight: 600; font-size: 0.9rem; }
.trust-badges {
  display: flex;
  gap: 2rem;
  justify-content: center;
  flex-wrap: wrap;
  padding: 2rem 0;
}
.trust-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--navy);
}
.trust-badge .badge-icon { font-size: 1.3rem; }

/* ── Team grid ───────────────────────────────────────────────────────────── */
.team-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1.5rem;
  margin-top: 2rem;
}
.team-card {
  text-align: center;
  padding: 1.5rem 1rem;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  transition: transform 0.3s var(--ease), box-shadow 0.3s var(--ease);
}
.team-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-lg); }
.team-photo {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  object-fit: cover;
  margin: 0 auto 1rem;
  display: block;
  border: 3px solid var(--border);
}
.team-card h4 { color: var(--navy); font-size: 1rem; margin-bottom: 0.2rem; }
.team-card p  { color: var(--muted); font-size: 0.88rem; margin: 0; }

/* ── Review summary bar ──────────────────────────────────────────────────── */
.review-summary {
  margin-bottom: 2rem;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.75rem 2rem;
  box-shadow: var(--shadow);
  max-width: 420px;
}
.review-summary h3 { margin-bottom: 1rem; color: var(--navy); }
.rating-bar-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.4rem;
  font-size: 0.88rem;
  color: var(--text);
}
.rating-bar-track {
  flex: 1;
  height: 8px;
  background: var(--border);
  border-radius: 4px;
  overflow: hidden;
}
.rating-bar-fill {
  height: 8px;
  background: var(--green);
  border-radius: 4px;
  transition: width 0.6s var(--ease);
}
.rating-bar-pct { min-width: 36px; text-align: right; color: var(--muted); }

/* ── Services page trust strip ────────────────────────────────────────────── */
.services-trust-strip {
  background: var(--light);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  padding: 2.5rem 0;
}
.services-trust-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2rem;
  text-align: center;
}
.services-trust-item { padding: 1.25rem; }
.services-trust-item .trust-icon { font-size: 2rem; margin-bottom: 0.5rem; }
.services-trust-item h4 { color: var(--navy); margin-bottom: 0.3rem; font-size: 1rem; }
.services-trust-item p  { color: var(--muted); font-size: 0.9rem; margin: 0; }
@media (max-width: 560px) {
  .services-trust-grid { grid-template-columns: 1fr; gap: 1.25rem; }
  .team-grid { grid-template-columns: repeat(2, 1fr); }
  .trust-badges { gap: 1.25rem; }
}

/* ── Footer ─────────────────────────────────────────────────────────────── */
footer {
  background: var(--dark);
  color: rgba(255,255,255,0.7);
  padding: 3rem 0 1.5rem;
}
.footer-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 2.5rem;
  margin-bottom: 2rem;
}
.footer-brand { font-weight: 800; font-size: 1.1rem; color: white; margin-bottom: 0.5rem; }
.footer-brand span { color: var(--green); }
.footer-desc { font-size: 0.9rem; line-height: 1.6; }
.footer-col h4 { color: white; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.75rem; }
.footer-links { list-style: none; }
.footer-links li { margin-bottom: 0.4rem; }
.footer-links a { color: rgba(255,255,255,0.6); font-size: 0.9rem; }
.footer-links a:hover { color: white; }
.footer-bottom {
  border-top: 1px solid rgba(255,255,255,0.08);
  padding-top: 1.25rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.footer-credit { font-size:0.78rem; color:rgba(255,255,255,0.35); }
.footer-credit a { color:rgba(255,255,255,0.35); text-decoration:none; transition:color 0.2s; }
.footer-credit a:hover { color:rgba(255,255,255,0.7); }

/* ── Page header ─────────────────────────────────────────────────────────── */
.page-hero {
  position: relative; overflow: hidden;
  background: radial-gradient(900px 400px at 50% -30%, #16344f, var(--dark) 70%);
  color: white; padding: 4.5rem 0 3.5rem; text-align: center;
}
.page-hero::after {
  content: ""; position: absolute; inset: 0;
  background: radial-gradient(420px 260px at 80% 0%, rgba(31,181,116,0.18), transparent 65%);
  pointer-events: none;
}
.page-hero .container { position: relative; z-index: 1; }
.page-hero h1 { color: white; }
.page-hero p  { color: rgba(255,255,255,0.78); margin-top: 0.6rem; }

/* ── Mobile sticky call bar (key sales feature) ────────────────────────── */
.mobile-callbar {
  display: none;
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 200;
  background: rgba(10,22,34,0.96);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid rgba(255,255,255,0.08);
  padding: 0.6rem 0.75rem calc(0.6rem + env(safe-area-inset-bottom));
  gap: 0.6rem;
  box-shadow: 0 -6px 24px rgba(0,0,0,0.28);
}
.mobile-callbar .btn { flex: 1; min-height: 50px; font-size: 0.98rem; }

/* ── Tablet & mobile ───────────────────────────────────────────────────── */
@media (max-width: 880px) {
  .section { padding: 4rem 0; }
  .nav-links {
    position: fixed; inset: 0 0 0 auto; width: min(78vw, 320px);
    flex-direction: column; align-items: flex-start; justify-content: center;
    gap: 0.4rem; background: var(--dark); padding: 5rem 2rem 2rem;
    transform: translateX(100%); transition: transform 0.4s var(--ease);
    box-shadow: -20px 0 60px rgba(0,0,0,0.4);
  }
  .nav-links.open { transform: translateX(0); }
  .nav-links li { width: 100%; padding: 0.7rem 0; border-bottom: 1px solid rgba(255,255,255,0.07); }
  .nav-links a { font-size: 1.1rem; }
  .nav-toggle { display: flex; }
  .nav-cta { display: none; }
  .about-grid   { grid-template-columns: 1fr; gap: 2rem; }
  .about-image  { height: 260px; order: -1; }
  .about-split  { grid-template-columns: 1fr; gap: 2.5rem; }
  .about-split-img { height: 280px; }
  .about-split-badge { right: 0.5rem; bottom: -1rem; }
  .contact-grid { grid-template-columns: 1fr; }
  .footer-grid  { grid-template-columns: 1fr 1fr; gap: 1.75rem; }
  .stats-grid   { grid-template-columns: repeat(2, 1fr); gap: 1.5rem; }
  .cta-actions  { flex-direction: column; align-items: stretch; }
  .cta-actions .btn { width: 100%; }
}

@media (max-width: 560px) {
  .container { padding: 0 1.15rem; }
  .section { padding: 3.25rem 0; }
  .hero { min-height: 100svh; padding: 1.5rem 0; }
  .hero .container { padding-top: 2rem; padding-bottom: 1.5rem; }
  .hero-actions { flex-direction: column; align-items: stretch; }
  .hero-actions .btn { width: 100%; }
  .trust-items { flex-direction: column; align-items: center; gap: 0.75rem; }
  .footer-grid { grid-template-columns: 1fr; gap: 1.5rem; }
  .form-row { grid-template-columns: 1fr; }
  .footer-bottom { flex-direction: column; text-align: center; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); gap: 1.25rem; }
  .services-grid { grid-template-columns: 1fr; }
  .testimonials-grid { grid-template-columns: 1fr; }
  /* show sticky call bar + keep content clear of it */
  .mobile-callbar { display: flex; }
  body { padding-bottom: 76px; }
}
"""
    css += "\n/* ── Theme overrides ─────────────────────────────────────────── */\n"
    css += theme.get("css", "")
    (site_dir / "css" / "style.css").write_text(css, encoding="utf-8")


def _theme_css(theme: dict) -> str:
    """Build the :root palette block for the selected theme."""
    pal = dict(theme["palette"])
    pal.setdefault("--on-accent", "#ffffff")
    palette = "\n".join(f"  {k}: {v};" for k, v in pal.items())
    return f""":root {{
{palette}
  --white:   #ffffff;
  --shadow:  0 4px 24px rgba(13,27,42,0.07);
  --shadow-lg: 0 18px 48px rgba(13,27,42,0.16);
  --radius:  {theme.get('radius', '16px')};
  --radius-sm: 10px;
  --font:    'Inter', system-ui, -apple-system, sans-serif;
  --font-display: {theme['display_font']};
  --ease:    cubic-bezier(0.22, 1, 0.36, 1);
}}
"""


# ── JS ────────────────────────────────────────────────────────────────────────

def _write_js(site_dir: Path) -> None:
    js = """\
// Nav toggle
const toggle = document.querySelector('.nav-toggle');
const links  = document.querySelector('.nav-links');
if (toggle && links) {
  toggle.addEventListener('click', () => {
    links.classList.toggle('open');
    toggle.classList.toggle('open');
  });
  links.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
    links.classList.remove('open'); toggle.classList.remove('open');
  }));
  document.addEventListener('click', e => {
    if (!toggle.contains(e.target) && !links.contains(e.target)) {
      links.classList.remove('open'); toggle.classList.remove('open');
    }
  });
}

// Nav shrink on scroll
const navEl = document.querySelector('nav');
if (navEl) {
  const onScroll = () => navEl.classList.toggle('scrolled', window.scrollY > 24);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
}

// Scroll-reveal animations
const revealEls = document.querySelectorAll(
  '.section-head, .service-card, .why-item, .review-card, .about-grid > *, .about-split > *, .contact-grid > *, .faq-list, .stat, .stats-grid .stat, .testimonial-card'
);
if ('IntersectionObserver' in window && revealEls.length) {
  revealEls.forEach((el, i) => {
    el.classList.add('reveal');
    el.style.transitionDelay = (Math.min(i % 4, 3) * 0.08) + 's';
  });
  const io = new IntersectionObserver((entries, obs) => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); obs.unobserve(e.target); } });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
  revealEls.forEach(el => io.observe(el));
} else {
  revealEls.forEach(el => el.classList.add('in'));
}

// Animated stat counters
const stats = document.querySelectorAll('.stat-num');
if ('IntersectionObserver' in window && stats.length) {
  const sio = new IntersectionObserver((entries, obs) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const el = e.target;
      const m = el.textContent.trim().match(/^(\\D*)([\\d.]+)(.*)$/);
      if (m) {
        const pre = m[1], target = parseFloat(m[2]), suf = m[3];
        const dec = (m[2].indexOf('.') > -1) ? 1 : 0;
        let start = null;
        const step = ts => {
          if (!start) start = ts;
          const p = Math.min((ts - start) / 1100, 1);
          const val = (target * (0.5 - Math.cos(p * Math.PI) / 2)).toFixed(dec);
          el.textContent = pre + val + suf;
          if (p < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }
      obs.unobserve(el);
    });
  }, { threshold: 0.5 });
  stats.forEach(el => sio.observe(el));
}

// FAQ accordion
document.querySelectorAll('.faq-q').forEach(q => {
  q.addEventListener('click', () => {
    const item = q.closest('.faq-item');
    const isOpen = item.classList.contains('open');
    document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));
    if (!isOpen) item.classList.add('open');
  });
});

// Contact forms — Netlify Forms handles the actual POST submission natively.
// We only intercept to show a "Sending..." state for 600ms, then let it submit.
['contact-form', 'contact-form-index'].forEach(id => {
  const form = document.getElementById(id);
  if (form) {
    form.addEventListener('submit', e => {
      e.preventDefault();
      const btn = form.querySelector('button[type=submit]');
      btn.disabled = true;
      btn.textContent = 'Sending...';
      setTimeout(() => form.submit(), 600);
    });
  }
});

// Before/After slider
document.querySelectorAll('.ba-wrap').forEach(wrap => {
  const after   = wrap.querySelector('.ba-after');
  const afterImg = after ? after.querySelector('img') : null;
  const handle  = wrap.querySelector('.ba-handle');
  if (!after || !handle) return;
  let dragging = false;
  const syncImgWidth = () => { if (afterImg) afterImg.style.width = wrap.offsetWidth + 'px'; };
  syncImgWidth();
  window.addEventListener('resize', syncImgWidth);
  const setPos = x => {
    const r = wrap.getBoundingClientRect();
    const pct = Math.min(Math.max((x - r.left) / r.width * 100, 5), 95);
    after.style.width  = pct + '%';
    handle.style.left  = pct + '%';
  };
  wrap.addEventListener('mousedown', e => { dragging = true; setPos(e.clientX); e.preventDefault(); });
  document.addEventListener('mousemove', e => { if (dragging) setPos(e.clientX); });
  document.addEventListener('mouseup', () => { dragging = false; });
  wrap.addEventListener('touchstart', e => { dragging = true; setPos(e.touches[0].clientX); }, { passive: true });
  document.addEventListener('touchmove', e => { if (dragging) setPos(e.touches[0].clientX); }, { passive: true });
  document.addEventListener('touchend', () => { dragging = false; });
});

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  });
});
"""
    (site_dir / "js" / "main.js").write_text(js, encoding="utf-8")


# ── Shared HTML helpers ───────────────────────────────────────────────────────

def _nav(business: dict, active: str) -> str:
    name = business.get("name", "Our Business")
    phone = business.get("phone", "")
    pages = [("index.html","Home"), ("services.html","Services"),
             ("about.html","About"), ("contact.html","Contact"),
             ("reviews.html","Reviews")]
    links = "\n".join(
        f'<li><a href="{p}" {"style=color:white" if p.split(".")[0]==active else ""}>{label}</a></li>'
        for p, label in pages
    )
    cta = f'<a href="tel:{phone}" class="btn btn-primary btn-sm nav-cta">📞 Call Now</a>' if phone else \
          '<a href="contact.html" class="btn btn-primary btn-sm nav-cta">Get a Quote</a>'
    short = name.split()[0] if name else "Business"
    return f"""<nav>
  <div class="container nav-inner">
    <a href="index.html" class="nav-logo">{_esc(short)}<span>.</span></a>
    <ul class="nav-links">{links}</ul>
    {cta}
    <button class="nav-toggle" aria-label="Menu">
      <span></span><span></span><span></span>
    </button>
  </div>
</nav>"""


def _footer(business: dict) -> str:
    name    = business.get("name", "Our Business")
    city    = business.get("city", "BC")
    phone   = business.get("phone", "")
    address = business.get("address", "")
    year    = datetime.now().year
    cats    = business.get("categories") or [business.get("category", "services")]
    cat     = cats[0] if cats else "services"

    phone_html = f'<li><a href="tel:{phone}">{_esc(phone)}</a></li>' if phone else ""
    addr_html  = f'<li>{_esc(address)}</li>' if address else ""

    return f"""<footer>
  <div class="container">
    <div class="footer-grid">
      <div>
        <div class="footer-brand">{_esc(name.split()[0])}<span>.</span></div>
        <p class="footer-desc">Professional {_esc(cat)} services in {_esc(city)}, BC. Licensed, insured, and committed to quality work.</p>
      </div>
      <div class="footer-col">
        <h4>Pages</h4>
        <ul class="footer-links">
          <li><a href="index.html">Home</a></li>
          <li><a href="services.html">Services</a></li>
          <li><a href="about.html">About</a></li>
          <li><a href="contact.html">Contact</a></li>
          <li><a href="reviews.html">Reviews</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>Contact</h4>
        <ul class="footer-links">
          {phone_html}
          {addr_html}
          <li>{_esc(city)}, BC, Canada</li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <span>&copy; {year} {_esc(name)}. All rights reserved.</span>
      <span class="footer-credit">Site by <a href="https://pacificwebbuilder.com" target="_blank" rel="noopener">Pacific Web Builder</a></span>
      <span>Serving {_esc(city)}, BC</span>
    </div>
  </div>
</footer>
{_mobile_callbar(business)}
<script src="js/main.js"></script>"""


def _mobile_callbar(business: dict) -> str:
    """Fixed bottom call/quote bar shown on phones - a key conversion feature."""
    phone = business.get("phone", "")
    if phone:
        return f"""<div class="mobile-callbar">
  <a href="tel:{_esc(phone)}" class="btn btn-primary">📞 Call Now</a>
  <a href="contact.html" class="btn btn-outline">Get a Quote</a>
</div>"""
    return """<div class="mobile-callbar">
  <a href="contact.html" class="btn btn-primary">Get a Free Quote</a>
</div>"""


def _head(title: str, description: str, business: dict) -> str:
    name = business.get("name", "Business")
    city = business.get("city", "BC")
    cats = business.get("categories") or [business.get("category", "services")]
    cat  = cats[0] if cats else "services"

    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": name,
        "description": description,
        "address": {
            "@type": "PostalAddress",
            "addressLocality": city,
            "addressRegion": "BC",
            "addressCountry": "CA"
        },
        "areaServed": city,
    }
    if business.get("phone"):
        schema["telephone"] = business["phone"]
    if business.get("address"):
        schema["address"]["streetAddress"] = business["address"]

    return f"""<!DOCTYPE html>
<html lang="en-CA">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="theme-color" content="#0d1b2a" />
  <title>{_esc(title)}</title>
  <meta name="description" content="{_esc(description)}" />
  <meta property="og:title" content="{_esc(title)}" />
  <meta property="og:description" content="{_esc(description)}" />
  <meta property="og:type" content="website" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=Fraunces:wght@500;600;700&family=Poppins:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&family=Playfair+Display:wght@500;600;700&family=Cormorant+Garamond:wght@500;600;700&family=Anton&family=Spectral:wght@400;500;600&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="css/style.css" />
  <script type="application/ld+json">{json.dumps(schema)}</script>
  <!-- GA4: replace G-XXXXXXXXXX with your Measurement ID -->
  <!-- <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script> -->
</head>
<body class="theme-{_esc(business.get('_theme', {}).get('name', 'modern') if isinstance(business.get('_theme'), dict) else 'modern')}">"""


def _esc(s) -> str:
    # Explicitly allow 0 / 0.0 / False to pass through as their string form.
    # Only None and empty-string should collapse to "".
    if s is None or s == "":
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ── Filler images ───────────────────────────────────────────────────────────

# Maps a business category to good stock-photo search keywords so the filler
# images actually match the type of business.
# A single strong tag per business category. loremflickr matches photos far
# more reliably with one specific tag than with several OR'd together.
_IMG_KEYWORDS = {
    "plumber":      "plumbing",
    "plumbing":     "plumbing",
    "electrician":  "electrician",
    "electrical":   "electrician",
    "landscaper":   "landscaping",
    "landscaping":  "landscaping",
    "garden":       "garden",
    "nursery":      "plant-nursery",
    "hvac":         "hvac",
    "heating":      "hvac",
    "roofer":       "roofing",
    "roofing":      "roofing",
    "painter":      "house-painting",
    "painting":     "house-painting",
    "cleaning":     "house-cleaning",
    "salon":        "hair-salon",
    "barber":       "barbershop",
    "spa":          "day-spa",
    "dentist":      "dentist",
    "restaurant":   "restaurant",
    "cafe":         "coffee-shop",
    "bakery":       "bakery",
    "mechanic":     "auto-repair",
    "auto":         "auto-repair",
    "fitness":      "gym",
    "construction": "construction-site",
    "contractor":   "construction-site",
}

# Maps words found in a SERVICE name to a specific photo tag, so each card gets
# a relevant image instead of all cards sharing the business category.
_SERVICE_IMG_KEYWORDS = {
    "lawn":        "lawn-mowing",
    "mowing":      "lawn-mowing",
    "garden":      "flower-garden",
    "planting":    "flower-garden",
    "hardscap":    "stone-patio",
    "patio":       "stone-patio",
    "paving":      "stone-patio",
    "tree":        "tree-pruning",
    "shrub":       "garden-hedge",
    "hedge":       "garden-hedge",
    "irrigation":  "garden-sprinkler",
    "sprinkler":   "garden-sprinkler",
    "cleanup":     "raking-leaves",
    "seasonal":    "raking-leaves",
    "drain":       "plumbing",
    "pipe":        "plumbing",
    "leak":        "plumbing",
    "wiring":      "electrician",
    "lighting":    "light-fixture",
    "panel":       "electrician",
    "roof":        "roofing",
    "gutter":      "roofing",
    "paint":       "house-painting",
    "haircut":     "haircut",
    "color":       "hair-salon",
    "massage":     "massage",
    "facial":      "day-spa",
    "repair":      "repair-tools",
    "install":     "repair-tools",
    "maintenance": "repair-tools",
}


def _img_keywords(category: str) -> str:
    cat = (category or "").lower()
    for key, kw in _IMG_KEYWORDS.items():
        if key in cat:
            return kw
    word = re.sub(r"[^a-z]+", "", cat.split()[0]) if cat.strip() else ""
    return word or "local-business"


def _service_img_keywords(service_name: str, fallback: str) -> str:
    name = (service_name or "").lower()
    for key, kw in _SERVICE_IMG_KEYWORDS.items():
        if key in name:
            return kw
    return fallback


def _img(keywords: str, w: int, h: int, seed: str = "") -> str:
    """
    Return a keyword-matched filler image URL. Uses loremflickr.com, which
    serves Creative-Commons photos matching the tag with no API key. A stable
    seed (e.g. service name) keeps the same image across rebuilds. The /all
    path segment forces every comma-separated tag to match, cutting down on
    unrelated results.
    """
    base = f"https://loremflickr.com/{w}/{h}/{keywords}/all"
    if seed:
        lock = abs(hash(seed)) % 9999
        return f"{base}?lock={lock}"
    return base


# ── Pages ─────────────────────────────────────────────────────────────────────

def _write_index(business: dict, profile: dict, content: dict, site_dir: Path,
                 customize: dict | None = None) -> None:
    customize = customize or {}
    name     = business.get("name", "Our Business")
    city     = business.get("city", "BC")
    phone    = business.get("phone", "")
    rating   = business.get("rating", "")
    reviews  = business.get("review_count", 0)
    headline = content.get("headline", f"Trusted Services in {city}")
    tagline  = content.get("tagline", "")
    cta      = content.get("cta_text", "Get a Free Quote")
    trust    = content.get("trust_line", f"Serving {city}, BC")
    services = content.get("services", [])[:6]
    faq      = content.get("faq", [])[:4]
    about    = content.get("about_paragraph", f"{name} proudly serves the {city} community.")
    meta     = content.get("meta_description", f"{name} - {city}, BC")

    phone_btn = f'<a href="tel:{phone}" class="btn btn-outline btn-lg">📞 Call Now</a>' if phone else ""

    cats     = business.get("categories") or [business.get("category", "")]
    category = cats[0] if cats else "service"
    keywords = _img_keywords(category)
    hero_img = customize.get("hero_image") or _img(keywords, 1600, 800, seed=name)
    service_images = customize.get("service_images") or {}
    theme    = business.get("_theme") if isinstance(business.get("_theme"), dict) else THEMES["modern"]
    hero_overlay = theme.get("hero_overlay", THEMES["modern"]["hero_overlay"])

    # --- Hero social proof pill ---
    if rating and reviews:
        proof_pill = f'<div class="hero-eyebrow"><span class="hero-star">⭐</span> {_esc(str(rating))} · {reviews}+ Reviews on Google</div>'
    else:
        proof_pill = '<div class="hero-eyebrow">✓ Licensed &amp; Insured in BC</div>'

    # --- Hero eyebrow label ---
    cat_label = category.title() if category else "Local Experts"
    hero_eyebrow_label = f"{_esc(city)}'s Trusted {_esc(cat_label)} Specialists"

    # --- Stats strip data ---
    # Years in business (rough heuristic: "10+" unless we can derive it)
    years_val = "10+"
    stats_items = [
        {"num": years_val, "label": "Years in Business"},
        {"num": f"{max(reviews, 100)}+" if reviews else "100+", "label": "Happy Customers"},
        {"num": "Same-Day", "label": "Response Available"},
        {"num": "25km", "label": "Service Radius"},
    ]

    stats_html = "\n".join(
        f'<div class="stat"><span class="stat-num">{_esc(s["num"])}</span><span class="stat-label">{_esc(s["label"])}</span></div>'
        for s in stats_items
    )

    # Before/After slider section (landscaper "fresh" theme only)
    ba_section = ""
    if theme.get("name") == "fresh":
        b1 = _img(keywords, 700, 460, seed=name + "-p1-before")
        a1 = _img(keywords, 700, 460, seed=name + "-p1-after")
        b2 = _img(keywords, 700, 460, seed=name + "-p2-before")
        a2 = _img(keywords, 700, 460, seed=name + "-p2-after")
        ba_section = f"""
  <!-- Before/After Slider (landscaper) -->
  <section class="section">
    <div class="container">
      <div class="section-head reveal">
        <p class="eyebrow">Our Work</p>
        <h2>Before &amp; After</h2>
        <p>Drag the handle to see the transformation. Real projects, real results.</p>
      </div>
      <div class="ba-grid">
        <div class="ba-wrap">
          <img src="{_esc(b1)}" alt="Before landscaping project" loading="lazy" />
          <div class="ba-after"><img src="{_esc(a1)}" alt="After landscaping project" loading="lazy" /></div>
          <div class="ba-handle"><div class="ba-btn">&#8596;</div></div>
          <span class="ba-label ba-label-before">Before</span>
          <span class="ba-label ba-label-after">After</span>
        </div>
        <div class="ba-wrap">
          <img src="{_esc(b2)}" alt="Before garden design" loading="lazy" />
          <div class="ba-after"><img src="{_esc(a2)}" alt="After garden design" loading="lazy" /></div>
          <div class="ba-handle"><div class="ba-btn">&#8596;</div></div>
          <span class="ba-label ba-label-before">Before</span>
          <span class="ba-label ba-label-after">After</span>
        </div>
      </div>
    </div>
  </section>"""

    def _service_card(s: dict) -> str:
        sname = s.get("name", "")
        img_src = service_images.get(sname) or _img(
            _service_img_keywords(sname, keywords), 400, 260, seed=sname)
        return f"""<div class="service-card">
  <img class="service-img" src="{_esc(img_src)}" alt="{_esc(sname or 'Service')}" loading="lazy" />
  <div class="service-card-body">
    <div class="service-icon">{_esc(s.get("icon","🔧"))}</div>
    <h3>{_esc(sname or "Service")}</h3>
    <p>{_esc(s.get("description",""))}</p>
    <a href="services.html" class="service-learn-more">Learn more →</a>
  </div>
</div>"""

    service_cards = "\n".join(_service_card(s) for s in services)

    faq_items = "\n".join(
        f"""<div class="faq-item">
  <div class="faq-q">{_esc(f.get("q",""))} <span class="arrow">▼</span></div>
  <div class="faq-a">{_esc(f.get("a",""))}</div>
</div>"""
        for f in faq
    )

    # --- Testimonials: customize reviews > profile reviews > placeholders ---
    real_reviews = []
    testimonials_comment = ""
    cust_reviews = customize.get("reviews") or []
    if cust_reviews:
        real_reviews = [_normalize_review(r, city) for r in cust_reviews][:3]
    else:
        gp = profile.get("google_places", {})
        if isinstance(gp, dict) and gp.get("reviews"):
            real_reviews = gp["reviews"][:3]

    if not real_reviews:
        # Placeholder reviews — clearly marked in HTML comment
        trade_noun = category.lower()
        real_reviews = [
            {"author": "Sarah M.", "location": "Victoria, BC", "rating": 5,
             "text": f"Absolutely thrilled with the work. The team was prompt, professional, and the {trade_noun} quality was outstanding. I've already referred two neighbours."},
            {"author": "David K.", "location": "Saanich, BC", "rating": 5,
             "text": f"Best {trade_noun} experience I've had in years. Fair pricing, quality work, and they left the site spotless. Will be calling them again."},
            {"author": "Linda T.", "location": "Oak Bay, BC", "rating": 5,
             "text": f"Called in the morning, they were here by noon. Fixed everything quickly and explained the whole process. Incredibly impressed."},
        ]
        testimonials_comment = "<!-- PLACEHOLDER reviews: replace with real customer quotes once available -->"
    else:
        testimonials_comment = ""

    def _testimonial_card(r: dict) -> str:
        stars = "⭐" * int(r.get("rating") or 5)
        author = r.get("author", "Happy Customer")
        loc    = r.get("location", f"{city}, BC")
        text   = r.get("text", "Great service!")
        return f"""<div class="testimonial-card">
  <div class="testimonial-stars">{stars}</div>
  <p class="testimonial-quote">{_esc(text)}</p>
  <div class="testimonial-meta">
    <div>
      <div class="testimonial-author">{_esc(author)}</div>
      <div class="testimonial-location">{_esc(loc)}</div>
    </div>
    <div class="testimonial-g-badge" title="Google Review">G</div>
  </div>
</div>"""

    testimonial_cards = "\n".join(_testimonial_card(r) for r in real_reviews[:3])

    # --- About teaser ---
    about_img = _img(keywords, 700, 560, seed=name + "-about")
    badge_text = "25+ Years<br>Experience"

    # --- CTA phone ---
    phone_cta_html = ""
    if phone:
        phone_cta_html = f'<a href="tel:{phone}" class="cta-phone">{_esc(phone)}</a>'

    html = _head(f"{name} | {city}, BC", meta, business)
    html += _nav(business, "index")
    html += f"""
<main>
  <!-- Hero -->
  <section class="hero" style="background-image:{hero_overlay}, url('{_esc(hero_img)}');background-size:cover;background-position:center top;">
    <div class="container">
      {proof_pill}
      <p class="eyebrow" style="color:rgba(255,255,255,0.55);margin-bottom:0.5rem">{hero_eyebrow_label}</p>
      <h1>{_esc(headline)}</h1>
      <p class="hero-sub">{_esc(tagline)}</p>
      <div class="hero-actions">
        <a href="contact.html" class="btn btn-primary btn-lg">{_esc(cta)}</a>
        {phone_btn}
      </div>
    </div>
    <div class="trust-bar">
      <div class="container">
        <div class="trust-items">
          <span class="trust-item"><span class="check">✓</span> Licensed &amp; Insured</span>
          <span class="trust-item"><span class="check">✓</span> Free Estimates</span>
          <span class="trust-item"><span class="check">✓</span> {_esc(trust)}</span>
        </div>
      </div>
    </div>
  </section>

  <!-- Stats Strip -->
  <section class="stats-strip">
    <div class="container">
      <div class="stats-grid">
        {stats_html}
      </div>
    </div>
  </section>

  <!-- Services -->
  <section class="section">
    <div class="container">
      <div class="section-head reveal">
        <p class="eyebrow">What We Do</p>
        <h2>Our Services</h2>
        <p>Everything you need, handled by experienced professionals.</p>
      </div>
      <div class="services-grid">{service_cards}</div>
      <div style="text-align:center;margin-top:2.5rem">
        <a href="services.html" class="btn btn-outline">View All Services →</a>
      </div>
    </div>
  </section>

  {ba_section}

  <!-- About Teaser Split -->
  <section class="section section-alt">
    <div class="container">
      <div class="about-split">
        <div class="about-split-img-wrap">
          <img class="about-split-img" src="{_esc(about_img)}" alt="{_esc(name)} team" loading="lazy" />
          <div class="about-split-badge">{badge_text}</div>
        </div>
        <div class="about-split-content">
          <p class="eyebrow">About Us</p>
          <h2>Trusted by {_esc(city)} Families &amp; Businesses</h2>
          <p>{_esc(about)}</p>
          <ul class="about-checklist">
            <li><span class="check-icon">✓</span> Fully licensed and insured in BC</li>
            <li><span class="check-icon">✓</span> Free, no-obligation estimates</li>
            <li><span class="check-icon">✓</span> Local team — we live in {_esc(city)} too</li>
          </ul>
          <a href="about.html" class="btn btn-primary">Meet Our Team →</a>
        </div>
      </div>
    </div>
  </section>

  <!-- Testimonials Strip -->
  <section class="section testimonials-strip">
    <div class="container">
      <div class="section-head reveal">
        <p class="eyebrow">What Customers Say</p>
        <h2>Trusted by the Community</h2>
        <p>Real reviews from real {_esc(city)} neighbours.</p>
      </div>
      {testimonials_comment}
      <div class="testimonials-grid">
        {testimonial_cards}
      </div>
      <div style="text-align:center;margin-top:2.25rem">
        <a href="reviews.html" class="btn btn-outline">Read All Reviews →</a>
      </div>
    </div>
  </section>

  <!-- FAQ -->
  {f'''<section class="section">
    <div class="container">
      <div class="section-head reveal">
        <p class="eyebrow">Got Questions?</p>
        <h2>Frequently Asked Questions</h2>
      </div>
      <div class="faq-list">{faq_items}</div>
    </div>
  </section>''' if faq_items else ""}

  <!-- CTA Banner -->
  <section class="cta-banner">
    <div class="container">
      <h2>Ready to Get Started?</h2>
      {phone_cta_html}
      <p>Contact us today for a free, no-obligation quote. Serving {_esc(city)} and surrounding area.</p>
      <form id="contact-form-index" name="contact-index" data-netlify="true" method="POST" style="max-width:480px;margin:1.5rem auto 0;display:flex;flex-direction:column;gap:0.75rem;">
        <input type="hidden" name="form-name" value="contact-index" />
        <input type="text" name="name" placeholder="Your name" required style="padding:0.8rem 1rem;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.1);color:#fff;font-size:1rem;backdrop-filter:blur(6px);" />
        <input type="tel" name="phone" placeholder="Phone number" style="padding:0.8rem 1rem;border-radius:8px;border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.1);color:#fff;font-size:1rem;backdrop-filter:blur(6px);" />
        <button type="submit" class="btn btn-white btn-lg" style="width:100%">{_esc(cta)}</button>
        <p class="form-note" style="color:rgba(255,255,255,0.55);">We'll respond within 24 hours.</p>
      </form>
      <p class="cta-trust-note" style="margin-top:1rem;">No obligation &nbsp;·&nbsp; Fast response &nbsp;·&nbsp; Local experts</p>
    </div>
  </section>
</main>
"""
    html += _footer(business)
    html += "\n</body>\n</html>"
    (site_dir / "index.html").write_text(html, encoding="utf-8")


def _write_services(business: dict, content: dict, site_dir: Path) -> None:
    name     = business.get("name", "Our Business")
    city     = business.get("city", "BC")
    phone    = business.get("phone", "")
    services = content.get("services", [])
    cta      = content.get("cta_text", "Get a Free Quote")
    tagline  = content.get("tagline", f"Professional solutions for every need, delivered right in {city}.")
    meta     = f"Services offered by {name} in {city}, BC. Professional, licensed, and insured."

    cats     = business.get("categories") or [business.get("category", "")]
    category = cats[0] if cats else "service"
    keywords = _img_keywords(category)

    # Service cards — 2-col desktop grid with accent-bar hover animation
    def _svc_card(s: dict) -> str:
        sname = s.get("name", "Service")
        img_src = _img(_service_img_keywords(sname, keywords), 500, 300, seed=sname)
        return f"""<div class="service-card">
  <img class="service-img" src="{_esc(img_src)}" alt="{_esc(sname)}" loading="lazy" />
  <div class="service-card-body">
    <div class="service-icon">{_esc(s.get("icon","🔧"))}</div>
    <h3>{_esc(sname)}</h3>
    <p>{_esc(s.get("description",""))}</p>
    <a href="contact.html" class="service-learn-more">Get a Quote →</a>
  </div>
</div>"""

    cards = "\n".join(_svc_card(s) for s in services)

    phone_cta_html = ""
    if phone:
        phone_cta_html = f'<a href="tel:{phone}" class="cta-phone">{_esc(phone)}</a>'

    html  = _head(f"Services | {name}", meta, business)
    html += _nav(business, "services")
    html += f"""
<main>
  <div class="page-hero">
    <div class="container">
      <p class="eyebrow">What We Offer</p>
      <h1>Our Services</h1>
      <p>{_esc(tagline)}</p>
    </div>
  </div>

  <section class="section">
    <div class="container">
      <div class="section-head reveal">
        <p class="eyebrow">Expert Solutions</p>
        <h2>Everything You Need</h2>
        <p>From routine maintenance to complex projects — we handle it all with the same care and professionalism.</p>
      </div>
      <div class="services-grid-2col">{cards}</div>
    </div>
  </section>

  <!-- Trust strip -->
  <div class="services-trust-strip">
    <div class="container">
      <div class="services-trust-grid">
        <div class="services-trust-item">
          <div class="trust-icon">🛡️</div>
          <h4>Licensed &amp; Insured</h4>
          <p>Fully licensed in BC and insured for your complete peace of mind.</p>
        </div>
        <div class="services-trust-item">
          <div class="trust-icon">📋</div>
          <h4>Free Estimates</h4>
          <p>No-obligation quotes so you know exactly what to expect before we start.</p>
        </div>
        <div class="services-trust-item">
          <div class="trust-icon">📍</div>
          <h4>Local to {_esc(city)}</h4>
          <p>We live and work right here in {_esc(city)} — we're your neighbours.</p>
        </div>
      </div>
    </div>
  </div>

  <!-- CTA Banner -->
  <section class="cta-banner">
    <div class="container">
      <h2>Not Sure What You Need?</h2>
      {phone_cta_html}
      <p>Give us a call or send a message — we'll help you figure out the best solution for your situation.</p>
      <div class="cta-actions">
        <a href="contact.html" class="btn btn-white btn-lg">{_esc(cta)}</a>
        {f'<a href="tel:{phone}" class="btn btn-outline btn-lg">📞 Call Now</a>' if phone else ""}
      </div>
      <p class="cta-trust-note">No obligation &nbsp;·&nbsp; Fast response &nbsp;·&nbsp; Local experts</p>
    </div>
  </section>
</main>
"""
    html += _footer(business)
    html += "\n</body>\n</html>"
    (site_dir / "services.html").write_text(html, encoding="utf-8")


def _write_about(business: dict, content: dict, site_dir: Path) -> None:
    name    = business.get("name", "Our Business")
    city    = business.get("city", "BC")
    phone   = business.get("phone", "")
    rating  = business.get("rating", "")
    reviews = business.get("review_count", 0)
    about   = content.get("about_paragraph", f"{name} proudly serves the {city} community.")
    tagline = content.get("tagline", f"Your trusted local service experts in {city}, BC.")
    trust   = content.get("trust_line", "")
    meta    = f"About {name} - Your trusted local service provider in {city}, BC."

    cats = business.get("categories") or [business.get("category", "services")]
    cat  = cats[0] if cats else "services"
    keywords = _img_keywords(cat)

    # Team photo with keyword "portrait", different seeds
    team_photo_1 = _img("portrait", 300, 300, seed=name + "-team1")
    team_photo_2 = _img("portrait", 300, 300, seed=name + "-team2")
    team_photo_3 = _img("portrait", 300, 300, seed=name + "-team3")

    # About team photo
    team_img = _img(keywords, 600, 500, seed=name + "-team")

    # Stats strip values
    years_serving = "10+"
    happy_count   = f"{max(reviews, 100)}+" if reviews else "200+"
    review_count  = f"{reviews}+" if reviews else "50+"
    star_rating   = str(rating) if rating else "5.0"

    stats_html = f"""<div class="stats-grid">
  <div><span class="stat-num">{_esc(years_serving)}</span><span class="stat-label">Years Serving {_esc(city)}</span></div>
  <div><span class="stat-num">{_esc(happy_count)}</span><span class="stat-label">Happy Customers</span></div>
  <div><span class="stat-num">{_esc(star_rating)}★</span><span class="stat-label">Average Rating</span></div>
  <div><span class="stat-num">{_esc(review_count)}</span><span class="stat-label">5-Star Reviews</span></div>
</div>"""

    # Trade noun for team roles
    trade_nouns = {
        "landscaper": "Landscaper", "plumber": "Plumber",
        "electrician": "Electrician", "roofer": "Roofer",
        "painter": "Painter", "mechanic": "Mechanic",
        "contractor": "Contractor", "barber": "Barber",
        "cleaner": "Cleaner", "hvac": "Technician",
    }
    cat_lower = cat.lower()
    lead_role = next((v for k, v in trade_nouns.items() if k in cat_lower), cat.title())

    html  = _head(f"About Us | {name}", meta, business)
    html += _nav(business, "about")
    html += f"""
<main>
  <div class="page-hero">
    <div class="container">
      <p class="eyebrow">Who We Are</p>
      <h1>About Us</h1>
      <p>{_esc(tagline)}</p>
    </div>
  </div>

  <!-- Our Story split layout -->
  <section class="section">
    <div class="container">
      <div class="about-split">
        <div class="about-split-img-wrap">
          <img class="about-split-img" src="{_esc(team_img)}" alt="{_esc(name)} team" loading="lazy" style="height:500px" />
          <div class="about-split-badge">Locally<br>Owned</div>
        </div>
        <div class="about-split-content">
          <p class="eyebrow">Our Story</p>
          <h2>Our Story</h2>
          <p>{_esc(about)}</p>
          <p>We believe in honest, transparent service — you'll always know what to expect before we start any job. Our team is background-checked, fully insured, and committed to leaving your property better than we found it.</p>
          {f'<p><strong>{_esc(trust)}</strong></p>' if trust else ""}
          <ul class="about-checklist">
            <li><span class="check-icon">✓</span> Fully licensed and insured in BC</li>
            <li><span class="check-icon">✓</span> Free, no-obligation estimates</li>
            <li><span class="check-icon">✓</span> Local team — we live in {_esc(city)} too</li>
            <li><span class="check-icon">✓</span> Satisfaction guaranteed on every job</li>
          </ul>
          <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-top:0.5rem">
            <a href="contact.html" class="btn btn-primary">Get a Free Quote</a>
            {f'<a href="tel:{phone}" class="btn btn-outline">📞 Call Us</a>' if phone else ""}
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Stats strip -->
  <section class="stats-strip">
    <div class="container">
      {stats_html}
    </div>
  </section>

  <!-- Our Values -->
  <section class="section section-alt">
    <div class="container">
      <div class="section-head reveal">
        <p class="eyebrow">What Drives Us</p>
        <h2>Our Values</h2>
      </div>
      <div class="why-grid">
        <div class="why-item"><div class="why-icon">🤝</div><h3>Integrity</h3><p>We say what we mean and do what we say.</p></div>
        <div class="why-item"><div class="why-icon">🔧</div><h3>Craftsmanship</h3><p>Every job done right — no shortcuts, no compromises.</p></div>
        <div class="why-item"><div class="why-icon">🌿</div><h3>Community</h3><p>We live here too. {_esc(city)} is our home.</p></div>
        <div class="why-item"><div class="why-icon">📞</div><h3>Responsiveness</h3><p>Fast replies and clear communication, always.</p></div>
      </div>
    </div>
  </section>

  <!-- Meet the team -->
  <section class="section">
    <div class="container">
      <div class="section-head reveal">
        <p class="eyebrow">The People Behind the Work</p>
        <h2>Meet the Team</h2>
        <p>Experienced, friendly professionals who take pride in every job.</p>
      </div>
      <!-- PLACEHOLDER team cards: replace names, roles, and photos with real team members -->
      <div class="team-grid">
        <div class="team-card">
          <img class="team-photo" src="{_esc(team_photo_1)}" alt="Team member" loading="lazy" />
          <h4>Team Member</h4>
          <p>Lead {_esc(lead_role)}</p>
        </div>
        <div class="team-card">
          <img class="team-photo" src="{_esc(team_photo_2)}" alt="Team member" loading="lazy" />
          <h4>Team Member</h4>
          <p>{_esc(lead_role)} &amp; Estimator</p>
        </div>
        <div class="team-card">
          <img class="team-photo" src="{_esc(team_photo_3)}" alt="Team member" loading="lazy" />
          <h4>Team Member</h4>
          <p>Customer Relations</p>
        </div>
      </div>
      <!-- END PLACEHOLDER team cards -->
    </div>
  </section>

  <!-- CTA Banner -->
  <section class="cta-banner">
    <div class="container">
      <h2>Ready to Work Together?</h2>
      {f'<a href="tel:{phone}" class="cta-phone">{_esc(phone)}</a>' if phone else ""}
      <p>Get in touch today for a free, no-obligation estimate. We'd love to help.</p>
      <div class="cta-actions">
        <a href="contact.html" class="btn btn-white btn-lg">Get a Free Quote</a>
        {f'<a href="tel:{phone}" class="btn btn-outline btn-lg">📞 Call Us</a>' if phone else ""}
      </div>
      <p class="cta-trust-note">Licensed &amp; Insured &nbsp;·&nbsp; Local {_esc(city)} Team &nbsp;·&nbsp; No Obligation</p>
    </div>
  </section>
</main>
"""
    html += _footer(business)
    html += "\n</body>\n</html>"
    (site_dir / "about.html").write_text(html, encoding="utf-8")


def _write_contact(business: dict, content: dict, site_dir: Path) -> None:
    import urllib.parse
    name    = business.get("name", "Our Business")
    city    = business.get("city", "BC")
    phone   = business.get("phone", "")
    address = business.get("address", "")
    cta     = content.get("cta_text", "Get a Free Quote")
    services = content.get("services", [])
    meta    = f"Contact {name} in {city}, BC. Call or send a message for a free estimate."

    maps_query = urllib.parse.quote_plus(f"{name} {city} BC")
    maps_url   = f"https://www.google.com/maps/search/{maps_query}"

    service_options = "\n".join(
        f'<option value="{_esc(s.get("name",""))}">{_esc(s.get("name",""))}</option>'
        for s in services
    )

    # Phone block (large, accent-coloured, tappable)
    phone_block = ""
    if phone:
        phone_block = f"""<div>
  <p class="eyebrow" style="margin-bottom:0.3rem">Call Us</p>
  <a href="tel:{phone}" class="contact-phone">{_esc(phone)}</a>
</div>"""

    # Address block
    addr_block = ""
    if address:
        addr_block = f"""<div>
  <p class="eyebrow" style="margin-bottom:0.3rem">Address</p>
  <p style="font-weight:600;color:var(--navy);margin:0">{_esc(address)}</p>
</div>"""

    html  = _head(f"Contact Us | {name}", meta, business)
    html += _nav(business, "contact")
    html += f"""
<main>
  <div class="page-hero">
    <div class="container">
      <p class="eyebrow">Say Hello</p>
      <h1>Get in Touch</h1>
      <p>We'd love to hear from you. Free estimates, fast response, no obligation.</p>
    </div>
  </div>

  <section class="section">
    <div class="container">
      <div class="contact-grid">
        <!-- Contact form (left/main) -->
        <div class="form-card" style="order:1">
          <h3>{_esc(cta)}</h3>
          <form id="contact-form" name="contact-main" data-netlify="true" method="POST">
            <input type="hidden" name="form-name" value="contact-main" />
            <div class="form-row">
              <div class="form-group">
                <label for="fname">First Name</label>
                <input type="text" id="fname" name="first_name" placeholder="Jane" required />
              </div>
              <div class="form-group">
                <label for="lname">Last Name</label>
                <input type="text" id="lname" name="last_name" placeholder="Smith" required />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" placeholder="jane@example.com" required />
              </div>
              <div class="form-group">
                <label for="phone_input">Phone</label>
                <input type="tel" id="phone_input" name="phone" placeholder="(250) 555-0100" />
              </div>
            </div>
            <div class="form-group">
              <label for="service">Service Needed</label>
              <select id="service" name="service">
                <option value="">Select a service...</option>
                {service_options}
                <option value="other">Other / Not Sure</option>
              </select>
            </div>
            <div class="form-group">
              <label for="message">Tell Us More</label>
              <textarea id="message" name="message" placeholder="Describe your project or issue..."></textarea>
            </div>
            <button type="submit" class="btn btn-primary" style="width:100%">Send Message</button>
            <p class="form-note">We'll respond within 24 hours.</p>
          </form>
        </div>

        <!-- Contact info panel (right) -->
        <div class="contact-info-panel" style="order:2">
          <h3>Contact Info</h3>

          {phone_block}

          {addr_block}

          <!-- Business hours — replace with your actual hours -->
          <div>
            <p class="eyebrow" style="margin-bottom:0.3rem">Hours</p>
            <p style="color:var(--text);margin:0;font-size:0.97rem">
              Mon–Fri 8am–6pm<br>
              Sat 9am–3pm<br>
              <span style="color:var(--muted);font-size:0.88rem"><!-- Replace with your actual hours --></span>
            </p>
          </div>

          <div>
            <p class="eyebrow" style="margin-bottom:0.3rem">Service Area</p>
            <p style="color:var(--text);margin:0;font-size:0.97rem">{_esc(city)} and surrounding area</p>
          </div>

          <!-- Map placeholder — no API key needed, links to Google Maps search -->
          <div class="map-placeholder">
            <span style="font-size:1.5rem">📍</span>
            <span style="font-weight:600;color:var(--text)">{_esc(name)}, {_esc(city)}, BC</span>
            <a href="{_esc(maps_url)}" target="_blank" rel="noopener noreferrer">View on Google Maps</a>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Trust badges -->
  <div class="section-alt" style="padding:0">
    <div class="container">
      <div class="trust-badges">
        <div class="trust-badge"><span class="badge-icon">🛡️</span> Licensed &amp; Insured</div>
        <div class="trust-badge"><span class="badge-icon">⚡</span> Fast Response</div>
        <div class="trust-badge"><span class="badge-icon">📋</span> Free Estimates</div>
      </div>
    </div>
  </div>
</main>
"""
    html += _footer(business)
    html += "\n</body>\n</html>"
    (site_dir / "contact.html").write_text(html, encoding="utf-8")


def _write_reviews(business: dict, profile: dict, content: dict, site_dir: Path,
                   customize: dict | None = None) -> None:
    import urllib.parse
    customize = customize or {}
    name    = business.get("name", "Our Business")
    city    = business.get("city", "BC")
    rating  = business.get("rating", "")
    reviews = business.get("review_count", 0)
    meta    = f"Reviews for {name} in {city}, BC. See what our customers say."

    maps_query    = urllib.parse.quote_plus(f"{name} {city} BC")
    maps_url      = f"https://www.google.com/maps/search/{maps_query}"
    review_url    = f"https://www.google.com/maps/search/{maps_query}"

    # Customize reviews take precedence, then profile reviews, then placeholders
    real_reviews = []
    cust_reviews = customize.get("reviews") or []
    if cust_reviews:
        real_reviews = [_normalize_review(r, city) for r in cust_reviews][:6]
    else:
        gp = profile.get("google_places", {})
        if isinstance(gp, dict) and gp.get("reviews"):
            real_reviews = gp["reviews"][:6]

    # Fallback placeholder reviews
    placeholder_comment = ""
    if not real_reviews:
        real_reviews = [
            {"author": "Sarah M.", "rating": 5, "text": "Excellent service! They were prompt, professional, and did a fantastic job. Would highly recommend to anyone in the area.", "time": "2 months ago"},
            {"author": "David K.", "rating": 5, "text": "Best experience I've had. Fair pricing, quality work, and they cleaned up after themselves. Will definitely use again.", "time": "3 months ago"},
            {"author": "Linda T.", "rating": 5, "text": "Called in the morning and they were here by noon. Fixed the problem quickly and explained everything clearly. Very happy.", "time": "1 month ago"},
            {"author": "Mike R.", "rating": 4, "text": "Professional and courteous. The job was done right and on budget. Good communication throughout.", "time": "4 months ago"},
        ]
        placeholder_comment = "<!-- PLACEHOLDER reviews: replace with real customer quotes once available -->"

    def _review_card(r: dict) -> str:
        r_rating = int(r.get("rating") or 5)
        stars_html = "".join(
            f'<span style="color:#f5a623">★</span>' if i < r_rating
            else f'<span style="color:var(--border)">★</span>'
            for i in range(5)
        )
        time_str = r.get("time", "")
        return f"""<div class="review-card">
  <div class="stars" style="font-size:1.15rem;letter-spacing:1px">{stars_html}</div>
  <p class="review-text">"{_esc(r.get("text","Great service!"))}"</p>
  <div style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:0.5rem;margin-top:0.75rem">
    <div class="review-author" style="font-weight:700;font-size:0.92rem;color:var(--navy)">— {_esc(r.get("author","Happy Customer"))}</div>
    {f'<div style="font-size:0.8rem;color:var(--muted)">{_esc(time_str)}</div>' if time_str else ""}
  </div>
</div>"""

    cards = "\n".join(_review_card(r) for r in real_reviews)

    # Hero subtitle
    if rating:
        hero_subtitle = f"⭐ {_esc(str(rating))}/5 · {reviews}+ reviews on Google"
    else:
        hero_subtitle = "What our customers are saying"

    # Rating distribution summary bar (shown when review_count >= 10)
    summary_html = ""
    if reviews >= 10 and rating:
        try:
            avg = float(rating)
        except (TypeError, ValueError):
            avg = 4.5
        # Generate plausible distribution from average
        # avg ≈ 4.5 → mostly 5-star, some 4-star, tiny 3-star, none below
        def _dist(avg: float) -> dict:
            """Return plausible star distribution (0-100 pct) from average."""
            if avg >= 4.8:
                return {5: 85, 4: 12, 3: 2, 2: 1, 1: 0}
            elif avg >= 4.5:
                return {5: 70, 4: 20, 3: 6, 2: 2, 1: 2}
            elif avg >= 4.0:
                return {5: 55, 4: 28, 3: 10, 2: 4, 1: 3}
            elif avg >= 3.5:
                return {5: 40, 4: 30, 3: 18, 2: 7, 1: 5}
            else:
                return {5: 25, 4: 25, 3: 25, 2: 15, 1: 10}

        dist = _dist(avg)
        bar_rows = "\n".join(
            f"""<div class="rating-bar-row">
  <span style="min-width:28px">{stars}★</span>
  <div class="rating-bar-track"><div class="rating-bar-fill" style="width:{pct}%"></div></div>
  <span class="rating-bar-pct">{pct}%</span>
</div>"""
            for stars, pct in sorted(dist.items(), reverse=True)
        )
        summary_html = f"""<div class="review-summary">
  <h3 style="font-size:1rem;margin-bottom:0.75rem">Rating Breakdown</h3>
  {bar_rows}
</div>"""

    html  = _head(f"Reviews | {name}", meta, business)
    html += _nav(business, "reviews")
    html += f"""
<main>
  <div class="page-hero">
    <div class="container">
      <p class="eyebrow">Customer Feedback</p>
      <h1>What Our Customers Say</h1>
      <p>{hero_subtitle}</p>
    </div>
  </div>

  <section class="section">
    <div class="container">
      {summary_html}
      {placeholder_comment}
      <div class="reviews-grid">{cards}</div>
    </div>
  </section>

  <!-- Leave a review CTA -->
  <section class="section section-alt">
    <div class="container" style="text-align:center">
      <p class="eyebrow">Share Your Experience</p>
      <h2>Happy with Our Work?</h2>
      <p style="color:var(--muted);max-width:500px;margin:0 auto 1.75rem">Your review helps other {_esc(city)} residents find trusted local service. It only takes a minute!</p>
      <a href="{_esc(review_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-lg">Leave a Google Review →</a>
    </div>
  </section>

  <!-- CTA Banner -->
  <section class="cta-banner">
    <div class="container">
      <h2>Join Our Happy Customers</h2>
      <p>Experience the quality service that keeps {_esc(city)} residents coming back year after year.</p>
      <div class="cta-actions">
        <a href="contact.html" class="btn btn-white btn-lg">Get a Free Quote</a>
      </div>
      <p class="cta-trust-note">Licensed &amp; Insured &nbsp;·&nbsp; Free Estimates &nbsp;·&nbsp; Local {_esc(city)} Team</p>
    </div>
  </section>
</main>
"""
    html += _footer(business)
    html += "\n</body>\n</html>"
    (site_dir / "reviews.html").write_text(html, encoding="utf-8")


# ── SEO files ─────────────────────────────────────────────────────────────────

def _write_sitemap(business: dict, site_dir: Path) -> None:
    name = business.get("name", "business")
    slug = _slugify(name)
    base = f"https://{slug}.netlify.app"
    today = datetime.now().strftime("%Y-%m-%d")
    pages = ["index.html", "services.html", "about.html", "contact.html", "reviews.html"]
    urls  = "\n".join(
        f"  <url><loc>{base}/{p}</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq></url>"
        for p in pages
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>"""
    (site_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def _write_robots(site_dir: Path) -> None:
    (site_dir / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n",
        encoding="utf-8"
    )


def _copy_logo(profile_dir: str, site_dir: Path) -> None:
    assets = Path(profile_dir) / "assets"
    if not assets.exists():
        return
    for ext in ("logo.png", "logo.jpg", "logo.svg", "logo.img"):
        src = assets / ext
        if src.exists():
            import shutil
            shutil.copy2(src, site_dir / "images" / ext)
            print(f"[build] Logo copied: {ext}")
            return


# ── Utilities ─────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:60]
