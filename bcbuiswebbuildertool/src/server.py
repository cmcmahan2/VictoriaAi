"""
Pacific Web Builder - Admin Web Server

FastAPI backend serving the admin dashboard and pipeline API.

Usage:
    python src/server.py
    Open: http://localhost:5000

Set ADMIN_PASSWORD in .env before running.
"""

import asyncio
import calendar
import io
import json
import os
import secrets
import shutil
import sys
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

import jobs_db
from logging_config import get_logger, log_path, setup_logging

log = get_logger("server")

OUTPUT_DIR   = Path("./output")
RESEARCH_DIR = Path("./research")
WEB_DIR      = Path(__file__).parent / "web"
CLIENTS_FILE = OUTPUT_DIR / "clients.json"

# Max accepted .zip upload (compressed). Also caps total *uncompressed* bytes to
# guard against zip bombs. Override with MAX_UPLOAD_MB in the environment.
MAX_UPLOAD_MB    = int(os.getenv("MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
# Files permitted inside an uploaded site zip. Anything else (executables,
# archives, etc.) is rejected. Dotfiles and __MACOSX/ cruft are skipped, not
# rejected, so macOS-created zips still import cleanly.
ALLOWED_UPLOAD_EXTS = {
    "html", "htm", "css", "js", "mjs", "json", "txt", "md", "xml",
    "webmanifest", "map", "svg", "png", "jpg", "jpeg", "gif", "webp",
    "avif", "ico", "bmp", "woff", "woff2", "ttf", "otf", "eot",
}

VALID_TOKENS: set[str] = set()
JOBS: dict[str, dict]  = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    OUTPUT_DIR.mkdir(exist_ok=True)
    RESEARCH_DIR.mkdir(exist_ok=True)
    setup_logging()
    jobs_db.configure(OUTPUT_DIR / "jobs.db")
    jobs_db.init()
    for job in jobs_db.load_all():
        if job["status"] == "running":
            job["status"] = "interrupted"
            job["logs"].append({
                "ts": datetime.now().strftime("%H:%M:%S"),
                "msg": "Job interrupted by server restart.",
            })
            jobs_db.upsert(job)
        JOBS[job["id"]] = job
    yield


app = FastAPI(title="Pacific Web Builder Admin", docs_url=None, redoc_url=None,
              lifespan=lifespan)


# Guards read-modify-write cycles on clients.json: pipeline jobs finish on
# worker threads while dashboard PATCH/DELETE requests run on the event loop,
# so unsynchronized writes can silently drop a client record.
_CLIENTS_LOCK = threading.Lock()


def _load_clients() -> list:
    if CLIENTS_FILE.exists():
        try:
            return json.loads(CLIENTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_clients(clients: list):
    OUTPUT_DIR.mkdir(exist_ok=True)
    tmp = CLIENTS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clients, indent=2), encoding="utf-8")
    tmp.replace(CLIENTS_FILE)  # atomic — a crash mid-write can't corrupt the db


def _upsert_client(record: dict):
    with _CLIENTS_LOCK:
        clients = _load_clients()
        slug = record["slug"]
        existing = next((c for c in clients if c.get("slug") == slug), None)
        if existing:
            # Never rewind the follow-up clock on a re-save of the same client.
            updates = {k: v for k, v in record.items() if v is not None}
            if "created_at" in existing:
                updates.pop("created_at", None)
            existing.update(updates)
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
    max_tier: int = 3  # region sweep depth: 1=top metros, 2=+mid-size, 3=all

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

class ImportSiteRequest(BaseModel):
    url: str
    phases: list[int] = [2, 3]   # 2=scrape, 3=build; add 4 (audit) / 5 (deploy) if wanted

class SweepRequest(BaseModel):
    region: str                    # "All of BC", "All of Canada", province name, or city
    business_types: list[str]      # one type per element, e.g. ["plumber", "dentist"]
    max_results: int = 15          # per city per type
    max_tier: int = 2              # sweep depth: 1=top metros, 2=+mid-size, 3=all


def require_auth(request: Request):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token or token not in VALID_TOKENS:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token


class _JobLogger:
    def __init__(self, job_id, real_stdout):
        self._job_id = job_id
        self._real   = real_stdout
        self._since_flush = 0

    def write(self, text):
        self._real.write(text)
        msg = text.strip()
        if msg:
            job = JOBS[self._job_id]
            job["logs"].append({"ts": datetime.now().strftime("%H:%M:%S"), "msg": msg})
            self._since_flush += 1
            # Persist every 5 log entries to avoid overwhelming SQLite on verbose jobs
            if self._since_flush >= 5:
                jobs_db.upsert(job)
                self._since_flush = 0

    def flush(self):
        self._real.flush()
        # Flush any buffered log entries
        if self._since_flush > 0:
            jobs_db.upsert(JOBS[self._job_id])
            self._since_flush = 0


class _ThreadStdoutRouter:
    """A process-wide stdout proxy that routes writes per-thread.

    The old approach swapped sys.stdout globally per job, so two concurrent
    jobs cross-contaminated each other's logs, and whichever finished first
    restored stdout out from under the other. This router is installed once;
    each job thread registers its own _JobLogger and unrelated threads
    (uvicorn, other jobs) keep writing to the real stdout.
    """

    def __init__(self, real):
        self.real = real
        self._routes: dict[int, object] = {}

    def register(self, logger):
        self._routes[threading.get_ident()] = logger

    def unregister(self):
        self._routes.pop(threading.get_ident(), None)

    def _target(self):
        return self._routes.get(threading.get_ident()) or self.real

    def write(self, text):
        self._target().write(text)

    def flush(self):
        self._target().flush()

    def __getattr__(self, name):  # delegate isatty(), encoding, etc.
        return getattr(self.real, name)


_stdout_router: _ThreadStdoutRouter | None = None


@contextmanager
def _capture(job_id):
    global _stdout_router
    if _stdout_router is None or sys.stdout is not _stdout_router:
        _stdout_router = _ThreadStdoutRouter(sys.stdout)
        sys.stdout = _stdout_router
    logger = _JobLogger(job_id, _stdout_router.real)
    _stdout_router.register(logger)
    try:
        yield
    finally:
        logger.flush()  # persist any buffered log entries
        _stdout_router.unregister()


def _new_job(description):
    job_id = secrets.token_hex(8)
    JOBS[job_id] = {
        "id":          job_id,
        "description": description,
        "status":      "queued",
        "logs":        [],
        "result":      None,
        "error":       None,
        "created_at":  datetime.now().isoformat(),
        "finished_at": None,
    }
    jobs_db.upsert(JOBS[job_id])
    return job_id


def _run(job_id, fn, *args, **kwargs):
    def _target():
        JOBS[job_id]["status"] = "running"
        jobs_db.upsert(JOBS[job_id])
        try:
            with _capture(job_id):
                result = fn(*args, **kwargs)
            JOBS[job_id]["status"]      = "done"
            JOBS[job_id]["result"]      = result
            JOBS[job_id]["finished_at"] = datetime.now().isoformat()
        except NotImplementedError:
            JOBS[job_id]["status"]      = "not_implemented"
            JOBS[job_id]["error"]       = "Phase not yet implemented."
            JOBS[job_id]["finished_at"] = datetime.now().isoformat()
            JOBS[job_id]["logs"].append({
                "ts": datetime.now().strftime("%H:%M:%S"),
                "msg": "Phase not yet implemented - scaffold only.",
            })
        except Exception as exc:
            JOBS[job_id]["status"]      = "error"
            JOBS[job_id]["error"]       = str(exc)
            JOBS[job_id]["finished_at"] = datetime.now().isoformat()
            JOBS[job_id]["logs"].append({
                "ts": datetime.now().strftime("%H:%M:%S"),
                "msg": f"Error: {exc}",
            })
        finally:
            jobs_db.upsert(JOBS[job_id])
    threading.Thread(target=_target, daemon=True).start()


def _slug(name: str) -> str:
    """Canonical slug — must match build.py/_slugify and dashboard JS slugify()."""
    import re
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)   # strip &, (, ), etc.
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")[:60]


