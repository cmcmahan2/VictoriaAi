"""
Premium single-page template — modeled on the hand-designed Careful Painting
site (editorial serif headlines, cream palette, bento gallery, process rail).

Every generated site gets this look, adapted to the business: name, city,
trade, services, photos, reviews and phone flow in from the profile /
customize layer. Fully responsive (fluid type via clamp(), grids collapse,
real hamburger menu) — the same design that sold on desktop works on a phone.

Rendered as ONE self-contained index.html (nav uses #anchors) with a
Netlify-ready contact form, so Phase 5 deploys capture leads immediately.
"""

from __future__ import annotations

import html as _html
import re


def _e(s) -> str:
    return _html.escape(str(s or ""))


def _tel(phone: str) -> str:
    return re.sub(r"[^\d+]", "", phone or "")


# Curated palettes — all keep the editorial cream/ink look; the accent and
# deep tone shift per trade so two neighbouring clients don't look identical.
_PALETTES = [
    {"accent": "#BC5B36", "deep": "#243B30", "deeper": "#1B2A22"},  # terracotta/forest
    {"accent": "#2A5B8C", "deep": "#22303B", "deeper": "#18242E"},  # steel blue/slate
    {"accent": "#A8742B", "deep": "#3B3226", "deeper": "#2A2117"},  # ochre/umber
    {"accent": "#246A52", "deep": "#28323B", "deeper": "#1B242C"},  # emerald/graphite
]


def _palette(business: dict, customize: dict) -> dict:
    import hashlib
    override = (customize.get("premium_accent") or "").strip()
    cat = (business.get("category") or "") + (business.get("name") or "")
    pal = _PALETTES[int(hashlib.md5(cat.encode()).hexdigest(), 16) % len(_PALETTES)]
    if override.startswith("#"):
        pal = dict(pal, accent=override)
    return pal


def _split_headline(headline: str) -> tuple[str, str]:
    """Split a headline so the last word gets the italic serif accent."""
    words = (headline or "").strip().split()
    if len(words) < 2:
        return headline, ""
    return " ".join(words[:-1]), words[-1]


