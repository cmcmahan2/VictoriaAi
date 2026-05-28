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

    slug    = _slugify(business.get("name", "unknown-business"))
    headers = {"Authorization": f"Bearer {auth_token}"}

    site = _create_site(slug, headers)
    if not site:
        return _manual_instructions(site_dir, business)

    deployment = _deploy_zip(site, site_path, headers)
    if not deployment.get("live_url"):
        return _manual_instructions(site_dir, business)

    (site_path / "deployment.json").write_text(json.dumps(deployment, indent=2))
    print(f"[deploy] Live at: {deployment['live_url']}")
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
