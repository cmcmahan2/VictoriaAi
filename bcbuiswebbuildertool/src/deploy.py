"""
Phase 5 - Auto-Deployment

Deploy the finished site to a Netlify subdomain:
  1. Name the site: {slug}-bcbuiswebbuildertool
  2. Run netlify deploy --prod (static) or npm build + deploy (Next.js)
  3. Retry with random suffix if site name is taken
  4. Parse live URL from CLI output
  5. Write deployment.json, update README, print completion summary

If NETLIFY_AUTH_TOKEN is missing: print manual deploy instructions and continue.
"""

import json
import os
import random
import string
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


def deploy_site(site_dir: str, business: dict) -> dict:
    """Entry point for Phase 5."""
    auth_token = os.getenv("NETLIFY_AUTH_TOKEN")
    if not auth_token:
        print("[deploy] NETLIFY_AUTH_TOKEN not set - skipping auto-deploy")
        return _manual_instructions(site_dir, business)
    slug      = _slugify(business.get("name", "unknown-business"))
    site_name = f"{slug}-bcbuiswebbuildertool"
    deployment = _run_deploy(Path(site_dir), site_name)
    if not deployment.get("live_url"):
        return _manual_instructions(site_dir, business)
    path = Path(site_dir) / "deployment.json"
    path.write_text(json.dumps(deployment, indent=2))
    print(f"[deploy] Live at: {deployment['live_url']}")
    _print_summary(business, Path(site_dir), deployment)
    return deployment


def _run_deploy(site_dir, site_name):
    """
    Run Netlify CLI deploy and parse the live URL from stdout.
    Retries with a random suffix if site name is taken.
    """
    is_nextjs = (site_dir / "package.json").exists() and any(site_dir.glob("next.config*"))
    if is_nextjs:
        subprocess.run(["npm", "run", "build"], cwd=site_dir, check=True)
        deploy_dir = str(site_dir / ".next")
    else:
        deploy_dir = str(site_dir)

    for attempt in range(2):
        name = site_name if attempt == 0 else f"{site_name}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=4))}"
        try:
            result = subprocess.run(
                ["netlify", "deploy", "--prod", f"--dir={deploy_dir}", f"--site={name}"],
                capture_output=True, text=True, check=True
            )
            import re
            m = re.search(r"Website URL:\s*(https://\S+)", result.stdout)
            deploy_id_m = re.search(r"Deploy ID:\s*(\S+)", result.stdout)
            if m:
                return {
                    "live_url": m.group(1),
                    "deploy_id": deploy_id_m.group(1) if deploy_id_m else None,
                    "deployed_at": datetime.now(timezone.utc).isoformat(),
                    "platform": "netlify",
                    "ready_for_custom_domain": True,
                }
        except subprocess.CalledProcessError as e:
            if "already exists" not in e.stderr and attempt == 0:
                break
    return {"live_url": None}


def _manual_instructions(site_dir, business):
    print(f"""
[deploy] To deploy manually:
  1. npm install -g netlify-cli
  2. netlify login
  3. cd {site_dir} && netlify deploy --prod
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
PDF:       {site_dir}/ai_opportunity_report.pdf
Files:     {site_dir}/
Redeploy:  cd {site_dir} && netlify deploy --prod
====================================================
""")


def _slugify(name):
    return name.lower().replace(" ", "-").replace("/", "-")
