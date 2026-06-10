"""
BCBUISWEBBUILDERTOOL - Admin Web Server

FastAPI backend serving the admin dashboard and pipeline API.

Usage:
    python src/server.py
    Open: http://localhost:5000

Set ADMIN_PASSWORD in .env before running.
"""

import asyncio
import json
import os
import secrets
import sys
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

app = FastAPI(title="BCBUISWEBBUILDERTOOL Admin", docs_url=None, redoc_url=None)

OUTPUT_DIR  = Path("./output")
RESEARCH_DIR = Path("./research")
WEB_DIR     = Path(__file__).parent / "web"
CLIENTS_FILE = OUTPUT_DIR / "clients.json"

VALID_TOKENS: set[str] = set()
JOBS: dict[str, dict]  = {}


def _load_clients() -> list:
    if CLIENTS_FILE.exists():
        try:
            return json.loads(CLIENTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_clients(clients: list):
    OUTPUT_DIR.mkdir(exist_ok=True)
    CLIENTS_FILE.write_text(json.dumps(clients, indent=2), encoding="utf-8")


def _upsert_client(record: dict):
    clients = _load_clients()
    slug = record["slug"]
    existing = next((c for c in clients if c["slug"] == slug), None)
    if existing:
        existing.update({k: v for k, v in record.items() if v is not None})
    else:
        clients.append(record)
    _save_clients(clients)


class LoginRequest(BaseModel):
    password: str

class DiscoverRequest(BaseModel):
    city: str
    business_type: str
    radius_km: int = 15
    max_results: int = 50

class PipelineRequest(BaseModel):
    name: str
    address: str
    phases: list[int] = [2, 3, 4, 5]
    category: str = ""
    city: str = ""
    existing_website: str | None = None
    phone: str = ""
    rating: float | None = None
    review_count: int = 0


def require_auth(request: Request):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token or token not in VALID_TOKENS:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token


class _JobLogger:
    def __init__(self, job_id, real_stdout):
        self._job_id = job_id
        self._real   = real_stdout
    def write(self, text):
        self._real.write(text)
        msg = text.strip()
        if msg:
            JOBS[self._job_id]["logs"].append({"ts": datetime.now().strftime("%H:%M:%S"), "msg": msg})
    def flush(self):
        self._real.flush()


@contextmanager
def _capture(job_id):
    old = sys.stdout
    sys.stdout = _JobLogger(job_id, old)
    try:
        yield
    finally:
        sys.stdout = old


def _new_job(description):
    job_id = secrets.token_hex(8)
    JOBS[job_id] = {"id": job_id, "description": description, "status": "queued",
                    "logs": [], "result": None, "error": None, "created_at": datetime.now().isoformat()}
    return job_id


def _run(job_id, fn, *args, **kwargs):
    def _target():
        JOBS[job_id]["status"] = "running"
        try:
            with _capture(job_id):
                result = fn(*args, **kwargs)
            JOBS[job_id]["status"]  = "done"
            JOBS[job_id]["result"] = result
        except NotImplementedError:
            JOBS[job_id]["status"] = "not_implemented"
            JOBS[job_id]["error"]  = "Phase not yet implemented."
            JOBS[job_id]["logs"].append({"ts": datetime.now().strftime("%H:%M:%S"),
                                          "msg": "Phase not yet implemented - scaffold only."})
        except Exception as exc:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"]  = str(exc)
            JOBS[job_id]["logs"].append({"ts": datetime.now().strftime("%H:%M:%S"), "msg": f"Error: {exc}"})
    threading.Thread(target=_target, daemon=True).start()


def _slug(name: str) -> str:
    """Canonical slug — must match build.py/_slugify and dashboard JS slugify()."""
    import re
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)   # strip &, (, ), etc.
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")[:60]


