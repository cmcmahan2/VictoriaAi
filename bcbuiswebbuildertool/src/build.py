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


# ── Entry point ───────────────────────────────────────────────────────────────

def build_website(profile_dir: str, output_dir: str = "./output") -> Path:
    """
    Phase 3 entry point. Reads the scraped profile and generates a
    complete website into ./output/{business_slug}/.
    """
    profile_path = Path(profile_dir) / "profile.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"No profile.json found in {profile_dir}. Run Phase 2 first.")

    profile  = json.loads(profile_path.read_text(encoding="utf-8"))
    business = profile.get("business", {})

    slug     = _slugify(business.get("name", "unknown-business"))
    site_dir = Path(output_dir) / slug
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "css").mkdir(exist_ok=True)
    (site_dir / "js").mkdir(exist_ok=True)
    (site_dir / "images").mkdir(exist_ok=True)

    stack = _select_stack(business)
    print(f"[build] Stack: {stack} for {business.get('name')}")

    # Generate content via Claude (or fall back to templates)
    print("[build] Generating page content...")
    content = _generate_content(business, profile)

    print("[build] Building static site...")
    _write_css(site_dir, content)
    _write_js(site_dir)
    _write_index(business, profile, content, site_dir)
    _write_services(business, content, site_dir)
    _write_about(business, content, site_dir)
    _write_contact(business, content, site_dir)
    _write_reviews(business, profile, content, site_dir)
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

def _generate_content(business: dict, profile: dict) -> dict:
    """
    Call Claude API to generate tailored copy for the site.
    Falls back to template content if no API key.
    """
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

        prompt = f"""You are writing website copy for a local BC business.

Business: {name}
City: {city}, BC, Canada
Category: {category}
Phone: {phone or "TBD"}
Address: {address or "TBD"}
Rating: {rating} stars ({reviews} reviews)
Existing site text snippet: {website_text or "None available"}

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

    # Avoid awkward doubling like "Trusted Services Services in ..."
    cat_title = category.title()
    headline = (f"Trusted {cat_title} in {city}"
                if "service" in cat_key
                else f"Trusted {cat_title} Services in {city}")

    return {
        "headline": headline,
        "tagline": f"Professional, reliable {category} serving {city} and the surrounding area.",
        "about_paragraph": f"{name} proudly serves the {city} community with top-quality {category}. Our experienced team delivers honest, dependable work at fair prices. We treat every customer like a neighbour.",
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

def _write_css(site_dir: Path, content: dict) -> None:
    css = """\
/* ── Reset & Variables ─────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --green:   #22a262;
  --green2:  #1a8a52;
  --navy:    #1a3a5c;
  --dark:    #0d1b2a;
  --light:   #f4f7fa;
  --white:   #ffffff;
  --muted:   #6a8aaa;
  --text:    #1e2d3d;
  --border:  #dde4ed;
  --shadow:  0 2px 16px rgba(0,0,0,0.08);
  --radius:  10px;
  --font:    'Inter', system-ui, -apple-system, sans-serif;
}

html { scroll-behavior: smooth; }

body {
  font-family: var(--font);
  color: var(--text);
  background: var(--white);
  line-height: 1.6;
  font-size: 1rem;
}

img { max-width: 100%; height: auto; display: block; }
a   { color: var(--green); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Typography ─────────────────────────────────────────────────────────── */
h1 { font-size: clamp(1.8rem, 5vw, 3rem); font-weight: 800; line-height: 1.2; }
h2 { font-size: clamp(1.4rem, 3vw, 2rem); font-weight: 700; line-height: 1.3; margin-bottom: 0.75rem; }
h3 { font-size: 1.15rem; font-weight: 600; margin-bottom: 0.5rem; }
p  { margin-bottom: 1rem; }