import re as _re_slug

_SLUG_RE = _re_slug.compile(r"^[\w-]{1,80}$")


def _safe_slug(slug: str) -> str:
    """Validate a slug from a URL/body before it is used in a filesystem path.

    Slugs are single path segments, but '..', '.', '~' or empty values could
    still escape output/ or research/. 400 on anything suspicious.
    """
    if not slug or slug in (".", "..") or not _SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="Invalid client slug.")
    return slug


_PROVINCES = {"BC", "B.C.", "AB", "SK", "MB", "ON", "QC", "NB", "NS", "PE",
              "NL", "YT", "NT", "NU"}


def _city_from_address(address: str) -> str:
    """Extract the city from an address like '4493 Boundary Rd, Vancouver, BC'.

    Handles every Canadian province/territory code (with or without a trailing
    postal code) and 'Canada' — not just BC.
    """
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",")]

    def _is_region_token(p: str) -> bool:
        up = p.upper()
        if up in _PROVINCES or up == "CANADA":
            return True
        first = up.split()[0] if up.split() else ""
        # 'BC V5K 1A1' / 'ON M5V 2T6' style tokens
        return first in _PROVINCES
    parts = [p for p in parts if p and not _is_region_token(p)]
    return parts[-1] if parts else ""


@app.get("/", response_class=HTMLResponse)
async def serve_login():
    return HTMLResponse((WEB_DIR / "login.html").read_text(encoding="utf-8"))

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    return HTMLResponse((WEB_DIR / "dashboard.html").read_text(encoding="utf-8"))

@app.post("/auth/login")
async def login(data: LoginRequest):
    expected = os.getenv("ADMIN_PASSWORD", "changeme")
    if not secrets.compare_digest(data.password.encode(), expected.encode()):
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

@app.get("/api/health")
async def health_check(request: Request):
    """Report which API keys are configured and the readiness of each pipeline
    phase. Safe to call on startup to confirm the env before a live run."""
    require_auth(request)
    from pathlib import Path as _P

    def _key(name: str) -> dict:
        val = os.getenv(name, "")
        present = bool(val.strip())
        # Show a redacted suffix so the user can spot a copy-paste mistake
        preview = (val[-6:] if len(val) >= 6 else "…") if present else None
        return {"present": present, "preview": f"…{preview}" if preview else None}

    google  = _key("GOOGLE_MAPS_API_KEY")
    anthro  = _key("ANTHROPIC_API_KEY")
    netlify = _key("NETLIFY_AUTH_TOKEN")
    fsq     = _key("FOURSQUARE_API_KEY")

    phases = {
        "1_discover": {
            "ready": google["present"],
            "note": "Google Places (Tier 1)" if google["present"] else "OSM only — no GOOGLE_MAPS_API_KEY",
        },
        "2_scrape": {
            "ready": True,
            "note": "No key required",
        },
        "3_build": {
            "ready": anthro["present"],
            "note": "Claude AI copy" if anthro["present"] else "Template fallback — no ANTHROPIC_API_KEY",
        },
        "4_audit": {
            "ready": anthro["present"],
            "note": "Claude AI report" if anthro["present"] else "Template fallback — no ANTHROPIC_API_KEY",
        },
        "5_deploy": {
            "ready": netlify["present"],
            "note": "Netlify auto-deploy" if netlify["present"] else "Manual deploy — no NETLIFY_AUTH_TOKEN",
        },
    }
    all_core = google["present"] and anthro["present"] and netlify["present"]
    return {
        "ready":    all_core,
        "summary":  "All systems go" if all_core else "Some API keys missing — check phases",
        "keys": {
            "GOOGLE_MAPS_API_KEY": google,
            "ANTHROPIC_API_KEY":   anthro,
            "NETLIFY_AUTH_TOKEN":  netlify,
            "FOURSQUARE_API_KEY":  fsq,
        },
        "phases":   phases,
        "db": {
            "jobs_db":   str(OUTPUT_DIR / "jobs.db"),
            "cache_db":  os.getenv("CACHE_DB", "./output/cache.db"),
            "log_file":  str(log_path()),
        },
    }

@app.get("/api/discover")
async def discover_info(request: Request):
    """Stub — discovery is triggered via POST /api/discover, not GET."""
    require_auth(request)
    raise HTTPException(status_code=501, detail="Not Implemented: use POST /api/discover to start a discovery job")

@app.post("/api/discover")
async def start_discovery(data: DiscoverRequest, request: Request):
    require_auth(request)
    import regions
    from discovery import discover_businesses, save_leads
    where = regions.region_label(data.city, data.max_tier)
    job_id = _new_job(f"Discover: {data.business_type} in {where}")
    def _go():
        log.info(f"[Phase 1] Searching: {data.business_type} in {where}")
        leads = discover_businesses(data.city, data.business_type, data.radius_km, data.max_results, data.max_tier)
        save_leads(leads, str(OUTPUT_DIR))
        log.info(f"[Phase 1] Complete - {len(leads)} leads found")
        return {"leads_count": len(leads), "leads": leads}
    _run(job_id, _go)
    return {"job_id": job_id}

@app.get("/api/leads")
async def get_leads(request: Request):
    require_auth(request)
    path = OUTPUT_DIR / "leads.json"
    return {"leads": json.loads(path.read_text()) if path.exists() else []}


@app.post("/api/sweep")
async def start_sweep(data: SweepRequest, request: Request):
    require_auth(request)
    import time as _time
    import regions as _regions
    from discovery import discover_businesses, save_leads

    btypes = [t.strip() for t in data.business_types if t.strip()]
    if not btypes:
        raise HTTPException(status_code=400, detail="At least one business type required")

    label  = _regions.region_label(data.region, data.max_tier)
    prefix = ", ".join(btypes[:3]) + ("…" if len(btypes) > 3 else "")
    job_id = _new_job(f"Sweep: {prefix} in {label}")

    def _go():
        region_data = _regions.resolve_region(data.region, data.max_tier)
        cities = region_data["cities"] if region_data else [data.region]
        total  = len(btypes) * len(cities)
        done   = 0
        all_leads: list[dict] = []

        # Restore checkpoint when resuming an interrupted sweep
        prev = JOBS[job_id].get("result") or {}
        completed: set[str] = set(prev.get("completed_pairs", []))
        if completed:
            log.info(f"[sweep] Resuming — {len(completed)}/{total} pairs already done")

        def _checkpoint(current: str = ""):
            JOBS[job_id]["result"] = {
                "done_pairs":      done,
                "total_pairs":     total,
                "progress_pct":    round(100 * done / total) if total else 100,
                "leads_found":     len(all_leads),
                "current":         current,
                "completed_pairs": list(completed),
                "region":          data.region,
                "business_types":  btypes,
            }
            jobs_db.upsert(JOBS[job_id])

        _checkpoint("Starting…")
        log.info(f"[sweep] {len(btypes)} type(s) × {len(cities)} cities = {total} search pairs")

        for bt in btypes:
            for city in cities:
                pair_key = f"{bt}|{city}"
                if pair_key in completed:
                    done += 1
                    continue

                # Pause check — cooperative, checked between pairs
                if JOBS[job_id].get("pause_requested"):
                    JOBS[job_id]["status"] = "paused"
                    _checkpoint(f"Paused before: {bt} in {city}")
                    log.info(f"[sweep] Paused. POST /api/jobs/{job_id}/resume to continue.")
                    while JOBS[job_id].get("pause_requested"):
                        _time.sleep(1)
                    JOBS[job_id]["status"] = "running"
                    jobs_db.upsert(JOBS[job_id])
                    log.info(f"[sweep] Resumed.")

                current = f"{bt} in {city}"
                log.info(f"[sweep] [{done + 1}/{total}] {current}")
                _checkpoint(current)

                try:
                    leads = discover_businesses(city, bt, 15, data.max_results, data.max_tier)
                    all_leads.extend(leads)
                    log.info(f"[sweep] +{len(leads)} leads (total {len(all_leads)})")
                except Exception as exc:
                    log.info(f"[sweep] Error for {current}: {exc}")

                completed.add(pair_key)
                done += 1

                # Write leads progressively so partial results survive a restart
                try:
                    save_leads(all_leads, str(OUTPUT_DIR))
                except Exception:
                    pass

        _checkpoint("Complete")
        log.info(f"[sweep] Done — {len(all_leads)} total leads across {done} pairs.")
        return {
            "total_leads":   len(all_leads),
            "pairs_run":     done,
            "region":        data.region,
            "business_types": btypes,
        }

    _run(job_id, _go)
    return {"job_id": job_id}


