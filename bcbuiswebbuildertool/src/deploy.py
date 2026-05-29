"""
Phase 5 - Auto-Deployment (Netlify API)

Deploys the finished static site to a Netlify subdomain using the Netlify REST
API directly - no `netlify` CLI install required, just NETLIFY_AUTH_TOKEN.

Flow:
  1. Zip the site directory in memory.
  2. Create a site named {slug}-bcbuiswebbuildertool (retry w/ random suffix
     if the name is taken).
  3. POST the zip to /sites/{id}/deploys.
  4. Poll the deploy until it is "ready", then read the live URL.
  5. Write deployment.json and print a completion summary.

If NETLIFY_AUTH_TOKEN is missing: print manual instructions and continue.
"""

import io
import json
import os
import random
import string
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API = "https://api.netlify.com/api/v1"


def deploy_site(site_dir: str, business: dict) -> dict:
    """Entry point for Phase 5."""
    auth_token = os.getenv("NETLIFY_AUTH_TOKEN", "").strip()
    if not auth_token or auth_token.startswith("your_"):
        print("[deploy] NETLIFY_AUTH_TOKEN not set - skipping auto-deploy")
        return _manual_instructions(site_dir, business)

    site_path = Path(site_dir)
    if not (site_path / "index.html").exists():
        print(f"[deploy] No index.html in {site_dir} - run Phase 3 first")
        return _manual_instructions(site_dir, business)

    # Build static portal page into the site folder before zipping
    _write_portal_html(site_path, business)

    slug    = _slugify(business.get("name", "unknown-business"))
    headers = {"Authorization": f"Bearer {auth_token}"}

    site = _create_site(slug, headers)
    if not site:
        return _manual_instructions(site_dir, business)

    deployment = _deploy_zip(site, site_path, headers)
    if not deployment.get("live_url"):
        return _manual_instructions(site_dir, business)

    live_url = deployment["live_url"]
    deployment["portal_url"] = f"{live_url}/portal.html"
    (site_path / "deployment.json").write_text(json.dumps(deployment, indent=2))
    print(f"[deploy] Live at:   {live_url}")
    print(f"[deploy] Portal at: {live_url}/portal.html")
    _print_summary(business, site_path, deployment)
    return deployment


def _create_site(slug, headers):
    """Create a Netlify site, retrying with a random suffix if the name is taken."""
    team = os.getenv("NETLIFY_TEAM_SLUG", "").strip()
    base = f"{API}/{team}/sites" if team else f"{API}/sites"
    for attempt in range(3):
        name = f"{slug}-bcbuiswebbuildertool" if attempt == 0 else \
               f"{slug}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"
        print(f"[deploy] Creating site '{name}'...")
        try:
            r = requests.post(base, headers=headers, json={"name": name}, timeout=30)
        except requests.RequestException as e:
            print(f"[deploy] Network error creating site: {e}")
            return None
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code == 422:  # name taken
            continue
        print(f"[deploy] Site create failed ({r.status_code}): {r.text[:200]}")
        return None
    print("[deploy] Could not find an available site name")
    return None


def _deploy_zip(site, site_path, headers):
    """Zip the site dir and POST it to the Netlify deploys endpoint, then poll."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in site_path.rglob("*"):
            if f.is_file() and f.name != "deployment.json":
                zf.write(f, f.relative_to(site_path).as_posix())
    buf.seek(0)

    site_id = site["id"]
    print("[deploy] Uploading site bundle...")
    try:
        r = requests.post(
            f"{API}/sites/{site_id}/deploys",
            headers={**headers, "Content-Type": "application/zip"},
            data=buf.getvalue(), timeout=120,
        )
    except requests.RequestException as e:
        print(f"[deploy] Upload failed: {e}")
        return {"live_url": None}
    if r.status_code not in (200, 201):
        print(f"[deploy] Deploy failed ({r.status_code}): {r.text[:200]}")
        return {"live_url": None}

    deploy = r.json()
    deploy_id = deploy["id"]
    for _ in range(30):
        state = deploy.get("state")
        if state == "ready":
            break
        if state == "error":
            print("[deploy] Netlify reported a build error")
            return {"live_url": None}
        time.sleep(2)
        try:
            deploy = requests.get(f"{API}/deploys/{deploy_id}", headers=headers, timeout=30).json()
        except requests.RequestException:
            break

    live_url = site.get("ssl_url") or site.get("url") or deploy.get("ssl_url")
    return {
        "live_url": live_url,
        "deploy_id": deploy_id,
        "admin_url": site.get("admin_url"),
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "platform": "netlify",
        "ready_for_custom_domain": True,
    }


def _write_portal_html(site_path: Path, business: dict):
    """Generate a public-facing client portal page baked into the Netlify deploy."""
    name     = business.get("name", "Your Business")
    city     = business.get("city", "British Columbia")
    agency   = os.getenv("AGENCY_NAME", "Victoria AI")
    booking  = os.getenv("PORTAL_BOOKING_URL", "")
    email    = os.getenv("PORTAL_CONTACT_EMAIL", "")
    cta_href = booking or (f"mailto:{email}" if email else "#contact")
    cta_text = "Book a Free Call" if booking else ("Email Us to Get Started" if email else "Get Started")
    has_pdf  = (site_path / "ai_opportunity_report.pdf").exists()
    pdf_block = (
        '<section class="pdf-section">'
        '<div class="pdf-card">'
        '<h2>Free Website Opportunity Report</h2>'
        '<p>We ran a full audit of your current online presence. See exactly what\'s costing you customers.</p>'
        f'<a href="ai_opportunity_report.pdf" class="btn-pdf" download>Download Your Free Report</a>'
        '</div></section>'
    ) if has_pdf else ""

    html = f"""<!DOCTYPE html>