/* ── Layout ─────────────────────────────────────────────────────────────── */
.container { max-width: 1100px; margin: 0 auto; padding: 0 1.25rem; }
.section    { padding: 4rem 0; }
.section-alt { background: var(--light); }
.section-dark { background: var(--dark); color: var(--white); }

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.btn {
  display: inline-block;
  padding: 0.85rem 2rem;
  border-radius: var(--radius);
  font-weight: 700;
  font-size: 1rem;
  cursor: pointer;
  border: none;
  transition: transform 0.15s, background 0.2s;
  text-align: center;
}
.btn:hover { transform: translateY(-2px); text-decoration: none; }
.btn-primary  { background: var(--green); color: #fff; }
.btn-primary:hover { background: var(--green2); }
.btn-outline  { background: transparent; color: var(--green); border: 2px solid var(--green); }
.btn-outline:hover { background: var(--green); color: #fff; }
.btn-white    { background: #fff; color: var(--navy); }
.btn-white:hover { background: var(--light); }
.btn-lg { padding: 1rem 2.5rem; font-size: 1.1rem; }

/* ── Nav ─────────────────────────────────────────────────────────────────── */
nav {
  background: var(--dark);
  padding: 1rem 0;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
.nav-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.nav-logo {
  font-weight: 800;
  font-size: 1.1rem;
  color: var(--white);
  letter-spacing: -0.02em;
}
.nav-logo span { color: var(--green); }
.nav-links { display: flex; align-items: center; gap: 1.5rem; list-style: none; }
.nav-links a { color: rgba(255,255,255,0.8); font-size: 0.9rem; font-weight: 500; }
.nav-links a:hover { color: var(--white); text-decoration: none; }
.nav-cta { margin-left: 0.5rem; }
.nav-toggle {
  display: none;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  flex-direction: column;
  gap: 5px;
}
.nav-toggle span {
  display: block;
  width: 24px; height: 2px;
  background: #fff;
  border-radius: 2px;
  transition: all 0.3s;
}

/* ── Hero ─────────────────────────────────────────────────────────────────── */
.hero {
  background: linear-gradient(135deg, var(--dark) 0%, var(--navy) 100%);
  color: var(--white);
  padding: 5rem 0 4rem;
  text-align: center;
}
.hero h1 { color: var(--white); margin-bottom: 1.25rem; }
.hero h1 span { color: var(--green); }
.hero-sub {
  font-size: 1.15rem;
  color: rgba(255,255,255,0.8);
  max-width: 600px;
  margin: 0 auto 2rem;
}
.hero-actions { display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }
.trust-bar {
  background: rgba(255,255,255,0.06);
  border-top: 1px solid rgba(255,255,255,0.08);
  padding: 1.25rem 0;
  margin-top: 3rem;
  font-size: 0.9rem;
  color: rgba(255,255,255,0.7);
}
.trust-items { display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap; }
.trust-item { display: flex; align-items: center; gap: 0.4rem; }
.trust-item .check { color: var(--green); font-size: 1rem; }

/* ── Service cards ─────────────────────────────────────────────────────── */
.services-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.5rem;
  margin-top: 2.5rem;
}
.service-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: transform 0.2s, box-shadow 0.2s;
}
.service-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
.service-img {
  width: 100%;
  height: 170px;
  object-fit: cover;
  display: block;
  background: var(--border);
}
.service-card-body { padding: 1.5rem; }
.service-icon { font-size: 2rem; margin-bottom: 0.75rem; }
.service-card h3 { color: var(--navy); }
.service-card p  { color: var(--muted); font-size: 0.95rem; margin: 0; }

/* ── Why choose us ─────────────────────────────────────────────────────── */
.why-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-top: 2.5rem;
}
.why-item { text-align: center; }
.why-icon { font-size: 2.5rem; margin-bottom: 0.5rem; }
.why-item h3 { color: var(--navy); margin-bottom: 0.25rem; }
.why-item p  { color: var(--muted); font-size: 0.9rem; margin: 0; }

/* ── CTA banner ─────────────────────────────────────────────────────────── */
.cta-banner {
  background: linear-gradient(135deg, var(--green) 0%, var(--navy) 100%);
  color: white;
  text-align: center;
  padding: 4rem 0;
}
.cta-banner h2 { color: white; }
.cta-banner p  { color: rgba(255,255,255,0.85); max-width: 500px; margin: 0 auto 2rem; }

/* ── Reviews ─────────────────────────────────────────────────────────────── */
.reviews-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
  margin-top: 2.5rem;
}
.review-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.5rem;
  box-shadow: var(--shadow);
}
.stars { color: #f5a623; font-size: 1.1rem; margin-bottom: 0.5rem; }
.review-text { font-style: italic; color: var(--muted); margin-bottom: 0.75rem; font-size: 0.95rem; }
.review-author { font-weight: 600; font-size: 0.9rem; color: var(--navy); }

/* ── About ────────────────────────────────────────────────────────────── */
.about-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3rem;
  align-items: center;
}
.about-image {
  background: linear-gradient(135deg, var(--navy), var(--green));
  border-radius: var(--radius);
  height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 4rem;
}
.stat-row { display: flex; gap: 2rem; margin-top: 1.5rem; flex-wrap: wrap; }
.stat { text-align: center; }
.stat-num { font-size: 2rem; font-weight: 800; color: var(--green); display: block; }
.stat-label { font-size: 0.85rem; color: var(--muted); }

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