@app.post("/api/jobs/{job_id}/pause")
async def pause_job(job_id: str, request: Request):
    require_auth(request)
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404)
    if job["status"] != "running":
        raise HTTPException(status_code=400, detail=f"Job is '{job['status']}', not running")
    job["pause_requested"] = True
    return {"ok": True, "job_id": job_id, "msg": "Pause will take effect after the current search pair completes."}


@app.post("/api/jobs/{job_id}/resume")
async def resume_job(job_id: str, request: Request):
    require_auth(request)
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404)
    if job["status"] not in ("paused", "running"):
        raise HTTPException(status_code=400, detail=f"Job is '{job['status']}', cannot resume")
    job["pause_requested"] = False
    return {"ok": True, "job_id": job_id, "msg": "Sweep will resume after the next poll cycle."}

@app.post("/api/pipeline/{slug}")
async def run_pipeline(slug: str, data: PipelineRequest, request: Request):
    require_auth(request)
    # Canonicalize: the build/scrape phases derive their folder names from the
    # business name, so the client record MUST use the same slug or the
    # dashboard registers a client whose Preview/PDF/portal point at a folder
    # that doesn't exist ("careful-painting-vancouver" bug).
    slug = _slug(data.name) or slug
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
            log.info(f"[Phase 2] Scraping profile for {data.name}...")
            profile_dir = str(build_profile(business, str(RESEARCH_DIR)))
            results["profile_dir"] = profile_dir
        if 3 in data.phases:
            from build import build_website
            log.info(f"[Phase 3] Building website for {data.name}...")
            site_dir = str(build_website(profile_dir, str(OUTPUT_DIR)))
            results["site_dir"] = site_dir
        if 4 in data.phases:
            from audit import run_audit
            log.info(f"[Phase 4] Generating audit PDF for {data.name}...")
            results["pdf_path"] = str(run_audit(profile_dir, str(OUTPUT_DIR)))
        if 5 in data.phases:
            from deploy import deploy_site
            readiness = deploy_readiness(slug)
            for issue in readiness["issues"]:
                log.warning(f"[Phase 5] ⚠ {issue['label']}: {issue['hint']}")
            if readiness["issues"]:
                log.warning("[Phase 5] Deploying anyway — fix the above in the "
                            "Customize tab and redeploy before showing the client.")
            log.info(f"[Phase 5] Deploying {data.name}...")
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