def _city_from_address(address: str) -> str:
    """Extract the city from an address like '4493 Boundary Road, Vancouver, BC'."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",")]
    # Drop a trailing province/postal token like 'BC' or 'BC V5K 1A1'
    parts = [p for p in parts if p and p.upper() not in ("BC", "B.C.") and not p.upper().startswith("BC ")]
    return parts[-1] if parts else ""


@app.get("/", response_class=HTMLResponse)
async def serve_login():
    return HTMLResponse((WEB_DIR / "login.html").read_text(encoding="utf-8"))

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    return HTMLResponse((WEB_DIR / "dashboard.html").read_text(encoding="utf-8"))

@app.post("/auth/login")
async def login(data: LoginRequest):
    if data.password != os.getenv("ADMIN_PASSWORD", "changeme"):
        raise HTTPException(status_code=401, detail="Wrong password")
    token = secrets.token_hex(32)
    VALID_TOKENS.add(token)
    return {"token": token}

@app.get("/auth/check")
async def check_auth(request: Request):
    require_auth(request); return {"ok": True}

@app.post("/auth/logout")
async def logout(request: Request):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    VALID_TOKENS.discard(token); return {"ok": True}

@app.post("/api/discover")
async def start_discovery(data: DiscoverRequest, request: Request):
    require_auth(request)
    from discovery import discover_businesses, save_leads
    job_id = _new_job(f"Discover: {data.business_type} in {data.city}, BC")
    def _go():
        print(f"[Phase 1] Searching: {data.business_type} in {data.city}, BC")
        leads = discover_businesses(data.city, data.business_type, data.radius_km, data.max_results)
        save_leads(leads, str(OUTPUT_DIR))
        print(f"[Phase 1] Complete - {len(leads)} leads found")
        return {"leads_count": len(leads), "leads": leads}
    _run(job_id, _go)
    return {"job_id": job_id}

@app.get("/api/leads")
async def get_leads(request: Request):
    require_auth(request)
    path = OUTPUT_DIR / "leads.json"
    return {"leads": json.loads(path.read_text()) if path.exists() else []}

@app.post("/api/pipeline/{slug}")
async def run_pipeline(slug: str, data: PipelineRequest, request: Request):
    require_auth(request)
    job_id   = _new_job(f"Pipeline: {data.name}")
    business = {
        "name": data.name,
        "address": data.address,
        "slug": slug,
        "category": data.category,
        "business_type": data.category,
        "city": data.city or _city_from_address(data.address),
        "existing_website": data.existing_website,
        "phone": data.phone,
        "rating": data.rating,
        "review_count": data.review_count,
    }
    def _go():
        results     = {}
        profile_dir = str(RESEARCH_DIR / _slug(data.name))
        site_dir    = str(OUTPUT_DIR   / _slug(data.name))
        if 2 in data.phases:
            from scrape import build_profile
            print(f"[Phase 2] Scraping profile for {data.name}...")
            profile_dir = str(build_profile(business, str(RESEARCH_DIR)))
            results["profile_dir"] = profile_dir
        if 3 in data.phases:
            from build import build_website
            print(f"[Phase 3] Building website for {data.name}...")
            site_dir = str(build_website(profile_dir, str(OUTPUT_DIR)))
            results["site_dir"] = site_dir
        if 4 in data.phases:
            from audit import run_audit
            print(f"[Phase 4] Generating audit PDF for {data.name}...")
            results["pdf_path"] = str(run_audit(profile_dir, str(OUTPUT_DIR)))
        if 5 in data.phases:
            from deploy import deploy_site
            print(f"[Phase 5] Deploying {data.name}...")
            results["deployment"] = deploy_site(site_dir, business)
        # Persist client record
        deployment = results.get("deployment") or {}
        live_url   = deployment.get("live_url")
        portal_url = deployment.get("portal_url") or (f"{live_url}/portal.html" if live_url else f"/portal/{slug}")
        _upsert_client({
            "slug":         slug,
            "name":         data.name,
            "address":      data.address,
            "phone":        data.phone,
            "category":     data.category,
            "status":       "prospect",
            "created_at":   datetime.now().isoformat(),
            "has_site":     bool(results.get("site_dir")),
            "has_pdf":      bool(results.get("pdf_path")),
            "live_url":     live_url,
            "portal_url":   portal_url,
        })
        return results
    _run(job_id, _go)
    return {"job_id": job_id}

@app.get("/api/jobs")
async def list_jobs(request: Request):
    require_auth(request)
    return {"jobs": sorted(JOBS.values(), key=lambda j: j["created_at"], reverse=True)}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    require_auth(request)
    job = JOBS.get(job_id)
    if not job: raise HTTPException(status_code=404)
    return job

@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str, token: str = Query(...)):
    if not token or token not in VALID_TOKENS: raise HTTPException(status_code=401)
    async def _gen():
        last = 0
        while True:
            job  = JOBS.get(job_id)
            if not job: break
            logs = job.get("logs", [])
            for entry in logs[last:]:
                yield f"data: {json.dumps({'type': 'log', 'entry': entry})}\n\n"
            last = len(logs)
            if job["status"] in ("done", "error", "not_implemented"):
                yield f"data: {json.dumps({'type': 'done', 'status': job['status'], 'result': job.get('result'), 'error': job.get('error')})}\n\n"
                break
            await asyncio.sleep(0.3)
    return StreamingResponse(_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/api/output/{slug}/pdf")
async def download_pdf(slug: str, request: Request):
    require_auth(request)
    path = OUTPUT_DIR / slug / "ai_opportunity_report.pdf"
    if not path.exists(): raise HTTPException(status_code=404, detail="PDF not found - run Phase 4 first")
    return FileResponse(str(path), media_type="application/pdf", filename=f"{slug}-ai-opportunity-report.pdf")

@app.get("/api/output/{slug}/deployment")
async def get_deployment(slug: str, request: Request):
    require_auth(request)
    path = OUTPUT_DIR / slug / "deployment.json"
    return json.loads(path.read_text()) if path.exists() else {"live_url": None}

@app.get("/preview/{slug}/{file_path:path}")
async def preview_site(slug: str, file_path: str = "index.html"):
    """Serve a generated site's files for in-dashboard preview (localhost only)."""
    site_root = (OUTPUT_DIR / slug).resolve()
    target = (site_root / (file_path or "index.html")).resolve()
    if target.is_dir():
        target = target / "index.html"
    # Block path traversal outside the site directory
    if not str(target).startswith(str(site_root)):
        raise HTTPException(status_code=403)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found - run Phase 3 first")
    return FileResponse(str(target))


