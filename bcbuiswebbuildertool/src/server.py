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

VALID_TOKENS: set[str] = set()
JOBS: dict[str, dict]  = {}


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


def _slug(name):
    return name.lower().replace(" ", "-").replace("/", "-")


@app.get("/", response_class=HTMLResponse)
async def serve_login():
    return HTMLResponse((WEB_DIR / "login.html").read_text())

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    return HTMLResponse((WEB_DIR / "dashboard.html").read_text())

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
    business = {"name": data.name, "address": data.address, "slug": slug}
    def _go():
        results     = {}
        profile_dir = str(RESEARCH_DIR / _slug(data.name))
        if 2 in data.phases:
            from scrape import build_profile
            print(f"[Phase 2] Scraping profile for {data.name}...")
            results["profile_dir"] = str(build_profile(business, str(RESEARCH_DIR)))
        if 3 in data.phases:
            from build import build_website
            print(f"[Phase 3] Building website for {data.name}...")
            results["site_dir"] = str(build_website(profile_dir, str(OUTPUT_DIR)))
        if 4 in data.phases:
            from audit import run_audit
            print(f"[Phase 4] Generating audit PDF for {data.name}...")
            results["pdf_path"] = str(run_audit(profile_dir, str(OUTPUT_DIR)))
        if 5 in data.phases:
            from deploy import deploy_site
            print(f"[Phase 5] Deploying {data.name}...")
            results["deployment"] = deploy_site(str(OUTPUT_DIR / _slug(data.name)), business)
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