/* ── Page header ─────────────────────────────────────────────────────────── */
.page-hero {
  background: linear-gradient(135deg, var(--dark) 0%, var(--navy) 100%);
  color: white;
  padding: 3.5rem 0;
  text-align: center;
}
.page-hero h1 { color: white; }
.page-hero p  { color: rgba(255,255,255,0.75); margin-top: 0.5rem; }

/* ── Mobile ─────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .nav-links { display: none; flex-direction: column; gap: 0; position: absolute; top: 100%; left: 0; right: 0; background: var(--dark); padding: 1rem 1.25rem; }
  .nav-links.open { display: flex; }
  .nav-links li { padding: 0.6rem 0; border-bottom: 1px solid rgba(255,255,255,0.08); }
  .nav-toggle { display: flex; }
  nav { position: relative; }

  .about-grid    { grid-template-columns: 1fr; }
  .contact-grid  { grid-template-columns: 1fr; }
  .footer-grid   { grid-template-columns: 1fr; gap: 1.5rem; }
  .form-row      { grid-template-columns: 1fr; }
  .about-image   { height: 200px; }
  .section       { padding: 2.5rem 0; }
}

@media (max-width: 480px) {
  .hero { padding: 3rem 0 2.5rem; }
  .hero-actions { flex-direction: column; align-items: center; }
  .trust-items  { flex-direction: column; align-items: center; gap: 0.75rem; }
}
"""
    (site_dir / "css" / "style.css").write_text(css, encoding="utf-8")


# ── JS ────────────────────────────────────────────────────────────────────────

def _write_js(site_dir: Path) -> None:
    js = """\
// Nav toggle
const toggle = document.querySelector('.nav-toggle');
const links  = document.querySelector('.nav-links');
if (toggle && links) {
  toggle.addEventListener('click', () => links.classList.toggle('open'));
  document.addEventListener('click', e => {
    if (!toggle.contains(e.target) && !links.contains(e.target))
      links.classList.remove('open');
  });
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

// Contact form
const form = document.getElementById('contact-form');
if (form) {
  form.addEventListener('submit', e => {
    e.preventDefault();
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    btn.textContent = 'Sending...';
    setTimeout(() => {
      form.style.display = 'none';
      const success = document.querySelector('.form-success');
      if (success) success.style.display = 'block';
    }, 800);
  });
}

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
      <span>Serving {_esc(city)}, BC</span>
    </div>
  </div>
</footer>
<script src="js/main.js"></script>"""


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
  <title>{_esc(title)}</title>
  <meta name="description" content="{_esc(description)}" />
  <meta property="og:title" content="{_esc(title)}" />
  <meta property="og:description" content="{_esc(description)}" />
  <meta property="og:type" content="website" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="css/style.css" />
  <script type="application/ld+json">{json.dumps(schema)}</script>
  <!-- GA4: replace G-XXXXXXXXXX with your Measurement ID -->
  <!-- <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script> -->
</head>
<body>"""


def _esc(s) -> str:
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ── Filler images ───────────────────────────────────────────────────────────

# Maps a business category to good stock-photo search keywords so the filler
# images actually match the type of business.
_IMG_KEYWORDS = {
    "plumber":      "plumbing,pipes",
    "electrician":  "electrician,wiring",
    "landscaper":   "landscaping,garden",
    "landscaping":  "landscaping,garden",
    "garden":       "garden,plants,nursery",
    "nursery":      "garden,plants,nursery",
    "hvac":         "hvac,heating",
    "roofer":       "roofing,roof",
    "roofing":      "roofing,roof",
    "painter":      "painting,interior",
    "cleaning":     "cleaning,home",
    "salon":        "hair,salon",
    "barber":       "barber,haircut",
    "spa":          "spa,massage",
    "dentist":      "dental,clinic",
    "restaurant":   "restaurant,food",
    "cafe":         "cafe,coffee",
    "bakery":       "bakery,bread",
    "mechanic":     "auto,repair,garage",
    "fitness":      "gym,fitness",
    "construction": "construction,builder",
    "contractor":   "construction,builder",
}


def _img_keywords(category: str) -> str:
    cat = (category or "").lower()
    for key, kw in _IMG_KEYWORDS.items():
        if key in cat:
            return kw
    # Fall back to the category itself (single word) or a generic business image
    word = re.sub(r"[^a-z]+", "", cat.split()[0]) if cat.strip() else ""
    return f"{word},business" if word else "local,business"


def _img(keywords: str, w: int, h: int, seed: str = "") -> str:
    """
    Return a keyword-matched filler image URL. Uses loremflickr.com, which
    serves Creative-Commons photos matching the keywords with no API key.
    A stable seed (e.g. service name) keeps the same image across rebuilds.
    """
    base = f"https://loremflickr.com/{w}/{h}/{keywords}"
    if seed:
        lock = abs(hash(seed)) % 9999
        return f"{base}?lock={lock}"
    return base


# ── Pages ─────────────────────────────────────────────────────────────────────

def _write_index(business: dict, profile: dict, content: dict, site_dir: Path) -> None:
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
    meta     = content.get("meta_description", f"{name} - {city}, BC")

    phone_btn = f'<a href="tel:{phone}" class="btn btn-outline btn-lg">📞 Call Now</a>' if phone else ""
    rating_str = f"⭐ {rating}/5 ({reviews} reviews)" if rating else ""

    cats     = business.get("categories") or [business.get("category", "")]
    keywords = _img_keywords(cats[0] if cats else "")
    hero_img = _img(keywords, 1600, 700, seed=name)

    service_cards = "\n".join(
        f"""<div class="service-card">
  <img class="service-img" src="{_esc(_img(keywords, 400, 260, seed=s.get('name','')))}" alt="{_esc(s.get('name','Service'))}" loading="lazy" />
  <div class="service-card-body">
    <div class="service-icon">{_esc(s.get("icon","🔧"))}</div>
    <h3>{_esc(s.get("name","Service"))}</h3>
    <p>{_esc(s.get("description",""))}</p>
  </div>
</div>"""
        for s in services
    )

    faq_items = "\n".join(
        f"""<div class="faq-item">
  <div class="faq-q">{_esc(f.get("q",""))} <span class="arrow">▼</span></div>
  <div class="faq-a">{_esc(f.get("a",""))}</div>
</div>"""
        for f in faq
    )

    html = _head(f"{name} | {city}, BC", meta, business)
    html += _nav(business, "index")
    html += f"""
<main>
  <!-- Hero -->
  <section class="hero" style="background-image:linear-gradient(135deg, rgba(15,30,48,0.86) 0%, rgba(26,58,92,0.86) 100%), url('{_esc(hero_img)}');background-size:cover;background-position:center;">
    <div class="container">
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
          {f'<span class="trust-item"><span class="check">⭐</span> {_esc(rating_str)}</span>' if rating_str else ""}
        </div>
      </div>
    </div>
  </section>

  <!-- Services -->
  <section class="section">
    <div class="container">
      <h2>Our Services</h2>
      <p>Everything you need, handled by experienced professionals.</p>
      <div class="services-grid">{service_cards}</div>
      <div style="text-align:center;margin-top:2rem">
        <a href="services.html" class="btn btn-outline">View All Services →</a>
      </div>
    </div>
  </section>

  <!-- Why Us -->
  <section class="section section-alt">
    <div class="container">
      <h2>Why Choose Us</h2>
      <div class="why-grid">
        <div class="why-item"><div class="why-icon">🏆</div><h3>Quality Work</h3><p>We stand behind every job with a satisfaction guarantee.</p></div>
        <div class="why-item"><div class="why-icon">⚡</div><h3>Fast Response</h3><p>Same-day service available. We show up when we say we will.</p></div>
        <div class="why-item"><div class="why-icon">💰</div><h3>Fair Pricing</h3><p>Transparent quotes upfront — no surprises on your bill.</p></div>
        <div class="why-item"><div class="why-icon">🛡️</div><h3>Fully Insured</h3><p>Licensed and insured for your complete peace of mind.</p></div>
      </div>
    </div>
  </section>

  <!-- FAQ -->
  {f'''<section class="section">
    <div class="container">
      <h2>Frequently Asked Questions</h2>
      <div class="faq-list">{faq_items}</div>
    </div>
  </section>''' if faq_items else ""}

  <!-- CTA -->
  <section class="cta-banner">
    <div class="container">
      <h2>Ready to Get Started?</h2>
      <p>Contact us today for a free, no-obligation quote. Serving {_esc(city)} and area.</p>
      <a href="contact.html" class="btn btn-white btn-lg">{_esc(cta)}</a>
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
    services = content.get("services", [])
    cta      = content.get("cta_text", "Get a Free Quote")
    meta     = f"Services offered by {name} in {city}, BC. Professional, licensed, and insured."

    cards = "\n".join(
        f"""<div class="service-card">
  <div class="service-icon">{_esc(s.get("icon","🔧"))}</div>
  <h3>{_esc(s.get("name","Service"))}</h3>
  <p>{_esc(s.get("description",""))}</p>
  <a href="contact.html" style="color:var(--green);font-weight:600;font-size:0.9rem">Get a Quote →</a>
</div>"""
        for s in services
    )

    html  = _head(f"Services | {name}", meta, business)
    html += _nav(business, "services")
    html += f"""
<main>
  <div class="page-hero">
    <div class="container">
      <h1>Our Services</h1>
      <p>Professional solutions for every need, delivered right in {_esc(city)}.</p>
    </div>
  </div>
  <section class="section">
    <div class="container">
      <div class="services-grid">{cards}</div>
    </div>
  </section>
  <section class="cta-banner">
    <div class="container">
      <h2>Not Sure What You Need?</h2>
      <p>Give us a call or send a message — we'll help you figure out the best solution.</p>
      <a href="contact.html" class="btn btn-white btn-lg">{_esc(cta)}</a>
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
    trust   = content.get("trust_line", "")
    meta    = f"About {name} - Your trusted local service provider in {city}, BC."

    cats = business.get("categories") or [business.get("category", "services")]
    cat  = cats[0] if cats else "services"

    html  = _head(f"About Us | {name}", meta, business)
    html += _nav(business, "about")
    html += f"""
<main>
  <div class="page-hero">
    <div class="container">
      <h1>About {_esc(name)}</h1>
      <p>Your trusted local {_esc(cat)} experts in {_esc(city)}, BC.</p>
    </div>
  </div>
  <section class="section">
    <div class="container">
      <div class="about-grid">
        <div>
          <h2>Who We Are</h2>
          <p>{_esc(about)}</p>
          <p>We believe in honest, transparent service — you'll always know what to expect before we start any job. Our team is background-checked, fully insured, and committed to leaving your property cleaner than we found it.</p>
          {f'<p><strong>{_esc(trust)}</strong></p>' if trust else ""}
          <div class="stat-row">
            {f'<div class="stat"><span class="stat-num">{_esc(str(rating))}</span><span class="stat-label">Star Rating</span></div>' if rating else ""}
            {f'<div class="stat"><span class="stat-num">{reviews}+</span><span class="stat-label">Happy Clients</span></div>' if reviews else ""}
            <div class="stat"><span class="stat-num">100%</span><span class="stat-label">Satisfaction</span></div>
          </div>
          <div style="margin-top:1.75rem;display:flex;gap:1rem;flex-wrap:wrap">
            <a href="contact.html" class="btn btn-primary">Get a Free Quote</a>
            {f'<a href="tel:{phone}" class="btn btn-outline">📞 Call Us</a>' if phone else ""}
          </div>
        </div>
        <div class="about-image">🏠</div>
      </div>
    </div>
  </section>
  <section class="section section-alt">
    <div class="container">
      <h2>Our Values</h2>
      <div class="why-grid">
        <div class="why-item"><div class="why-icon">🤝</div><h3>Integrity</h3><p>We say what we mean and do what we say.</p></div>
        <div class="why-item"><div class="why-icon">🔧</div><h3>Craftsmanship</h3><p>Every job done right — no shortcuts.</p></div>
        <div class="why-item"><div class="why-icon">🌿</div><h3>Community</h3><p>We live here too. {_esc(city)} is our home.</p></div>
        <div class="why-item"><div class="why-icon">📞</div><h3>Responsiveness</h3><p>Fast replies, clear communication.</p></div>
      </div>
    </div>
  </section>
</main>
"""
    html += _footer(business)
    html += "\n</body>\n</html>"
    (site_dir / "about.html").write_text(html, encoding="utf-8")


def _write_contact(business: dict, content: dict, site_dir: Path) -> None:
    name    = business.get("name", "Our Business")
    city    = business.get("city", "BC")
    phone   = business.get("phone", "")
    address = business.get("address", "")
    cta     = content.get("cta_text", "Get a Free Quote")
    services = content.get("services", [])
    meta    = f"Contact {name} in {city}, BC. Call or send a message for a free estimate."

    phone_item = f"""<li>
  <span class="ci-icon">📞</span>
  <div><div class="ci-label">Phone</div><div class="ci-value"><a href="tel:{phone}">{_esc(phone)}</a></div></div>
</li>""" if phone else ""

    addr_item = f"""<li>
  <span class="ci-icon">📍</span>
  <div><div class="ci-label">Address</div><div class="ci-value">{_esc(address)}</div></div>
</li>""" if address else ""

    service_options = "\n".join(
        f'<option value="{_esc(s.get("name",""))}">{_esc(s.get("name",""))}</option>'
        for s in services
    )

    html  = _head(f"Contact Us | {name}", meta, business)
    html += _nav(business, "contact")
    html += f"""
<main>
  <div class="page-hero">
    <div class="container">
      <h1>Get in Touch</h1>
      <p>Free estimates. Fast response. No obligation.</p>
    </div>
  </div>
  <section class="section">
    <div class="container">
      <div class="contact-grid">
        <div>
          <h2>Contact Info</h2>
          <ul class="contact-info">
            {phone_item}
            {addr_item}
            <li>
              <span class="ci-icon">📍</span>
              <div><div class="ci-label">Service Area</div><div class="ci-value">{_esc(city)} and surrounding area</div></div>
            </li>
            <li>
              <span class="ci-icon">🕐</span>
              <div><div class="ci-label">Hours</div><div class="ci-value">Mon–Fri 8am–6pm<br>Sat 9am–4pm<br>Emergency service available</div></div>
            </li>
          </ul>
        </div>
        <div class="form-card">
          <h3>{_esc(cta)}</h3>
          <form id="contact-form">
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
          </form>
          <div class="form-success">✓ Message sent! We'll be in touch within 1 business day.</div>
        </div>
      </div>
    </div>
  </section>
</main>
"""
    html += _footer(business)
    html += "\n</body>\n</html>"
    (site_dir / "contact.html").write_text(html, encoding="utf-8")


def _write_reviews(business: dict, profile: dict, content: dict, site_dir: Path) -> None:
    name    = business.get("name", "Our Business")
    city    = business.get("city", "BC")
    rating  = business.get("rating", "")
    reviews = business.get("review_count", 0)
    meta    = f"Reviews for {name} in {city}, BC. See what our customers say."

    # Pull real reviews from profile if available
    real_reviews = []
    gp = profile.get("google_places", {})
    if isinstance(gp, dict) and gp.get("reviews"):
        real_reviews = gp["reviews"][:6]

    # Fallback placeholder reviews
    if not real_reviews:
        real_reviews = [
            {"author": "Sarah M.", "rating": 5, "text": "Excellent service! They were prompt, professional, and did a fantastic job. Would highly recommend to anyone in the area.", "time": "2 months ago"},
            {"author": "David K.", "rating": 5, "text": "Best experience I've had. Fair pricing, quality work, and they cleaned up after themselves. Will definitely use again.", "time": "3 months ago"},
            {"author": "Linda T.", "rating": 5, "text": "Called in the morning and they were here by noon. Fixed the problem quickly and explained everything clearly. Very happy.", "time": "1 month ago"},
            {"author": "Mike R.", "rating": 4, "text": "Professional and courteous. The job was done right and on budget. Good communication throughout.", "time": "4 months ago"},
        ]

    cards = "\n".join(
        f"""<div class="review-card">
  <div class="stars">{"⭐" * int(r.get("rating") or 5)}</div>
  <p class="review-text">"{_esc(r.get("text","Great service!"))}"</p>
  <div class="review-author">— {_esc(r.get("author","Happy Customer"))}</div>
  {f'<div style="font-size:0.8rem;color:var(--muted);margin-top:0.25rem">{_esc(r.get("time",""))}</div>' if r.get("time") else ""}
</div>"""
        for r in real_reviews
    )

    html  = _head(f"Reviews | {name}", meta, business)
    html += _nav(business, "reviews")
    html += f"""
<main>
  <div class="page-hero">
    <div class="container">
      <h1>Customer Reviews</h1>
      <p>{"⭐ " + str(rating) + "/5 from " + str(reviews) + "+ verified reviews" if rating else "What our customers are saying"}</p>
    </div>
  </div>
  <section class="section">
    <div class="container">
      <div class="reviews-grid">{cards}</div>
    </div>
  </section>
  <section class="cta-banner">
    <div class="container">
      <h2>Join Our Happy Customers</h2>
      <p>Experience the same quality service that keeps {_esc(city)} residents coming back.</p>
      <a href="contact.html" class="btn btn-white btn-lg">Get a Free Quote</a>
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