# ── Client database ──────────────────────────────────────────────────────────

@app.get("/api/clients")
async def list_clients(request: Request):
    require_auth(request)
    return {"clients": _load_clients()}

class ClientPatch(BaseModel):
    status: str | None = None
    notes: str | None = None
    name: str | None = None
    phone: str | None = None
    address: str | None = None

@app.patch("/api/clients/{slug}")
async def update_client(slug: str, data: ClientPatch, request: Request):
    require_auth(request)
    clients = _load_clients()
    client = next((c for c in clients if c["slug"] == slug), None)
    if not client:
        raise HTTPException(status_code=404)
    for k, v in data.model_dump(exclude_none=True).items():
        client[k] = v
    _save_clients(clients)
    return client

@app.get("/api/clients/export.csv")
async def export_clients_csv(request: Request, token: str = Query(default="")):
    t = token or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not t or t not in VALID_TOKENS:
        raise HTTPException(status_code=401)
    import csv, io
    clients = _load_clients()
    buf = io.StringIO()
    fields = ["name", "slug", "address", "phone", "category", "status",
              "live_url", "portal_url", "created_at"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(clients)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clients.csv"},
    )


# ── Site editor ───────────────────────────────────────────────────────────────

@app.get("/api/output/{slug}/site")
async def get_site_html(slug: str, request: Request):
    require_auth(request)
    path = OUTPUT_DIR / slug / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Site not built yet")
    return {"html": path.read_text(encoding="utf-8", errors="replace")}

@app.put("/api/output/{slug}/site")
async def save_site_html(slug: str, request: Request):
    require_auth(request)
    body = await request.json()
    html = body.get("html", "")
    path = OUTPUT_DIR / slug / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Site directory not found")
    path.write_text(html, encoding="utf-8")
    return {"ok": True}


# ── Customization layer ─────────────────────────────────────────────────────

def _customize_path(slug: str) -> Path:
    return OUTPUT_DIR / slug / "customize.json"


def _parse_reviews(raw: str) -> list:
    """Parse pasted Google-reviews text into structured review objects.

    Handles common copy formats: blocks separated by blank lines, star ratings
    written as '5 stars' / '★★★★★' / 'Rated 5.0', a reviewer-name line often
    followed by 'a month ago' / '2 reviews', and the longest line as the text.
    Falls back to one review per blank-line block (rating 5, generic name).
    """
    import re as _re

    if not raw or not raw.strip():
        return []

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Split into blocks on blank lines
    blocks = [b for b in _re.split(r"\n\s*\n", text) if b.strip()]

    # If the paste is one big block with no blank-line separators, try to
    # split on repeated star runs as block boundaries.
    if len(blocks) == 1 and text.count("★") >= 2:
        parts = _re.split(r"(?=★)", text)
        merged, buf = [], ""
        for p in parts:
            buf += p
            if buf.count("★") >= 1 and len(buf.strip()) > 40:
                merged.append(buf); buf = ""
        if buf.strip():
            merged.append(buf)
        if len(merged) > 1:
            blocks = merged

    star_word_re = _re.compile(r"\b([1-5])(?:\.0)?\s*stars?\b", _re.I)
    rated_re     = _re.compile(r"\brated\s+([1-5])(?:\.0)?\b", _re.I)
    meta_re      = _re.compile(
        r"(a|\d+)\s+(day|days|week|weeks|month|months|year|years)\s+ago"
        r"|\d+\s+reviews?|\d+\s+photos?|local guide|\blike\b|\bshare\b",
        _re.I,
    )
    name_re = _re.compile(r"^[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3}$")

    reviews = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue

        # --- rating ---
        rating = None
        joined = " ".join(lines)
        stars = max((ln.count("★") for ln in lines), default=0)
        if stars and stars <= 5:
            rating = stars
        if rating is None:
            m = star_word_re.search(joined) or rated_re.search(joined)
            if m:
                rating = int(m.group(1))
        if rating is None:
            rating = 5

        # --- name: first short line that looks like a person's name ---
        name = None
        for ln in lines:
            clean = ln.strip()
            if "★" in clean or star_word_re.search(clean) or rated_re.search(clean):
                continue
            if meta_re.search(clean):
                continue
            if len(clean.split()) <= 4 and name_re.match(clean):
                name = clean
                break
        if not name:
            name = "Google Reviewer"

        # --- text: longest line that isn't the name / rating / meta ---
        candidates = []
        for ln in lines:
            clean = ln.strip()
            if clean == name:
                continue
            stripped = clean.replace("★", "").replace("☆", "").strip()
            if not stripped:
                continue
            if star_word_re.fullmatch(stripped) or rated_re.fullmatch(stripped):
                continue
            if meta_re.search(stripped) and len(stripped.split()) <= 4:
                continue
            candidates.append(stripped)
        text_val = max(candidates, key=len) if candidates else block.strip()

        reviews.append({
            "name": name,
            "rating": rating,
            "text": text_val,
            "location": "",
        })

    return reviews


