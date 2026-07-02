# BCBUISWEBBUILDERTOOL

Autonomous BC business web presence pipeline. Discovers weak-presence businesses
in British Columbia, scrapes intelligence profiles, generates production-ready
websites, produces AI opportunity audit PDFs, and deploys everything live to
Netlify automatically.

---

## Easiest start — one click

Inside the `bcbuiswebbuildertool` folder:

- **Windows:** double‑click **`start.bat`**
- **macOS / Linux / Git Bash:** run **`bash start.sh`**

It automatically creates a `.env` (default login password **`careful2026`**) if you don't have one, starts the server, and opens a public HTTPS tunnel on the stable HTTP/2 protocol. The server window prints your **login password** and local URL; the tunnel window prints your public `https://…trycloudflare.com` link.

To stop, just close the two windows it opened.

---

## Manual Start (run on your PC)

```bash
# 1. Clone the repo
git clone https://github.com/cmcmahan2/victoriaai.git
cd victoriaai/bcbuiswebbuildertool

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure environment (optional — login defaults to "changeme")
cp .env.example .env
# Open .env and set ADMIN_PASSWORD (and API keys when ready)

# 4. Start the admin server
python src/server.py    # prints your login password + a ready-to-copy tunnel command

# 5. Open in browser
# http://localhost:5000
```

> **Forgot your password?** The server window prints it on startup. With no `.env`, it's `changeme`.

Log in with your `ADMIN_PASSWORD`, type a business type + city in the sidebar, and click Search.

---

## Phases

| Phase | What it does |
|---|---|
| 1 — Discover | Find BC businesses with weak/no web presence, score + rank leads |
| 2 — Scrape | Build full intelligence profile (website, GMB, social, reviews, competitors) |
| 3 — Build | Generate production-ready website (static HTML or Next.js) |
| 4 — Audit | Produce AI Opportunity PDF report for the business owner |
| 5 — Deploy | Push site live to Netlify, capture preview URL |

---

## Environment Variables

Copy `.env.example` to `.env`:

| Variable | Description |
|---|---|
| `ADMIN_PASSWORD` | Password for the web dashboard (required) |
| `DEMO_MODE=true` | Use realistic fake data — no API keys needed to start |
| `GOOGLE_MAPS_API_KEY` | Tier 1 discovery (best quality) |
| `YELP_API_KEY` | Tier 2 discovery — free at yelp.com/developers |
| `ANTHROPIC_API_KEY` | AI content generation |
| `NETLIFY_AUTH_TOKEN` | Auto-deployment to Netlify |
| `MAX_UPLOAD_MB` | Max size of an uploaded site `.zip` (default `50`) |

**Start with `DEMO_MODE=true`** — you'll see 10 realistic fake BC leads immediately so you can test the full UI before adding API keys.

---

## CLI Usage (alternative to web UI)

```bash
# Full pipeline
python src/cli.py run --type plumber --city Victoria

# Discovery only
python src/cli.py discover --type electrician --city Kelowna

# Build from existing profile
python src/cli.py build --profile ./research/cedar-valley-plumbing/

# Audit PDF only
python src/cli.py audit --profile ./research/cedar-valley-plumbing/

# Redeploy
python src/cli.py deploy --site ./output/cedar-valley-plumbing/ --name "Cedar Valley Plumbing"
```

---

## Bring your own site (Customize tab)

Besides generating sites, you can bring in a site you built elsewhere (e.g. in
Claude Design) and have it served + deployed like any generated one. Three ways,
all in the **Customize** tab:

- **Paste a site from Claude Design** — paste full-page HTML; saved as the
  client's `index.html`.
- **Upload a site (.zip)** — drag-and-drop a `.zip` of HTML/CSS/JS/images.
- **Import an existing site** — paste a prospect's live URL to scrape + rebuild.

Uploaded/pasted sites are flagged `custom_html` in `output/{slug}/customize.json`
so **"Rebuild all" and Phase 3 never overwrite them**. Images referenced by the
page are bundled locally so the result is self-contained.

### `POST /api/upload-site`

Multipart form upload. Auth required (same `Bearer` token as the dashboard).

| Field | Type | Notes |
|---|---|---|
| `file` | file | The site `.zip` (required) |
| `name` | text | Business name (optional; defaults to the zip's file name) |
| `?overwrite=true` | query | Replace an existing site of the same slug |

The zip is validated and safely extracted into `output/{slug}/`:

- Rejects non-zips, corrupt zips, and uploads over `MAX_UPLOAD_MB` (default 50 MB).
- Guards against **zip-slip** (path traversal), **symlinks**, and **zip bombs**
  (total uncompressed size is also capped at `MAX_UPLOAD_MB`).
- Allowlists file types (html, css, js, json, common image + font types);
  rejects anything else (e.g. executables). Skips `__MACOSX/` and dotfile cruft.
- Entry point: prefers `index.html`, else a nested `index.html`, else the single
  / largest top-level `.html` (aliased to `index.html`). Errors if there's no HTML.

Returns `{ slug, name, files, entry, preview_url }`. Preview at
`/preview/{slug}/index.html`.

Run the uploader tests with:

```bash
python src/test_upload_zip.py
```

---

## Output Structure

```
output/
  leads.json                    <- Ranked leads from Phase 1
  {business-slug}/
    index.html                  <- Home page
    services.html
    about.html
    contact.html
    reviews.html
    css/style.css
    js/main.js
    images/
    sitemap.xml
    robots.txt
    ai_opportunity_report.pdf
    deployment.json             <- Live URL after Phase 5
    README.md

research/
  {business-slug}/
    profile.json
    screenshots/
    assets/
    competitors/
```