<html lang="en-CA">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{name} &mdash; Your New Website</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{--green:#1fb574;--navy:#1a3a5c;--off:#f5f7fa;--text:#2d3a47;--muted:#6b7c93;--white:#fff}}
    body{{font-family:'Inter',sans-serif;background:var(--off);color:var(--text)}}
    .topbar{{background:var(--navy);padding:.75rem 2rem;display:flex;align-items:center}}
    .brand{{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:.9rem;color:rgba(255,255,255,.5);letter-spacing:.06em;text-transform:uppercase}}
    .brand span{{color:var(--green)}}
    .hero{{background:var(--navy);padding:4rem 2rem 3rem;text-align:center}}
    .eyebrow{{font-size:.8rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--green);margin-bottom:1rem}}
    h1{{font-family:'Space Grotesk',sans-serif;font-size:clamp(1.8rem,5vw,3rem);font-weight:800;color:#fff;line-height:1.15;margin-bottom:1rem}}
    .hero p{{font-size:1.05rem;color:rgba(255,255,255,.6);max-width:520px;margin:0 auto 2rem;line-height:1.6}}
    .btn-primary{{background:var(--green);color:#fff;border:none;border-radius:8px;padding:.85rem 2rem;font-family:'Space Grotesk',sans-serif;font-size:1rem;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}}
    .btn-primary:hover{{background:#178f5c}}
    .preview-section{{padding:3rem 2rem;max-width:1100px;margin:0 auto}}
    .preview-section h2{{font-family:'Space Grotesk',sans-serif;font-size:1.4rem;font-weight:700;margin-bottom:.5rem}}
    .preview-section>p{{color:var(--muted);font-size:.9rem;margin-bottom:1.5rem}}
    .toggle{{display:flex;gap:.5rem;margin-bottom:1.25rem}}
    .tbtn{{background:#fff;border:1px solid #dde3ea;border-radius:7px;padding:.45rem 1.1rem;font-family:inherit;font-size:.85rem;font-weight:600;color:var(--muted);cursor:pointer}}
    .tbtn.active{{background:var(--navy);color:#fff;border-color:var(--navy)}}
    .stage{{background:#e8ecf0;border-radius:14px;padding:1.5rem;display:flex;align-items:flex-start;justify-content:center;min-height:560px}}
    .frame-wrap{{background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1);width:100%;max-height:680px;transition:all .3s}}
    .frame-wrap.mobile{{width:390px;border-radius:26px;border:8px solid #c0cad6;max-height:760px}}
    iframe{{width:100%;height:640px;border:0;display:block}}
    .frame-wrap.mobile iframe{{height:720px}}
    .props{{background:#fff;border-top:1px solid #e8ecf0;border-bottom:1px solid #e8ecf0}}
    .props-inner{{display:flex;max-width:900px;margin:0 auto}}
    .prop{{flex:1;padding:2rem 1.75rem;text-align:center;border-right:1px solid #e8ecf0}}
    .prop:last-child{{border-right:none}}
    .prop-icon{{font-size:1.8rem;margin-bottom:.75rem}}
    .prop h3{{font-family:'Space Grotesk',sans-serif;font-size:.95rem;font-weight:700;color:var(--navy);margin-bottom:.4rem}}
    .prop p{{font-size:.82rem;color:var(--muted);line-height:1.5}}
    .pdf-section{{padding:3rem 2rem;max-width:700px;margin:0 auto;text-align:center}}
    .pdf-card{{background:#fff;border:1px solid #dde3ea;border-radius:14px;padding:2rem;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
    .pdf-card h2{{font-family:'Space Grotesk',sans-serif;font-size:1.2rem;font-weight:700;color:var(--navy);margin-bottom:.5rem}}
    .pdf-card p{{font-size:.88rem;color:var(--muted);margin-bottom:1.25rem;line-height:1.6}}
    .btn-pdf{{background:var(--navy);color:#fff;border:none;border-radius:8px;padding:.75rem 1.75rem;font-family:'Space Grotesk',sans-serif;font-size:.95rem;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}}
    .cta-footer{{background:var(--navy);padding:4rem 2rem;text-align:center}}
    .cta-footer h2{{font-family:'Space Grotesk',sans-serif;font-size:clamp(1.5rem,3vw,2.2rem);font-weight:800;color:#fff;margin-bottom:.75rem}}
    .cta-footer p{{color:rgba(255,255,255,.6);font-size:.95rem;margin-bottom:2rem;max-width:480px;margin-left:auto;margin-right:auto}}
    .footer-note{{margin-top:2.5rem;font-size:.78rem;color:rgba(255,255,255,.3)}}
    @media(max-width:640px){{.props-inner{{flex-direction:column}}.prop{{border-right:none;border-bottom:1px solid #e8ecf0}}.prop:last-child{{border-bottom:none}}}}
  </style>
</head>
<body>
<nav class="topbar"><div class="brand">{agency.rsplit(" ",1)[0]} <span>{agency.rsplit(" ",1)[-1]}</span></div></nav>
<section class="hero">
  <div class="eyebrow">Your free website preview</div>
  <h1>{name} &mdash; your site is ready</h1>
  <p>We built this site specifically for <strong>{name}</strong>. No templates, no compromises. Take a look, then let us know you want it.</p>
  <a href="{cta_href}" class="btn-primary">{cta_text} &rarr;</a>
</section>
<section class="preview-section">
  <h2>Your New Website</h2>
  <p>Switch between desktop and mobile to see how your site looks on every device.</p>
  <div class="toggle">
    <button class="tbtn active" id="btn-d" onclick="setMode('desktop')">Desktop</button>
    <button class="tbtn" id="btn-m" onclick="setMode('mobile')">Mobile</button>
  </div>
  <div class="stage">
    <div class="frame-wrap" id="fw">
      <iframe src="index.html" title="Website preview" scrolling="yes"></iframe>
    </div>
  </div>
</section>
<div class="props"><div class="props-inner">
  <div class="prop"><div class="prop-icon">&#128241;</div><h3>Mobile-First</h3><p>Over 70% of local searches happen on phones. Your site looks perfect on every screen.</p></div>
  <div class="prop"><div class="prop-icon">&#9889;</div><h3>Lightning Fast</h3><p>Static-site tech loads in under a second &mdash; customers don&rsquo;t wait, they convert.</p></div>
  <div class="prop"><div class="prop-icon">&#128270;</div><h3>Found on Google</h3><p>Built with schema markup, meta tags, and local SEO from day one.</p></div>
</div></div>
{pdf_block}
<section class="cta-footer">
  <h2>Ready to claim your site?</h2>
  <p>We handle everything &mdash; domain, hosting, and updates. You just run your business.</p>
  <a href="{cta_href}" class="btn-primary">{cta_text} &rarr;</a>
  <p class="footer-note">Delivered by {agency} &mdash; BC&rsquo;s local web specialists</p>
</section>
<script>
  function setMode(m){{
    document.getElementById('fw').classList.toggle('mobile',m==='mobile');
    document.getElementById('btn-d').classList.toggle('active',m==='desktop');
    document.getElementById('btn-m').classList.toggle('active',m==='mobile');
  }}
</script>
</body></html>"""
    (site_path / "portal.html").write_text(html, encoding="utf-8")
    print("[deploy] portal.html written to site folder")


def _manual_instructions(site_dir, business):
    print(f"""
[deploy] To deploy manually:
  1. Get a token: https://app.netlify.com/user/applications  (Personal access token)
  2. Put it in .env as NETLIFY_AUTH_TOKEN=... then re-run Phase 5
  Or drag the folder onto https://app.netlify.com/drop :
     {site_dir}
""")
    return {
        "live_url": None, "deploy_id": None,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "platform": "netlify", "ready_for_custom_domain": True,
        "manual_deploy_required": True,
    }


def _print_summary(business, site_dir, deployment):
    print(f"""
====================================================
  BCBUISWEBBUILDERTOOL - JOB COMPLETE
====================================================
Business:  {business.get('name')}
LIVE:      {deployment.get('live_url')}
Admin:     {deployment.get('admin_url')}
Files:     {site_dir}/
====================================================
""")


def _slugify(name):
    return name.lower().replace(" ", "-").replace("/", "-")
