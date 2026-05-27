# BCBUISWEBBUILDERTOOL

Autonomous BC business web presence pipeline. Discovers weak-presence businesses
in British Columbia, scrapes intelligence profiles, generates production-ready
websites, produces AI opportunity audit PDFs, and deploys everything live to
Netlify automatically.

---

## Quick Start (run on your PC)

```bash
# 1. Clone the repo
git clone https://github.com/cmcmahan2/victoriaai.git
cd victoriaai/bcbuiswebbuildertool

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Open .env and set ADMIN_PASSWORD (and API keys when ready)

# 4. Start the admin server
python src/server.py

# 5. Open in browser
# http://localhost:5000
```

Log in with your `ADMIN_PASSWORD`, type a business type + BC city in the sidebar, and click Search.

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