def render_premium_site(business: dict, profile: dict, content: dict,
                        customize: dict, img_fn, svc_kw_fn, cat_kw: str) -> str:
    """Return the full index.html for the premium one-page site.

    img_fn(keywords, w, h, seed) and svc_kw_fn(service_name, fallback) are
    injected from build.py so this module stays import-light.
    """
    name  = (business.get("name") or "Our Business").strip()
    city  = (business.get("city") or "your area").strip()
    phone = (business.get("phone") or "").strip()
    cats  = business.get("categories") or [business.get("category", "services")]
    cat   = (cats[0] or "services") if cats else "services"

    headline = content.get("headline") or f"Quality work,\ndone with care."
    tagline  = content.get("tagline") or ""
    about    = content.get("about_paragraph") or ""
    cta_text = content.get("cta_text") or "Get a free estimate"
    trust_ln = content.get("trust_line") or f"Proudly serving {city}"
    meta     = content.get("meta_description") or f"{name} — {city}"
    services = [s for s in (content.get("services") or []) if isinstance(s, dict)][:6]

    pal = _palette(business, customize)
    head_a, head_b = _split_headline(headline)

    # ── Imagery: real photos first, curated stock as fallback ──
    svc_imgs = customize.get("service_images") or {}
    extra    = list(customize.get("_gp_extra_photos") or [])
    hero_img = customize.get("hero_image") or (extra.pop(0) if extra else None) \
        or img_fn(cat_kw, 1200, 1500, seed=name + "hero")

    def _service_img(svc_name: str, i: int) -> str:
        for k, v in svc_imgs.items():
            if k.lower() in svc_name.lower() or svc_name.lower() in k.lower():
                return v
        if extra:
            return extra[i % len(extra)]
        return img_fn(svc_kw_fn(svc_name, cat_kw), 900, 600, seed=svc_name)

    gallery: list[tuple[str, str]] = []
    seen = set()
    for label, url in [(k, v) for k, v in svc_imgs.items()] + \
                      [(f"Recent work", u) for u in extra]:
        if url not in seen:
            gallery.append((label, url)); seen.add(url)
    i = 0
    while len(gallery) < 6 and i < len(services):
        s_name = services[i].get("name", "Our work")
        url = _service_img(s_name, i)
        if url not in seen:
            gallery.append((s_name, url)); seen.add(url)
        i += 1
    while len(gallery) < 6:
        url = img_fn(cat_kw, 900, 700, seed=f"gal{len(gallery)}")
        if url in seen:
            break
        gallery.append(("Recent work", url)); seen.add(url)

    # ── Reviews: real ones win; visible placeholder note otherwise ──
    reviews = customize.get("reviews") or []
    placeholder_reviews = not reviews
    if placeholder_reviews:
        reviews = [
            {"name": "Happy Customer", "text": "Professional, tidy and exactly on schedule. We'd hire them again in a heartbeat.", "location": city},
            {"name": "Local Homeowner", "text": "Respectful of our home and meticulous with the details. The result is flawless.", "location": city},
            {"name": "Satisfied Client", "text": "From the first call to the final walkthrough, everything was handled with care.", "location": city},
        ]
    reviews = reviews[:3]

    rating = business.get("rating")
    try:
        rating_f = float(rating) if rating else None
    except (TypeError, ValueError):
        rating_f = None

    stats: list[str] = []
    if rating_f:
        stats.append(f'<span class="stat"><strong>{rating_f:.1f}★</strong> Google rating</span>')
    stats.append('<span class="stat">Licensed &amp; insured</span>')
    stats.append('<span class="stat">Free estimates</span>')
    stats_html = '<span class="sep"></span>'.join(stats)

    steps = [
        ("01", "Free estimate", "We visit, listen to what you need, and give you a clear written quote — no obligation."),
        ("02", "Plan &amp; schedule", "We finalize the details and schedule the work around your life, not ours."),
        ("03", "Careful prep", "Your property is protected and every surface prepared properly. Prep is everything."),
        ("04", "Quality work", "An experienced crew, quality materials, and clean workmanship from start to finish."),
        ("05", "Final walkthrough", "We inspect together, fix anything you spot, and leave the site spotless."),
    ]

    phone_html = ""
    phone_cta = ""
    nav_phone = ""
    if phone:
        t = _tel(phone)
        phone_html = f'<a href="tel:{t}">{_e(phone)}</a>'
        phone_cta = f'<a href="tel:{t}" class="btn btn-ghost">Call {_e(phone)}</a>'
        nav_phone = f'<a href="tel:{t}" class="nav-phone"><span class="pdot"></span>{_e(phone)}</a>'

    services_html = "\n".join(
        f'''<a href="#contact" class="svc">
      <div class="ph"><img src="{_e(_service_img(s.get("name","Service"), i))}" alt="{_e(s.get("name","Service"))}" loading="lazy"></div>
      <div class="body"><h3>{_e(s.get("name","Service"))}</h3><p>{_e(s.get("description",""))}</p><span class="more">Get a quote →</span></div>
    </a>''' for i, s in enumerate(services))

    gallery_html = "\n".join(
        f'''<div class="gtile{' g-2x2' if i == 0 else (' g-2x1' if i == 5 else '')}"><img src="{_e(u)}" alt="{_e(lbl)}" loading="lazy"><div class="cap"><div><div class="l">{_e(lbl)}</div><div class="p">{_e(city)}</div></div></div></div>'''
        for i, (lbl, u) in enumerate(gallery[:8]))

    steps_html = "\n".join(
        f'''<div class="step"><div class="num">{n}</div><div><h3>{t}</h3><p>{d}</p></div></div>'''
        for n, t, d in steps)

    reviews_html = "\n".join(
        f'''<figure class="rev"><div class="stars">★★★★★</div><blockquote>"{_e(r.get("text") or r.get("quote",""))}"</blockquote><figcaption><strong>{_e(r.get("name","Customer"))}</strong><span> — {_e(r.get("location") or city)}</span></figcaption></figure>'''
        for r in reviews)
    reviews_note = ('<p class="note">Representative reviews — replace with your '
                    'own verified testimonials.</p>' if placeholder_reviews else "")

    areas_html = "".join(f"<span>{_e(a)}</span>" for a in
                         [city, f"Greater {city}", "Surrounding areas"])

    # Person-noun → trade-noun so headings read naturally
    # ("painter" → "Painting", "plumber" → "Plumbing").
    _trades = {"painter": "Painting", "plumber": "Plumbing",
               "electrician": "Electrical", "roofer": "Roofing",
               "landscaper": "Landscaping", "mechanic": "Auto Repair",
               "contractor": "Contracting", "cleaner": "Cleaning",
               "mover": "Moving", "welder": "Welding"}
    cat_l = cat.strip().lower()
    trade_words = next((v for k, v in _trades.items() if k in cat_l),
                       cat.strip().title() or "Services")
    badge = f"{city} {trade_words}" if city.lower() not in cat.lower() else trade_words

    return f'''<!DOCTYPE html>
<html lang="en-CA">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(name)} — {_e(trade_words)} in {_e(city)}</title>
<meta name="description" content="{_e(meta)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{{
    --bg:#F6F1E7; --ink:#1B1B18; --accent:{pal["accent"]}; --deep:{pal["deep"]};
    --deeper:{pal["deeper"]}; --muted:#5C5A52; --muted2:#4A483F; --cream:#EFE9DA;
    --display:'Spectral',Georgia,serif; --body:'Hanken Grotesk',system-ui,sans-serif;
    --maxw:1200px;
  }}
  *{{box-sizing:border-box;margin:0;padding:0;}}
  html{{scroll-behavior:smooth;}}
  body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);
    min-height:100vh;-webkit-font-smoothing:antialiased;overflow-x:hidden;line-height:1.5;}}
  a{{text-decoration:none;color:inherit;}}
  img{{display:block;max-width:100%;}}
  ::selection{{background:var(--deep);color:var(--bg);}}
  .wrap{{max-width:var(--maxw);margin:0 auto;padding-left:28px;padding-right:28px;}}
  .eyebrow{{font-size:13px;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);font-weight:600;}}
  .btn{{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:9px;
    font-weight:600;font-size:16px;padding:15px 28px;transition:transform .2s ease,box-shadow .2s ease;}}
  .btn-primary{{background:var(--accent);color:#fff;border:none;cursor:pointer;font-family:var(--body);}}
  .btn-primary:hover{{transform:translateY(-2px);box-shadow:0 14px 30px -14px var(--accent);}}
  .btn-ghost{{border:1.5px solid rgba(27,27,24,.22);color:var(--ink);}}
  .btn-ghost:hover{{border-color:var(--ink);}}

  .topbar{{background:var(--deeper);color:#E9E2D2;font-size:13px;letter-spacing:.02em;}}
  .topbar .wrap{{padding-top:9px;padding-bottom:9px;display:flex;align-items:center;
    justify-content:space-between;gap:16px;flex-wrap:wrap;}}
  .topbar .dot{{width:7px;height:7px;border-radius:50%;background:var(--accent);display:inline-block;margin-right:8px;}}
  .topbar a{{font-weight:600;color:#fff;}}

  header{{position:sticky;top:0;z-index:60;background:rgba(246,241,231,.9);
    backdrop-filter:blur(10px);border-bottom:1px solid rgba(27,27,24,.10);}}
  .nav{{padding-top:15px;padding-bottom:15px;display:flex;align-items:center;justify-content:space-between;gap:24px;}}
  .brand{{display:flex;align-items:center;gap:12px;color:var(--ink);}}
  .brand .mark{{width:34px;height:34px;border-radius:7px;background:var(--deep);
    display:flex;align-items:center;justify-content:center;flex:none;}}
  .brand .mark span{{width:13px;height:13px;border-radius:3px;background:var(--accent);}}
  .brand .name{{font-family:var(--display);font-weight:600;font-size:20px;letter-spacing:.01em;display:block;line-height:1;}}
  .brand .sub{{font-size:11px;letter-spacing:.22em;text-transform:uppercase;color:#6b695e;margin-top:4px;display:block;}}
  .menu{{display:flex;align-items:center;gap:30px;font-size:15px;font-weight:500;}}
  .menu a{{opacity:.82;padding:4px 0;}} .menu a:hover{{opacity:1;}}
  .nav-actions{{display:flex;align-items:center;gap:16px;}}
  .nav-phone{{font-weight:600;font-size:15px;display:flex;align-items:center;gap:7px;}}
  .nav-phone .pdot{{width:6px;height:6px;border-radius:50%;background:var(--accent);}}
  .nav-cta{{background:var(--deep);color:var(--bg);padding:11px 20px;border-radius:8px;font-weight:600;font-size:14.5px;}}
  .hamburger{{display:none;flex-direction:column;justify-content:center;gap:5px;width:44px;height:44px;
    border:1px solid rgba(27,27,24,.18);border-radius:9px;background:transparent;cursor:pointer;flex:none;}}
  .hamburger span{{display:block;width:20px;height:2px;background:var(--ink);margin:0 auto;}}
  .mobile-menu{{display:none;border-top:1px solid rgba(27,27,24,.10);background:rgba(246,241,231,.98);}}
  .mobile-menu.open{{display:block;}}
  .mobile-menu a{{display:block;padding:14px 28px;font-size:17px;font-weight:500;border-bottom:1px solid rgba(27,27,24,.06);}}
  .mobile-menu .mm-cta{{margin:16px 28px 22px;}}

  .hero{{padding-top:72px;padding-bottom:40px;display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:center;}}
  .badge{{display:inline-flex;align-items:center;gap:10px;padding:7px 14px;border:1px solid rgba(27,27,24,.16);
    border-radius:100px;font-size:12.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:26px;}}
  .badge .bdot{{width:6px;height:6px;border-radius:50%;background:var(--accent);}}
  h1.hero-title{{font-family:var(--display);font-weight:600;font-size:clamp(38px,7vw,60px);
    line-height:1.06;letter-spacing:-.015em;margin-bottom:24px;}}
  h1.hero-title em{{font-style:italic;color:var(--deep);}}
  .hero-lead{{font-size:clamp(16px,2.2vw,18.5px);line-height:1.6;color:var(--muted2);max-width:480px;margin-bottom:34px;}}
  .hero-actions{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:34px;}}
  .hero-stats{{display:flex;align-items:center;gap:24px;flex-wrap:wrap;font-size:13.5px;color:var(--muted);}}
  .hero-stats .stat strong{{font-family:var(--display);font-size:20px;color:var(--ink);font-weight:600;}}
  .hero-stats .sep{{width:1px;height:26px;background:rgba(27,27,24,.14);}}
  .hero-photo{{border-radius:16px;overflow:hidden;aspect-ratio:4/5;background:var(--deep);
    box-shadow:0 30px 60px -30px rgba(0,0,0,.5);}}
  .hero-photo img{{width:100%;height:100%;object-fit:cover;}}

  .trust{{border-top:1px solid rgba(27,27,24,.10);border-bottom:1px solid rgba(27,27,24,.10);margin-top:32px;}}
  .trust .grid{{padding-top:26px;padding-bottom:26px;display:grid;grid-template-columns:repeat(4,1fr);gap:24px;}}
  .trust .t{{font-family:var(--display);font-weight:600;font-size:17px;}}
  .trust .s{{font-size:13.5px;color:var(--muted);margin-top:4px;}}

  .sec-pad{{padding-top:90px;padding-bottom:30px;}}
  .sec-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:44px;flex-wrap:wrap;}}
  .sec-head h2,.h2{{font-family:var(--display);font-weight:600;font-size:clamp(30px,4.5vw,42px);
    line-height:1.06;letter-spacing:-.01em;max-width:600px;margin-top:14px;}}
  .sec-head p{{font-size:16px;color:var(--muted2);max-width:340px;line-height:1.6;}}

  .services-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;}}
  .svc{{display:flex;flex-direction:column;background:#fff;border:1px solid rgba(27,27,24,.08);
    border-radius:14px;overflow:hidden;transition:transform .25s ease,box-shadow .25s ease;}}
  .svc:hover{{transform:translateY(-4px);box-shadow:0 22px 44px -26px rgba(0,0,0,.35);}}
  .svc .ph{{aspect-ratio:3/2;overflow:hidden;background:#E9E2D2;}}
  .svc .ph img{{width:100%;height:100%;object-fit:cover;transition:transform .4s ease;}}
  .svc:hover .ph img{{transform:scale(1.04);}}
  .svc .body{{padding:22px 22px 24px;}}
  .svc h3{{font-family:var(--display);font-weight:600;font-size:21px;margin-bottom:8px;}}
  .svc p{{font-size:14.5px;color:var(--muted);line-height:1.55;margin-bottom:14px;}}
  .svc .more{{font-size:14px;font-weight:600;color:var(--accent);}}

  .gallery{{display:grid;grid-template-columns:repeat(4,1fr);grid-auto-rows:200px;gap:14px;}}
  .gtile{{position:relative;overflow:hidden;border-radius:12px;background:#E9E2D2;}}
  .gtile img{{width:100%;height:100%;object-fit:cover;transition:transform .5s ease;}}
  .gtile:hover img{{transform:scale(1.05);}}
  .gtile .cap{{position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,.6),rgba(0,0,0,0) 52%);
    display:flex;align-items:flex-end;padding:16px;color:var(--bg);}}
  .gtile .cap .l{{font-family:var(--display);font-weight:600;font-size:16px;}}
  .gtile .cap .p{{font-size:12.5px;opacity:.82;}}
  .g-2x2{{grid-column:span 2;grid-row:span 2;}} .g-2x1{{grid-column:span 2;}}

  .process{{background:var(--deep);color:var(--cream);margin-top:90px;}}
  .process .inner{{padding-top:84px;padding-bottom:84px;display:grid;grid-template-columns:.85fr 1.15fr;gap:56px;align-items:start;}}
  .process h2{{font-family:var(--display);font-weight:600;font-size:clamp(30px,4.4vw,40px);line-height:1.08;margin:14px 0 20px;}}
  .process .intro{{font-size:16px;line-height:1.65;opacity:.75;max-width:360px;}}
  .step{{display:flex;gap:22px;padding:22px 0;border-top:1px solid rgba(239,233,218,.16);}}
  .step .num{{font-family:var(--display);font-size:18px;color:var(--accent);font-weight:600;min-width:34px;}}
  .step h3{{font-family:var(--display);font-weight:600;font-size:21px;margin-bottom:6px;}}
  .step p{{font-size:15px;opacity:.75;line-height:1.55;}}

  .about{{padding-top:90px;padding-bottom:90px;display:grid;grid-template-columns:.95fr 1.05fr;gap:56px;align-items:center;}}
  .about-photo{{border-radius:16px;overflow:hidden;aspect-ratio:5/4;background:#E9E2D2;box-shadow:0 28px 56px -32px rgba(0,0,0,.4);}}
  .about-photo img{{width:100%;height:100%;object-fit:cover;}}
  .about h2{{font-family:var(--display);font-weight:600;font-size:clamp(30px,4.4vw,40px);line-height:1.1;margin:14px 0 22px;}}
  .about p{{font-size:17px;line-height:1.7;color:var(--muted2);margin-bottom:18px;}}

  .reviews{{border-top:1px solid rgba(27,27,24,.10);background:var(--cream);}}
  .reviews .inner{{padding-top:84px;padding-bottom:84px;}}
  .reviews .head{{text-align:center;margin-bottom:48px;}}
  .reviews-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;}}
  .rev{{background:#fff;border:1px solid rgba(27,27,24,.08);border-radius:14px;padding:30px 28px;display:flex;flex-direction:column;}}
  .rev .stars{{color:var(--accent);font-size:18px;letter-spacing:3px;margin-bottom:16px;}}
  .rev blockquote{{font-family:var(--display);font-size:19px;line-height:1.5;margin-bottom:22px;flex:1;}}
  .rev figcaption{{font-size:14px;}} .rev figcaption span{{color:var(--muted);}}
  .reviews .note{{text-align:center;font-size:13.5px;color:#7A776B;margin-top:24px;font-style:italic;}}

  .areas{{padding-top:84px;padding-bottom:44px;text-align:center;}}
  .chips{{display:flex;flex-wrap:wrap;justify-content:center;gap:12px;max-width:780px;margin:30px auto 0;}}
  .chips span{{padding:10px 20px;border:1px solid rgba(27,27,24,.16);border-radius:100px;font-size:15px;font-weight:500;}}

  .contact{{padding-top:60px;padding-bottom:90px;}}
  .contact .box{{background:var(--deep);border-radius:22px;padding:64px 56px;display:grid;
    grid-template-columns:1fr 1fr;gap:48px;align-items:start;position:relative;overflow:hidden;}}
  .contact .blob{{position:absolute;right:-60px;top:-60px;width:280px;height:280px;border-radius:50%;background:var(--accent);opacity:.16;}}
  .contact h2{{font-family:var(--display);font-weight:600;font-size:clamp(30px,4.6vw,42px);line-height:1.08;color:var(--bg);margin-bottom:18px;position:relative;}}
  .contact .sub{{font-size:17px;color:rgba(239,233,218,.75);line-height:1.6;max-width:420px;position:relative;margin-bottom:26px;}}
  .contact .call{{position:relative;color:var(--cream);font-size:15px;}}
  .contact .call a{{color:#fff;font-weight:700;font-size:20px;font-family:var(--display);}}
  form.cform{{position:relative;display:flex;flex-direction:column;gap:12px;}}
  .cform input,.cform textarea{{background:rgba(246,241,231,.07);border:1px solid rgba(239,233,218,.25);
    border-radius:9px;padding:13px 15px;color:#fff;font-family:var(--body);font-size:15px;outline:none;width:100%;}}
  .cform input::placeholder,.cform textarea::placeholder{{color:rgba(239,233,218,.5);}}
  .cform input:focus,.cform textarea:focus{{border-color:var(--accent);}}
  #form-success{{display:none;background:rgba(255,255,255,.1);border:1px solid var(--accent);border-radius:10px;
    padding:14px 16px;color:#fff;font-size:15px;}}

  footer{{background:var(--deeper);color:#C7C0AF;}}
  .foot{{padding-top:44px;padding-bottom:30px;display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap;align-items:center;}}
  .foot .nm{{font-family:var(--display);font-weight:600;font-size:19px;color:var(--bg);}}
  .foot .fine{{font-size:13px;color:#7E8A80;}}

  @media (max-width:1000px){{
    .hero{{grid-template-columns:1fr;gap:40px;padding-top:48px;}}
    .hero-media{{order:-1;}} .hero-photo{{aspect-ratio:16/11;}}
    .process .inner,.about,.contact .box{{grid-template-columns:1fr;gap:36px;}}
    .reviews-grid{{grid-template-columns:1fr 1fr;}}
    .gallery{{grid-auto-rows:170px;}}
  }}
  @media (max-width:760px){{
    .wrap{{padding-left:20px;padding-right:20px;}}
    .menu,.nav-phone{{display:none;}} .hamburger{{display:flex;}}
    .nav-actions .nav-cta{{display:none;}}
    .services-grid,.reviews-grid{{grid-template-columns:1fr;}}
    .trust .grid{{grid-template-columns:1fr 1fr;gap:20px 16px;}}
    .sec-pad{{padding-top:60px;}} .about{{padding-top:64px;padding-bottom:64px;}}
    .gallery{{grid-template-columns:1fr 1fr;grid-auto-rows:150px;gap:10px;}}
    .g-2x2{{grid-column:span 2;grid-row:span 1;}}
    .hero-actions .btn{{flex:1 1 auto;}}
    .contact .box{{padding:40px 26px;}}
  }}
  @media (max-width:420px){{
    .gallery{{grid-template-columns:1fr;grid-auto-rows:200px;}}
    .g-2x2,.g-2x1{{grid-column:span 1;}}
    .trust .grid{{grid-template-columns:1fr;}}
  }}
</style>
</head>
<body>

<div class="topbar">
  <div class="wrap">
    <span><span class="dot"></span>{_e(trust_ln)}</span>
    {phone_html}
  </div>
</div>

<header>
  <div class="wrap nav">
    <a href="#top" class="brand">
      <span class="mark"><span></span></span>
      <span>
        <span class="name">{_e(name)}</span>
        <span class="sub">{_e(city)}</span>
      </span>
    </a>
    <nav class="menu">
      <a href="#top">Home</a><a href="#services">Services</a><a href="#work">Gallery</a>
      <a href="#about">About</a><a href="#reviews">Reviews</a><a href="#contact">Contact</a>
    </nav>
    <div class="nav-actions">
      {nav_phone}
      <a href="#contact" class="nav-cta">{_e(cta_text)}</a>
      <button class="hamburger" id="hamburger" aria-label="Open menu" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>
    </div>
  </div>
  <div class="mobile-menu" id="mobileMenu">
    <a href="#top">Home</a><a href="#services">Services</a><a href="#work">Gallery</a>
    <a href="#about">About</a><a href="#reviews">Reviews</a><a href="#contact">Contact</a>
    {f'<a href="tel:{_tel(phone)}">📞 {_e(phone)}</a>' if phone else ''}
    <a href="#contact" class="btn btn-primary mm-cta">{_e(cta_text)}</a>
  </div>
</header>

<section id="top" class="wrap hero">
  <div>
    <div class="badge"><span class="bdot"></span>{_e(badge)}</div>
    <h1 class="hero-title">{_e(head_a)} <em>{_e(head_b)}</em></h1>
    <p class="hero-lead">{_e(tagline)}</p>
    <div class="hero-actions">
      <a href="#contact" class="btn btn-primary">{_e(cta_text)}</a>
      {phone_cta}
    </div>
    <div class="hero-stats">{stats_html}</div>
  </div>
  <div class="hero-media">
    <div class="hero-photo"><img src="{_e(hero_img)}" alt="{_e(name)} — {_e(trade_words)} in {_e(city)}" loading="eager"></div>
  </div>
</section>

<section class="trust">
  <div class="wrap grid">
    <div><div class="t">Local &amp; trusted</div><div class="s">Proudly serving {_e(city)}</div></div>
    <div><div class="t">Licensed &amp; insured</div><div class="s">Work you can rely on</div></div>
    <div><div class="t">Free estimates</div><div class="s">Clear, honest quotes</div></div>
    <div><div class="t">Quality first</div><div class="s">We treat your place like ours</div></div>
  </div>
</section>

<section id="services" class="wrap sec-pad">
  <div class="sec-head">
    <div>
      <div class="eyebrow">What we do</div>
      <h2>{_e(trade_words)}, start to finish</h2>
    </div>
    <p>One reliable crew for the whole project — honest advice, careful work, and a tidy finish.</p>
  </div>
  <div class="services-grid">
{services_html}
  </div>
</section>

<section id="work" class="wrap sec-pad">
  <div style="margin-bottom:44px;">
    <div class="eyebrow">Recent work</div>
    <h2 class="h2">Projects across {_e(city)}</h2>
  </div>
  <div class="gallery">
{gallery_html}
  </div>
</section>

<section id="process" class="process">
  <div class="wrap inner">
    <div>
      <div class="eyebrow">How it works</div>
      <h2>A careful process, every time</h2>
      <p class="intro">No surprises and no shortcuts. From the first walkthrough to the final inspection, you'll know exactly what's happening and when.</p>
    </div>
    <div>
{steps_html}
    </div>
  </div>
</section>

<section id="about" class="wrap about">
  <div class="about-photo"><img src="{_e(gallery[0][1] if gallery else hero_img)}" alt="About {_e(name)}" loading="lazy"></div>
  <div>
    <div class="eyebrow">About {_e(name)}</div>
    <h2>{_e(city)}'s {_e(trade_words.lower())} team you can count on</h2>
    <p>{_e(about)}</p>
  </div>
</section>

<section id="reviews" class="reviews">
  <div class="wrap inner">
    <div class="head">
      <div class="eyebrow">Kind words</div>
      <h2 class="h2" style="margin:14px auto 0;">What {_e(city)} customers say</h2>
    </div>
    <div class="reviews-grid">
{reviews_html}
    </div>
    {reviews_note}
  </div>
</section>

<section class="wrap areas">
  <div class="eyebrow">Service area</div>
  <h2 class="h2" style="margin:14px auto 0;max-width:none;">Proudly serving {_e(city)}</h2>
  <div class="chips">{areas_html}</div>
</section>

<section id="contact" class="wrap contact">
  <div class="box">
    <span class="blob"></span>
    <div>
      <h2>Ready to get started?</h2>
      <p class="sub">Tell us about your project and we'll get back to you with a free, no-obligation estimate.</p>
      {f'<p class="call">Prefer to talk? {phone_html}</p>' if phone else ''}
    </div>
    <form class="cform" id="contact-form" name="contact-main" method="POST" data-netlify="true">
      <input type="hidden" name="form-name" value="contact-main">
      <div id="form-success">✓ Thanks — we got your message and will be in touch shortly.</div>
      <input type="text" name="name" placeholder="Your name" required>
      <input type="email" name="email" placeholder="Email" required>
      <input type="tel" name="phone" placeholder="Phone (optional)">
      <textarea name="message" rows="4" placeholder="Tell us about your project…" required></textarea>
      <button type="submit" class="btn btn-primary">{_e(cta_text)}</button>
    </form>
  </div>
</section>

<footer>
  <div class="wrap foot">
    <span class="nm">{_e(name)}</span>
    <span class="fine">© <span id="year">2026</span> {_e(name)}. {_e(trade_words)} in {_e(city)}.</span>
  </div>
</footer>

<script>
  (function(){{
    var btn = document.getElementById('hamburger');
    var menu = document.getElementById('mobileMenu');
    btn.addEventListener('click', function(){{
      var open = menu.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }});
    menu.addEventListener('click', function(e){{
      if (e.target.tagName === 'A'){{ menu.classList.remove('open'); btn.setAttribute('aria-expanded','false'); }}
    }});
    document.getElementById('year').textContent = new Date().getFullYear();

    // Netlify AJAX submit with inline thank-you (no redirect away)
    var form = document.getElementById('contact-form');
    form.addEventListener('submit', function(e){{
      e.preventDefault();
      var sb = form.querySelector('button[type="submit"]');
      sb.disabled = true; sb.textContent = 'Sending…';
      var data = new URLSearchParams(new FormData(form)).toString();
      fetch('/', {{method:'POST', headers:{{'Content-Type':'application/x-www-form-urlencoded'}}, body:data}})
        .then(function(){{
          var ok = document.getElementById('form-success');
          ok.style.display = 'block'; form.reset();
          sb.disabled = false; sb.textContent = 'Send';
        }})
        .catch(function(){{
          sb.disabled = false; sb.textContent = 'Try again';
          alert('Sorry, something went wrong. Please call us instead.');
        }});
    }});
  }})();
</script>
</body>
</html>'''