@app.get("/api/customize/{slug}")
async def get_customize(slug: str, request: Request):
    require_auth(request)
    path = _customize_path(slug)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


@app.put("/api/customize/{slug}")
async def save_customize(slug: str, request: Request):
    require_auth(request)
    body = await request.json()
    site_dir = OUTPUT_DIR / slug
    site_dir.mkdir(parents=True, exist_ok=True)
    _customize_path(slug).write_text(
        json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "slug": slug}


@app.post("/api/customize/{slug}/parse-reviews")
async def parse_reviews_endpoint(slug: str, request: Request):
    require_auth(request)
    body = await request.json()
    raw = body.get("raw", "") if isinstance(body, dict) else ""
    return {"reviews": _parse_reviews(raw)}


@app.post("/api/customize/{slug}/rebuild")
async def rebuild_customize(slug: str, request: Request):
    require_auth(request)
    profile_dir = RESEARCH_DIR / slug
    if not (profile_dir / "profile.json").exists():
        raise HTTPException(
            status_code=400,
            detail=f"No research profile found for '{slug}'. Run Phase 2 first.")
    from build import build_website
    site_dir = build_website(str(profile_dir), str(OUTPUT_DIR))
    return {"ok": True, "site_dir": str(site_dir),
            "preview_url": f"/preview/{slug}/index.html"}


# ── Public client portal (no auth — shareable with prospects) ────────────────

def _portal_business_name(slug: str) -> str:
    profile = RESEARCH_DIR / slug / "profile.json"
    if profile.exists():
        try:
            return json.loads(profile.read_text(encoding="utf-8", errors="replace")).get("name", slug)
        except Exception:
            pass
    return slug.replace("-", " ").title()


@app.get("/portal/{slug}", response_class=HTMLResponse)
async def serve_portal(slug: str):
    portal = WEB_DIR / "portal.html"
    if not portal.exists():
        raise HTTPException(status_code=404, detail="Portal page not found")
    return HTMLResponse(portal.read_text(encoding="utf-8"))


@app.get("/api/portal/{slug}")
async def portal_info(slug: str):
    site_dir   = OUTPUT_DIR / slug
    pdf_path   = site_dir / "ai_opportunity_report.pdf"
    deploy_path = site_dir / "deployment.json"
    live_url   = None
    if deploy_path.exists():
        try:
            live_url = json.loads(deploy_path.read_text()).get("live_url")
        except Exception:
            pass
    # Public share URL: prefer deployed portal.html, fall back to localhost
    share_url = (f"{live_url}/portal.html" if live_url else None)
    return {
        "slug":          slug,
        "name":          _portal_business_name(slug),
        "has_site":      (site_dir / "index.html").exists(),
        "has_pdf":       pdf_path.exists(),
        "live_url":      live_url,
        "share_url":     share_url,
        "preview_url":   f"/preview/{slug}/index.html",
        "pdf_url":       f"/portal/{slug}/pdf",
        "agency_name":   os.getenv("AGENCY_NAME", "Victoria AI"),
        "booking_url":   os.getenv("PORTAL_BOOKING_URL", ""),
        "contact_email": os.getenv("PORTAL_CONTACT_EMAIL", ""),
    }


@app.get("/portal/{slug}/pdf")
async def portal_pdf(slug: str):
    path = OUTPUT_DIR / slug / "ai_opportunity_report.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(str(path), media_type="application/pdf",
                        filename=f"{slug}-opportunity-report.pdf")


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)
    RESEARCH_DIR.mkdir(exist_ok=True)
    port = int(os.getenv("PORT", 5000))
    print(f"""
+----------------------------------------------+
|   BCBUISWEBBUILDERTOOL  Admin Server         |
+----------------------------------------------+
|   Open:  http://localhost:{port}                 |
|   Password: set ADMIN_PASSWORD in .env       |
+----------------------------------------------+
""")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True,
                reload_dirs=[str(Path(__file__).parent)])