@app.get("/api/logs")
async def tail_logs(request: Request, lines: int = Query(default=200, ge=1, le=5000)):
    """Tail the rotating server log file. Reads only the last chunk so a large
    log doesn't have to be loaded into memory."""
    require_auth(request)
    path = log_path()
    if not path.exists():
        return {"path": str(path), "lines": [], "note": "No log file yet."}
    # Read the tail efficiently: seek back a bounded number of bytes.
    max_bytes = lines * 400  # generous per-line budget
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > max_bytes:
            f.seek(-max_bytes, os.SEEK_END)
            f.readline()  # discard a partial first line
        tail = f.read().decode("utf-8", errors="replace")
    out = tail.splitlines()[-lines:]
    return {"path": str(path), "lines": out}

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
            if job["status"] in ("done", "error", "not_implemented", "interrupted"):
                yield f"data: {json.dumps({'type': 'done', 'status': job['status'], 'result': job.get('result'), 'error': job.get('error')})}\n\n"
                break
            await asyncio.sleep(0.3)
    return StreamingResponse(_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/api/output/{slug}/pdf")
async def download_pdf(slug: str, request: Request):
    require_auth(request)
    slug = _safe_slug(slug)
    path = OUTPUT_DIR / slug / "ai_opportunity_report.pdf"
    if not path.exists(): raise HTTPException(status_code=404, detail="PDF not found - run Phase 4 first")
    return FileResponse(str(path), media_type="application/pdf", filename=f"{slug}-ai-opportunity-report.pdf")

@app.get("/api/output/{slug}/deployment")
async def get_deployment(slug: str, request: Request):
    require_auth(request)
    slug = _safe_slug(slug)
    path = OUTPUT_DIR / slug / "deployment.json"
    return json.loads(path.read_text()) if path.exists() else {"live_url": None}

@app.get("/preview/{slug}/{file_path:path}")
async def preview_site(slug: str, file_path: str = "index.html"):
    """Serve a generated site's files for in-dashboard preview (localhost only)."""
    slug = _safe_slug(slug)
    site_root = (OUTPUT_DIR / slug).resolve()
    target = (site_root / (file_path or "index.html")).resolve()
    if target.is_dir():
        target = target / "index.html"
    # Block path traversal outside the site directory (is_relative_to avoids
    # the classic prefix bug where /output/foo-evil passes for slug 'foo')
    if not target.is_relative_to(site_root):
        raise HTTPException(status_code=403)
    if not target.exists():
        # Friendly page (instead of raw JSON) so the preview iframe is helpful.
        return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body{{margin:0;font-family:system-ui,Segoe UI,sans-serif;background:#0f1720;color:#e6edf3;
    display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center}}
  .box{{max-width:440px;padding:2rem}}
  h1{{font-size:1.3rem;margin:0 0 .6rem}} p{{color:#9fb0c0;line-height:1.6;margin:0 0 1rem}}
  .slug{{font-family:monospace;background:#1c2733;padding:.15rem .4rem;border-radius:5px;color:#7ee2b8}}
  .steps{{text-align:left;background:#1c2733;border-radius:10px;padding:1rem 1.25rem;font-size:.92rem}}
  .steps li{{margin:.35rem 0}}
</style></head><body><div class="box">
  <div style="font-size:2.4rem;margin-bottom:.5rem">🖌️</div>
  <h1>No site built yet for <span class="slug">{slug}</span></h1>
  <p>This client doesn't have a website in <code>output/{slug}/</code> yet. To add one:</p>
  <ol class="steps">
    <li>Go to the <b>Customize</b> tab</li>
    <li>Use <b>Upload a site (.zip)</b> or <b>Paste a site from Claude Design</b></li>
    <li>Type the name so the slug matches <span class="slug">{slug}</span>, tick <b>Overwrite</b></li>
    <li>Or run the pipeline (<b>Build</b>) to generate one</li>
  </ol>
</div></body></html>""", status_code=404)
    return FileResponse(str(target))


# ── Client database ──────────────────────────────────────────────────────────

@app.get("/api/clients")
async def list_clients(request: Request):
    require_auth(request)
    return {"clients": _load_clients()}

def _load_customize(slug: str) -> dict:
    """Load output/{slug}/customize.json defensively; {} on any problem."""
    path = OUTPUT_DIR / slug / "customize.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _project_checklist(client: dict) -> dict:
    """Compute the 8-item client-readiness checklist for one client.

    Inspects the filesystem + customize.json. Any missing file or unreadable
    JSON => that check is False; never raises.
    """
    slug = client.get("slug", "")
    site_dir = OUTPUT_DIR / slug
    cz = _load_customize(slug)

    def _truthy(v):
        return bool(v)

    try:
        built = (site_dir / "index.html").exists()
    except Exception:
        built = False
    try:
        pdf = (site_dir / "ai_opportunity_report.pdf").exists()
    except Exception:
        pdf = False

    reviews = cz.get("reviews")
    real_reviews = isinstance(reviews, list) and len(reviews) >= 1
    service_images = cz.get("service_images")
    real_photos = _truthy(cz.get("hero_image")) or _truthy(service_images)

    return {
        "built":        bool(built),
        "deployed":     _truthy(client.get("live_url")),
        "pdf":          bool(pdf),
        "custom_theme": cz.get("theme") is not None,
        "real_reviews": bool(real_reviews),
        "real_photos":  bool(real_photos),
        "details":      _truthy(cz.get("facts")) or _truthy(cz.get("voice")),
        "share_link":   _truthy(client.get("portal_url")),
    }


@app.get("/api/projects")
async def list_projects(request: Request):
    require_auth(request)
    clients = _load_clients()
    projects = []
    for client in clients:
        checklist = _project_checklist(client)
        trues = sum(1 for v in checklist.values() if v)
        ready_pct = round(100 * trues / 8)
        proj = dict(client)
        proj["checklist"] = checklist
        proj["ready_pct"] = ready_pct
        proj["is_ready"]  = ready_pct == 100
        projects.append(proj)
    projects.sort(key=lambda p: p.get("created_at") or "", reverse=True)
    return {"projects": projects}


class ClientPatch(BaseModel):
    status: str | None = None
    notes: str | None = None
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    # Follow-up engine
    portal_sent_at: str | None = None        # ISO datetime — set when portal link is shared
    last_contact_at: str | None = None       # ISO datetime — set by "Mark contacted"
    followup_snooze_until: str | None = None  # ISO date — hide from follow-ups until then
    # Payments
    payment_link: str | None = None          # e.g. a Stripe Payment Link

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

@app.delete("/api/clients/{slug}")
async def delete_client(slug: str, request: Request, purge: bool = Query(default=True)):
    """Remove a client from the registry.

    By default also deletes the generated site (output/{slug}) and any
    scraped research (research/{slug}) so the client is gone cleanly. Pass
    ?purge=false to keep the files on disk and only drop the registry row.
    """
    require_auth(request)
    clients = _load_clients()
    client = next((c for c in clients if c.get("slug") == slug), None)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    clients = [c for c in clients if c.get("slug") != slug]
    _save_clients(clients)
    removed_files = False
    if purge:
        for base in (OUTPUT_DIR, RESEARCH_DIR):
            target = base / slug
            try:
                if target.exists() and target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                    removed_files = True
            except Exception:
                pass
    return {"removed": slug, "name": client.get("name", ""), "files_deleted": removed_files}

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


# ── Leads (live form submissions via Netlify) ───────────────────────────────
#
# Contact forms on the deployed sites use Netlify Forms, so submissions are
# captured reliably even when this admin server is offline. We read them back
# through the Netlify API using the existing NETLIFY_AUTH_TOKEN and surface them
# here, mapped to the client whose site they came from.

_LEADS_CACHE = {"ts": 0.0, "data": None}


def _netlify_token() -> str:
    t = os.getenv("NETLIFY_AUTH_TOKEN", "").strip()
    return "" if (not t or t.startswith("your_")) else t


def _site_id_index() -> dict:
    """Map Netlify site_id -> client record, read from each client's
    output/{slug}/deployment.json (written by Phase 5)."""
    idx = {}
    for c in _load_clients():
        dep = OUTPUT_DIR / c.get("slug", "") / "deployment.json"
        if dep.exists():
            try:
                d = json.loads(dep.read_text(encoding="utf-8", errors="replace"))
                if d.get("site_id"):
                    idx[d["site_id"]] = c
            except Exception:
                pass
    return idx


def _normalize_lead(submission: dict, site_index: dict) -> dict:
    fields = submission.get("data") or {}
    client = site_index.get(submission.get("site_id")) or {}
    first  = (fields.get("first_name") or "").strip()
    last   = (fields.get("last_name") or "").strip()
    name   = (f"{first} {last}".strip() or fields.get("name") or "").strip()
    return {
        "id":          submission.get("id"),
        "client_name": client.get("name") or submission.get("title")
                       or submission.get("name") or "Unknown site",
        "client_slug": client.get("slug"),
        "site_url":    submission.get("site_url"),
        "name":        name or "(no name)",
        "email":       fields.get("email", ""),
        "phone":       fields.get("phone", ""),
        "service":     fields.get("service", ""),
        "message":     fields.get("message", ""),
        "created_at":  submission.get("created_at"),
    }


@app.get("/api/submissions")
def list_submissions(request: Request):
    require_auth(request)
    token = _netlify_token()
    if not token:
        return {"leads": [], "configured": False, "count": 0,
                "note": "Add NETLIFY_AUTH_TOKEN to .env to pull live form submissions."}

    now = time.time()
    if _LEADS_CACHE["data"] is not None and now - _LEADS_CACHE["ts"] < 60:
        return _LEADS_CACHE["data"]

    import requests
    try:
        r = requests.get(
            "https://api.netlify.com/api/v1/submissions",
            headers={"Authorization": f"Bearer {token}"},
            params={"per_page": 200}, timeout=20,
        )
    except Exception as exc:
        return {"leads": [], "configured": True, "count": 0, "error": str(exc)}

    if r.status_code != 200:
        return {"leads": [], "configured": True, "count": 0,
                "error": f"Netlify API returned {r.status_code}"}

    site_index = _site_id_index()
    leads = [_normalize_lead(s, site_index) for s in r.json()]
    leads.sort(key=lambda l: l.get("created_at") or "", reverse=True)
    data = {"leads": leads, "configured": True, "count": len(leads)}
    _LEADS_CACHE.update(ts=now, data=data)
    return data


# ── Uptime / health monitoring ──────────────────────────────────────────────

_MONITOR_CACHE = {"ts": 0.0, "data": None}


def _check_site(client: dict) -> dict:
    import requests
    url = client.get("live_url")
    res = {"slug": client.get("slug"), "name": client.get("name"),
           "live_url": url, "status": "unknown", "http_status": None,
           "response_ms": None}
    if not url:
        res["status"] = "not_deployed"
        return res
    try:
        t0 = time.time()
        r = requests.get(url, timeout=12, allow_redirects=True)
        res["response_ms"] = int((time.time() - t0) * 1000)
        res["http_status"] = r.status_code
        res["status"] = "up" if r.status_code < 400 else "down"
    except Exception as exc:
        res["status"] = "down"
        res["error"] = str(exc)[:140]
    return res


@app.get("/api/monitor")
def monitor_sites(request: Request, refresh: bool = Query(default=False)):
    require_auth(request)
    now = time.time()
    if (not refresh and _MONITOR_CACHE["data"] is not None
            and now - _MONITOR_CACHE["ts"] < 120):
        return _MONITOR_CACHE["data"]

    clients  = _load_clients()
    deployed = [c for c in clients if c.get("live_url")]
    results  = []
    if deployed:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(_check_site, deployed))
    results.sort(key=lambda r: (r["status"] != "down", r.get("name") or ""))

    up   = sum(1 for r in results if r["status"] == "up")
    down = sum(1 for r in results if r["status"] == "down")
    data = {
        "sites": results,
        "summary": {"total": len(results), "up": up, "down": down,
                    "not_deployed": len(clients) - len(deployed)},
        "checked_at": datetime.now().isoformat(),
    }
    _MONITOR_CACHE.update(ts=now, data=data)
    return data


# ── Billing / subscriptions ─────────────────────────────────────────────────

class BillingPatch(BaseModel):
    plan: str | None = None             # e.g. "Tier 1 — Entry"
    monthly_fee: float | None = None
    billing_status: str | None = None   # active | paused | free
    next_due: str | None = None         # ISO date (YYYY-MM-DD)
    billing_notes: str | None = None
    payment_link: str | None = None     # Stripe Payment Link the client pays through


def _add_month(d):
    """Return the same day-of-month one month later, clamped to month length."""
    m, y = d.month + 1, d.year
    if m > 12:
        m, y = 1, y + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


@app.get("/api/billing")
async def get_billing(request: Request):
    require_auth(request)
    clients = _load_clients()
    today   = datetime.now().date().isoformat()
    counts  = {"active": 0, "paused": 0, "free": 0, "unset": 0}
    mrr, overdue = 0.0, 0
    rows = []
    for c in clients:
        status = c.get("billing_status") or "unset"
        fee    = float(c.get("monthly_fee") or 0)
        nd     = c.get("next_due")
        is_overdue = bool(status == "active" and nd and nd < today)
        if status == "active":
            mrr += fee
        if is_overdue:
            overdue += 1
        counts[status if status in counts else "unset"] += 1
        rows.append({
            "slug": c.get("slug"), "name": c.get("name"),
            "live_url": c.get("live_url"), "status_label": c.get("status"),
            "plan": c.get("plan", ""), "monthly_fee": fee,
            "billing_status": status, "next_due": nd,
            "billing_notes": c.get("billing_notes", ""),
            "payment_link": c.get("payment_link", ""),
            "last_paid": c.get("last_paid"), "is_overdue": is_overdue,
        })
    # Overdue first, then by name
    rows.sort(key=lambda r: (not r["is_overdue"], (r["name"] or "").lower()))
    return {"clients": rows, "mrr": round(mrr, 2), "counts": counts,
            "overdue_count": overdue, "active_count": counts["active"]}


@app.put("/api/clients/{slug}/billing")
async def update_billing(slug: str, data: BillingPatch, request: Request):
    require_auth(request)
    clients = _load_clients()
    client = next((c for c in clients if c["slug"] == slug), None)
    if not client:
        raise HTTPException(status_code=404)
    for k, v in data.model_dump(exclude_none=True).items():
        client[k] = v
    _save_clients(clients)
    return client


@app.post("/api/clients/{slug}/billing/mark-paid")
async def mark_paid(slug: str, request: Request):
    require_auth(request)
    clients = _load_clients()
    client = next((c for c in clients if c["slug"] == slug), None)
    if not client:
        raise HTTPException(status_code=404)
    from datetime import date
    base = date.today()
    nd = client.get("next_due")
    if nd:
        try:
            cur = date.fromisoformat(nd)
            if cur > base:
                base = cur
        except Exception:
            pass
    client["next_due"]       = _add_month(base).isoformat()
    client["billing_status"] = "active"
    client["last_paid"]      = date.today().isoformat()
    _save_clients(clients)
    return client


# ── Site editor ───────────────────────────────────────────────────────────────

@app.get("/api/output/{slug}/site")
async def get_site_html(slug: str, request: Request):
    require_auth(request)
    slug = _safe_slug(slug)
    path = OUTPUT_DIR / slug / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Site not built yet")
    return {"html": path.read_text(encoding="utf-8", errors="replace")}

@app.put("/api/output/{slug}/site")
async def save_site_html(slug: str, request: Request):
    require_auth(request)
    slug = _safe_slug(slug)
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
    slug = _safe_slug(slug)
    path = _customize_path(slug)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


_CUSTOMIZE_INTERNAL_KEYS = ("custom_html", "_gp_extra_photos")


@app.put("/api/customize/{slug}")
async def save_customize(slug: str, request: Request):
    require_auth(request)
    slug = _safe_slug(slug)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")
    site_dir = OUTPUT_DIR / slug
    site_dir.mkdir(parents=True, exist_ok=True)
    # Preserve internal flags the customize form doesn't round-trip —
    # dropping custom_html here would let "Rebuild all" overwrite an
    # uploaded/hand-designed site.
    existing = _load_customize(slug)
    for key in _CUSTOMIZE_INTERNAL_KEYS:
        if key in existing and key not in body:
            body[key] = existing[key]
    _customize_path(slug).write_text(
        json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "slug": slug}


@app.post("/api/customize/{slug}/parse-reviews")
async def parse_reviews_endpoint(slug: str, request: Request):
    require_auth(request)
    body = await request.json()
    raw = body.get("raw", "") if isinstance(body, dict) else ""
    return {"reviews": _parse_reviews(raw)}


@app.post("/api/import-site")
async def import_site(data: ImportSiteRequest, request: Request):
    """Import an existing business website by URL and rebuild it — better.

    Scrapes the prospect's current site to derive their name, contact details,
    category and real photos, then runs Phase 2 (full profile) + Phase 3 (build)
    as a background job. The new build reuses the prospect's own images so it
    looks like *their* business, not a stock template. Registers a client record
    so it shows up in the Clients / Customize tabs immediately.
    """
    require_auth(request)
    from scrape import extract_business_from_url, build_profile

    if not data.url or not data.url.strip():
        raise HTTPException(status_code=400, detail="A website URL is required.")

    business = extract_business_from_url(data.url.strip())
    name = business.get("name") or "Imported Site"
    slug = _slug(name)
    business["slug"] = slug

    job_id = _new_job(f"Import & rebuild: {name}")

    def _go():
        results = {"derived": {
            "name":     name,
            "slug":     slug,
            "phone":    business.get("phone", ""),
            "city":     business.get("city", ""),
            "category": business.get("category", ""),
            "url":      business.get("existing_website"),
        }}
        if business.get("_fetch_error"):
            log.warning(f"[import] Limited data — could not fully fetch site: "
                        f"{business['_fetch_error']}")
        profile_dir = str(RESEARCH_DIR / slug)
        site_dir    = str(OUTPUT_DIR / slug)
        if 2 in data.phases:
            log.info(f"[import] [Phase 2] Scraping {name} "
                     f"({business.get('existing_website')})…")
            profile_dir = str(build_profile(business, str(RESEARCH_DIR)))
            results["profile_dir"] = profile_dir
        if 3 in data.phases:
            from build import build_website
            log.info(f"[import] [Phase 3] Rebuilding {name} — premium version…")
            site_dir = str(build_website(profile_dir, str(OUTPUT_DIR)))
            results["site_dir"] = site_dir
        if 4 in data.phases:
            from audit import run_audit
            log.info(f"[import] [Phase 4] Generating audit PDF for {name}…")
            results["pdf_path"] = str(run_audit(profile_dir, str(OUTPUT_DIR)))
        if 5 in data.phases:
            from deploy import deploy_site
            log.info(f"[import] [Phase 5] Deploying {name}…")
            results["deployment"] = deploy_site(site_dir, business)

        deployment = results.get("deployment") or {}
        live_url   = deployment.get("live_url")
        portal_url = deployment.get("portal_url") or (
            f"{live_url}/portal.html" if live_url else f"/portal/{slug}")
        _upsert_client({
            "slug":          slug,
            "name":          name,
            "address":       business.get("address", ""),
            "phone":         business.get("phone", ""),
            "category":      business.get("category", ""),
            "status":        "prospect",
            "source":        "imported",
            "imported_from": business.get("existing_website"),
            "created_at":    datetime.now().isoformat(),
            "has_site":      bool(results.get("site_dir")),
            "has_pdf":       bool(results.get("pdf_path")),
            "live_url":      live_url,
            "portal_url":    portal_url,
        })
        log.info(f"[import] Done — '{name}' ready. Open the Customize tab to "
                 "tweak theme, reviews and images, then deploy.")
        return results

    _run(job_id, _go)
    return {"job_id": job_id, "name": name, "slug": slug,
            "derived": {"phone": business.get("phone", ""),
                        "city": business.get("city", ""),
                        "category": business.get("category", "")}}


class ZipUploadError(Exception):
    """Raised with a user-facing message when an uploaded zip is unusable."""


def _is_symlink_zipinfo(zinfo) -> bool:
    """True if a zip entry is a symlink (we never extract these)."""
    return ((zinfo.external_attr >> 16) & 0o170000) == 0o120000


def _safe_extract_zip(raw: bytes, dest: Path) -> list[str]:
    """Validate and extract a site zip into dest, defending against zip-slip,
    symlinks, zip bombs and disallowed file types.

    Returns the list of extracted relative paths (POSIX style). Raises
    ZipUploadError with a specific message for every rejectable condition.
    """
    import zipfile

    if not zipfile.is_zipfile(io.BytesIO(raw)):
        raise ZipUploadError("That file isn't a valid .zip archive.")

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise ZipUploadError("The .zip archive is corrupt or unreadable.")

    with zf:
        if zf.testzip() is not None:
            raise ZipUploadError("The .zip archive is corrupt (failed CRC check).")

        total_uncompressed = sum(i.file_size for i in zf.infolist())
        if total_uncompressed > MAX_UPLOAD_BYTES:
            raise ZipUploadError(
                f"Uncompressed contents exceed the {MAX_UPLOAD_MB} MB limit "
                "(possible zip bomb).")

        dest_root = dest.resolve()
        extracted: list[str] = []
        for info in zf.infolist():
            name = info.filename
            # Skip directory entries.
            if name.endswith("/"):
                continue
            parts = Path(name).parts

            # Zip-slip guard FIRST (before any skip), so a traversal entry can
            # never be quietly ignored: reject absolute paths, '..' segments,
            # and anything whose resolved path escapes dest_root.
            if os.path.isabs(name) or ".." in parts:
                raise ZipUploadError(
                    f"Refusing to extract '{name}' — it escapes the target "
                    "directory (zip-slip).")
            target = (dest_root / name).resolve()
            if target != dest_root and dest_root not in target.parents:
                raise ZipUploadError(
                    f"Refusing to extract '{name}' — it escapes the target "
                    "directory (zip-slip).")

            # Skip macOS / dotfile cruft (genuine hidden files, not '..'/'.').
            if any(p == "__MACOSX" for p in parts) or \
                    any(p.startswith(".") and p not in (".", "..") for p in parts):
                continue
            if _is_symlink_zipinfo(info):
                continue  # never extract symlinks

            ext = target.suffix.lower().lstrip(".")
            if ext not in ALLOWED_UPLOAD_EXTS:
                raise ZipUploadError(
                    f"Disallowed file type in zip: '{name}'. Allowed: "
                    "html, css, js, json, images and fonts only.")

            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            extracted.append(target.relative_to(dest_root).as_posix())

    if not extracted:
        raise ZipUploadError("The zip had no usable files in it.")
    return extracted


def _detect_entry_point(rel_paths: list[str], base_dir: Path | None = None) -> str:
    """Pick the site's entry HTML from extracted relative paths.

    Preference: a root-level index.html > any index.html (shallowest) > the
    single top-level .html > the largest top-level .html (needs base_dir to
    stat sizes). Raises ZipUploadError if there's no HTML at all; returns None
    only when the choice is ambiguous and no base_dir was given to break the tie.
    """
    htmls = [p for p in rel_paths if p.lower().endswith((".html", ".htm"))]
    if not htmls:
        raise ZipUploadError(
            "No HTML file found in the zip — a site needs at least one .html "
            "page (ideally index.html).")

    # 1) root index.html
    for p in htmls:
        if p.lower() == "index.html":
            return p
    # 2) any index.html, shallowest first
    indexes = sorted((p for p in htmls if Path(p).name.lower() == "index.html"),
                     key=lambda p: p.count("/"))
    if indexes:
        return indexes[0]
    # 3) top-level html files
    top = [p for p in htmls if "/" not in p]
    if len(top) == 1:
        return top[0]
    if top and base_dir is not None:
        # Multiple top-level pages, no index.html: the largest is almost always
        # the real home page (component fragments are smaller).
        return max(top, key=lambda p: (base_dir / p).stat().st_size
                   if (base_dir / p).exists() else 0)
    if base_dir is not None:
        # No top-level html but nested ones exist — take the largest overall.
        return max(htmls, key=lambda p: (base_dir / p).stat().st_size
                   if (base_dir / p).exists() else 0)
    return None  # ambiguous and no disk access to break the tie


@app.post("/api/upload-site")
async def upload_site(request: Request,
                      file: UploadFile = File(...),
                      name: str = Form("")):
    """Ingest a hand-built site uploaded as a .zip and register it as a client
    preview site — same storage, preview URL and tabs as generated sites.

    The zip is validated (real zip, size limit, type allowlist, zip-slip /
    symlink / zip-bomb guards), extracted into output/{slug}/ preserving its
    folder structure, its images bundled locally, and the client flagged
    custom_html so rebuilds never overwrite it.
    """
    require_auth(request)
    import zipfile  # noqa: F401  (kept for symmetry; helpers import their own)

    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip file.")

    # Read with a hard cap so an oversized upload can't exhaust memory.
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file was empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than the {MAX_UPLOAD_MB} MB limit.")

    name = (name or "").strip() or Path(filename).stem
    slug = _slug(name)
    if not slug:
        raise HTTPException(status_code=400,
                            detail="Could not derive a name for this site.")

    site_dir = OUTPUT_DIR / slug
    # Duplicate guard: refuse to silently clobber an existing site.
    if site_dir.exists() and (site_dir / "index.html").exists() and \
            request.query_params.get("overwrite") != "true":
        raise HTTPException(
            status_code=409,
            detail=f"A site named '{slug}' already exists. Re-upload with "
                   "overwrite enabled to replace it.")

    # Extract into a temp dir first; only swap into place on full success.
    tmp_dir = OUTPUT_DIR / f".upload-{slug}-{secrets.token_hex(4)}"
    try:
        tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            rel_paths = await asyncio.to_thread(_safe_extract_zip, raw, tmp_dir)
        except ZipUploadError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        entry = _detect_entry_point(rel_paths, base_dir=tmp_dir)
        if entry is None:
            raise HTTPException(
                status_code=400,
                detail="Multiple top-level HTML files and no index.html — "
                       "rename your main page to index.html and re-upload.")

        # Promote the extracted tree into output/{slug}/, replacing any prior.
        if site_dir.exists():
            shutil.rmtree(site_dir)
        shutil.move(str(tmp_dir), str(site_dir))

        # Ensure the preview's default file (index.html) resolves to the entry.
        if entry.lower() != "index.html" and not (site_dir / "index.html").exists():
            try:
                shutil.copyfile(site_dir / entry, site_dir / "index.html")
            except Exception as exc:
                log.warning(f"[upload] could not alias entry to index.html ({exc})")

        # Bundle any remote images locally so the preview is self-contained.
        # Off the event loop: downloads images over the network.
        try:
            from build import _localize_images
            await asyncio.to_thread(_localize_images, site_dir)
        except Exception as exc:
            log.warning(f"[upload] image localization skipped ({exc})")

        # Flag custom so Phase 3 / "Rebuild all" preserve this uploaded site.
        cz_path = _customize_path(slug)
        cz = {}
        if cz_path.exists():
            try:
                cz = json.loads(cz_path.read_text(encoding="utf-8", errors="replace"))
                if not isinstance(cz, dict):
                    cz = {}
            except Exception:
                cz = {}
        cz["custom_html"] = True
        cz_path.write_text(json.dumps(cz, indent=2, ensure_ascii=False),
                           encoding="utf-8")

        _upsert_client({
            "slug":       slug,
            "name":       name,
            "status":     "prospect",
            "source":     "uploaded",
            "has_site":   True,
            "created_at": datetime.now().isoformat(),
        })

        log.info(f"[upload] '{name}' ingested ({len(rel_paths)} files, "
                 f"entry={entry}) -> {site_dir}")
        return {
            "ok": True, "slug": slug, "name": name,
            "files": len(rel_paths), "entry": entry,
            "preview_url": f"/preview/{slug}/index.html",
        }
    finally:
        # Always clean up the temp dir (it's gone after a successful move).
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/custom-site")
async def custom_site(request: Request):
    """Take a finished site the operator hand-built (e.g. in Claude Design) and
    bring it into the tool as a client's live site.

    Writes the pasted HTML as output/{slug}/index.html, bundles any remote
    images locally so it's self-contained, flags the client so rebuilds never
    clobber it, registers/updates the client record, and (optionally) deploys
    it live to Netlify in the background.
    """
    require_auth(request)
    body = await request.json()
    html = (body.get("html") or "").strip()
    name = (body.get("name") or "").strip()
    slug = _slug((body.get("slug") or "").strip() or name)
    do_deploy = bool(body.get("deploy"))

    if not html:
        raise HTTPException(status_code=400, detail="Paste the site's HTML first.")
    if "<" not in html or ">" not in html:
        raise HTTPException(status_code=400,
                            detail="That doesn't look like HTML. Paste the full page source.")
    if not slug:
        raise HTTPException(status_code=400,
                            detail="A business name is required to file this site under a client.")

    # Pull a friendly name from an existing client record if one wasn't typed.
    if not name:
        existing = next((c for c in _load_clients() if c.get("slug") == slug), None)
        name = (existing or {}).get("name") or slug.replace("-", " ").title()

    site_dir = OUTPUT_DIR / slug
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(html, encoding="utf-8")

    # Bundle remote images locally (real photo if reachable, placeholder if not).
    # Runs in a worker thread: it downloads images over the network and would
    # otherwise freeze every dashboard request until it finishes.
    try:
        from build import _localize_images
        await asyncio.to_thread(_localize_images, site_dir)
    except Exception as exc:
        log.warning(f"[custom-site] image localization skipped ({exc})")

    # Flag the client so Phase 3 / "Rebuild all" preserve this hand-built site.
    cz_path = _customize_path(slug)
    cz = {}
    if cz_path.exists():
        try:
            cz = json.loads(cz_path.read_text(encoding="utf-8", errors="replace"))
            if not isinstance(cz, dict):
                cz = {}
        except Exception:
            cz = {}
    cz["custom_html"] = True
    cz_path.write_text(json.dumps(cz, indent=2, ensure_ascii=False), encoding="utf-8")

    _upsert_client({
        "slug":       slug,
        "name":       name,
        "status":     "prospect",
        "source":     "custom",
        "has_site":   True,
        "created_at": datetime.now().isoformat(),
    })

    result = {"ok": True, "slug": slug, "name": name,
              "preview_url": f"/preview/{slug}/index.html"}

    if do_deploy:
        readiness = deploy_readiness(slug)
        if not readiness["ready"] and not body.get("force"):
            # Site saved fine — but don't publish placeholder content to a
            # real client. The dashboard shows the issues and can re-send
            # with force=true after an explicit "deploy anyway".
            result["blocked"] = True
            result["readiness"] = readiness
            return result
        from deploy import deploy_site
        business = {"name": name, "slug": slug}
        job_id = _new_job(f"Deploy custom site: {name}")

        def _go():
            log.info(f"[custom-site] Deploying hand-built site for {name}…")
            deployment = deploy_site(str(site_dir), business)
            live_url = deployment.get("live_url")
            if live_url:
                _upsert_client({"slug": slug, "name": name,
                                "live_url": live_url,
                                "portal_url": deployment.get("portal_url")})
                log.info(f"[custom-site] Live at {live_url}")
            else:
                log.warning("[custom-site] Deploy did not return a live URL — "
                            "check NETLIFY_AUTH_TOKEN.")
            return {"deployment": deployment}

        _run(job_id, _go)
        result["job_id"] = job_id

    return result


@app.post("/api/customize/{slug}/rebuild")
async def rebuild_customize(slug: str, request: Request):
    require_auth(request)
    slug = _safe_slug(slug)
    profile_dir = RESEARCH_DIR / slug
    if not (profile_dir / "profile.json").exists():
        raise HTTPException(
            status_code=400,
            detail=f"No research profile found for '{slug}'. Run Phase 2 first.")
    from build import build_website
    # Full rebuild does AI calls + image downloads — never block the event loop.
    site_dir = await asyncio.to_thread(build_website, str(profile_dir), str(OUTPUT_DIR))
    return {"ok": True, "site_dir": str(site_dir),
            "preview_url": f"/preview/{slug}/index.html"}


@app.post("/api/rebuild-all")
async def rebuild_all(request: Request):
    """Rebuild every client site that has a Phase-2 research profile, as a
    background job so progress streams to the dashboard. Pulls in the latest
    template, themes, and locally-bundled images for all existing clients."""
    require_auth(request)
    from build import build_website

    clients = _load_clients()
    buildable = [c for c in clients
                 if (RESEARCH_DIR / c["slug"] / "profile.json").exists()]
    skipped = [c["slug"] for c in clients if c not in buildable]

    job_id = _new_job(f"Rebuild all sites ({len(buildable)} clients)")

    def _go():
        log.info(f"[rebuild-all] {len(buildable)} client(s) to rebuild; "
                 f"{len(skipped)} skipped (no Phase-2 profile)")
        done, failed = 0, 0
        for i, c in enumerate(buildable, 1):
            slug = c["slug"]
            log.info(f"[rebuild-all] [{i}/{len(buildable)}] {c.get('name', slug)}")
            try:
                build_website(str(RESEARCH_DIR / slug), str(OUTPUT_DIR))
                done += 1
            except Exception as exc:
                failed += 1
                log.error(f"[rebuild-all] {slug} failed: {exc}")
        log.info(f"[rebuild-all] Done - {done} rebuilt, {failed} failed, {len(skipped)} skipped")
        return {"rebuilt": done, "failed": failed, "skipped": skipped}

    _run(job_id, _go)
    return {"job_id": job_id, "buildable": len(buildable), "skipped": len(skipped)}


# ── Pre-deploy readiness check ───────────────────────────────────────────────
#
# Blocks embarrassing deploys: a site full of "Representative reviews —
# replace with your own" placeholder content going live on a client's real
# domain is the fastest way to lose the deal.

# Specific phrases only — a bare "placeholder" would false-positive on
# legitimate <input placeholder="..."> attributes in every generated form.
_PLACEHOLDER_MARKERS = [
    "representative reviews",
    "replace with your own",
    "replace with real",
    "lorem ipsum",
    "your business name",
]


def deploy_readiness(slug: str) -> dict:
    """Checklist for whether output/{slug} is fit to publish."""
    site_dir = OUTPUT_DIR / slug
    cz = _load_customize(slug)
    client = next((c for c in _load_clients() if c.get("slug") == slug), {})

    html = ""
    index = site_dir / "index.html"
    if index.exists():
        try:
            html = index.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            html = ""

    found_markers = [m for m in _PLACEHOLDER_MARKERS if m in html]

    img_dir = site_dir / "assets" / "img"
    real_photo_files = []
    if img_dir.exists():
        # Placeholder art is generated as .svg; real photos land as jpg/png/webp.
        real_photo_files = [p for p in img_dir.iterdir()
                            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".avif")]
    has_real_photos = bool(cz.get("hero_image") or cz.get("service_images")
                           or real_photo_files)
    # Hand-built/uploaded sites bring their own imagery — don't flag them.
    if cz.get("custom_html"):
        has_real_photos = True

    has_reviews = bool(cz.get("reviews")) or (
        html and "representative reviews" not in html and "review" in html)
    has_phone = bool(client.get("phone")) or ("tel:" in html)

    checks = [
        {"key": "built", "label": "Site is built",
         "ok": index.exists(),
         "hint": "Run Phase 3, or upload/paste a site in Customize."},
        {"key": "no_placeholders", "label": "No placeholder text",
         "ok": not found_markers,
         "hint": ("Found: " + ", ".join(f'"{m}"' for m in found_markers))
                 if found_markers else ""},
        {"key": "real_reviews", "label": "Real customer reviews",
         "ok": has_reviews,
         "hint": "Paste their Google reviews in Customize → Reviews."},
        {"key": "real_photos", "label": "Real photos (not placeholders)",
         "ok": has_real_photos,
         "hint": "Add a hero image / service photos in Customize."},
        {"key": "phone", "label": "Phone number present",
         "ok": has_phone,
         "hint": "Set the business phone so the call buttons work."},
    ]
    ready = all(c["ok"] for c in checks)
    return {"slug": slug, "ready": ready, "checks": checks,
            "issues": [c for c in checks if not c["ok"]]}


@app.get("/api/deploy-check/{slug}")
async def deploy_check(slug: str, request: Request):
    require_auth(request)
    slug = _safe_slug(slug)
    return deploy_readiness(slug)


# ── Follow-up engine ─────────────────────────────────────────────────────────
#
# Surfaces prospects that have gone quiet: you shared their portal (or created
# them) N days ago and nothing has moved. Each row comes with a ready-to-send
# email draft so the follow-up takes one click, not ten minutes.

FOLLOWUP_AFTER_DAYS = int(os.getenv("FOLLOWUP_AFTER_DAYS", "3"))


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _followup_email(client: dict) -> dict:
    name = client.get("name") or client.get("slug", "")
    first_line = f"Hi — just checking in about the new website we built for {name}."
    portal = client.get("live_url") or client.get("portal_url") or ""
    pay = client.get("payment_link") or ""
    body_lines = [
        first_line,
        "",
        "You can see it live here (works great on your phone too):",
        portal or "[paste their portal link]",
        "",
        "Quick recap of the offer:",
        "  • $0 setup — the site is already built",
        "  • $99/month covers hosting, updates and maintenance",
        "  • No contract, cancel anytime",
    ]
    if pay:
        body_lines += ["", "Ready to go? You can start here:", pay]
    body_lines += ["", "Happy to make any tweaks you'd like — just reply to this email.", ""]
    return {
        "subject": f"Your new website — quick question ({name})",
        "body": "\n".join(body_lines),
    }


@app.get("/api/followups")
async def list_followups(request: Request):
    require_auth(request)
    now = datetime.now()
    due, upcoming = [], []
    for c in _load_clients():
        if c.get("status") != "prospect":
            continue  # clients are already won; closed are lost
        snooze = _parse_iso(c.get("followup_snooze_until"))
        if snooze and snooze > now:
            continue
        ref = max(filter(None, [
            _parse_iso(c.get("last_contact_at")),
            _parse_iso(c.get("portal_sent_at")),
            _parse_iso(c.get("created_at")),
        ]), default=None)
        if ref is None:
            continue
        days = (now - ref).days
        row = {
            "slug": c.get("slug"), "name": c.get("name"),
            "days_since_contact": days,
            "portal_sent_at": c.get("portal_sent_at"),
            "last_contact_at": c.get("last_contact_at"),
            "live_url": c.get("live_url"),
            "portal_url": c.get("portal_url"),
            "payment_link": c.get("payment_link"),
            "email": _followup_email(c),
        }
        (due if days >= FOLLOWUP_AFTER_DAYS else upcoming).append(row)
    due.sort(key=lambda r: -r["days_since_contact"])
    return {"due": due, "upcoming_count": len(upcoming),
            "after_days": FOLLOWUP_AFTER_DAYS}


@app.post("/api/clients/{slug}/mark-contacted")
async def mark_contacted(slug: str, request: Request):
    require_auth(request)
    slug = _safe_slug(slug)
    with _CLIENTS_LOCK:
        clients = _load_clients()
        client = next((c for c in clients if c.get("slug") == slug), None)
        if not client:
            raise HTTPException(status_code=404)
        client["last_contact_at"] = datetime.now().isoformat()
        _save_clients(clients)
    return client


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
    _safe_slug(slug)
    portal = WEB_DIR / "portal.html"
    if not portal.exists():
        raise HTTPException(status_code=404, detail="Portal page not found")
    return HTMLResponse(portal.read_text(encoding="utf-8"))


@app.get("/api/portal/{slug}")
async def portal_info(slug: str):
    slug = _safe_slug(slug)
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
    slug = _safe_slug(slug)
    path = OUTPUT_DIR / slug / "ai_opportunity_report.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(str(path), media_type="application/pdf",
                        filename=f"{slug}-opportunity-report.pdf")


if __name__ == "__main__":
    setup_logging()
    port = int(os.getenv("PORT", 5000))
    pw = os.getenv("ADMIN_PASSWORD", "changeme")
    log.info(f"""
==============================================================
   PACIFIC WEB BUILDER  —  Admin Server
==============================================================
   Open in browser:   http://localhost:{port}
   Login password:    {pw}
   (set ADMIN_PASSWORD in .env to change it)

   To share a public link, open a SECOND terminal and run:
   cloudflared tunnel --url http://localhost:{port} --protocol http2
==============================================================
""")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True,
                reload_dirs=[str(Path(__file__).parent)])
