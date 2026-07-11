# slipstream

Local betting tracker: drop a screenshot of a betting-model page (e.g. LCSLarry),
Claude vision parses it into rows, you verify/edit them in a bet-slip table, and
committed bets persist to a Google Sheet (the system of record) with a SQLite
local cache, a settle workflow, and a P&L dashboard with a model-calibration check.

## Quick start

```bash
export ANTHROPIC_API_KEY=sk-ant-...
./run.sh          # creates venv, installs deps, opens http://localhost:8787
```

That's it for local-only mode (SQLite only). To make the Google Sheet the
source of truth, do the one-time service-account setup below.

## Google Sheets setup (one time, ~5 minutes)

The app authenticates as a **service account** — a robot Google identity with
its own email address. You create it once, download its JSON key, and share the
spreadsheet with it like you'd share with a person.

1. **Create a Google Cloud project** (or reuse one): https://console.cloud.google.com
   → project picker → *New project* → name it e.g. `slipstream`.
2. **Enable the APIs**: in that project, go to *APIs & Services → Library* and
   enable **Google Sheets API** and **Google Drive API** (Drive is needed to
   open/create spreadsheets by name).
3. **Create the service account**: *APIs & Services → Credentials → Create
   credentials → Service account*. Name it `slipstream`, skip the optional role
   steps, *Done*.
4. **Download the JSON key**: click the new service account → *Keys* tab →
   *Add key → Create new key → JSON*. Save the downloaded file as
   `service_account.json` in this directory (or point
   `GOOGLE_SERVICE_ACCOUNT_FILE` at it). **Never commit this file** — it's
   already in `.gitignore`.
5. **Give it a spreadsheet** — pick ONE of:
   - **Recommended:** create a Google Sheet yourself named `Slipstream`, click
     *Share*, and add the service account's email (it looks like
     `slipstream@your-project.iam.gserviceaccount.com`, shown in the JSON as
     `client_email`) as an **Editor**. Optionally set `SLIPSTREAM_SHEET_ID` to
     the ID from the sheet URL to skip name lookup.
   - **Auto-create:** set `SLIPSTREAM_SHARE_EMAIL=you@gmail.com` and the app
     will create the spreadsheet on first run and share it with you. (Without
     the share, the sheet lives in the service account's Drive and you can't
     see it in your own.)
6. Restart the app. The header pill should read **Sheets connected**, and the
   `bets` + `config` tabs are created automatically if missing.

### Environment variables

| Var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for screenshot parsing (claude-sonnet-4-6 vision) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `./service_account.json` | Service-account JSON key |
| `SLIPSTREAM_SHEET_ID` | — | Open a specific spreadsheet by ID |
| `SLIPSTREAM_SHEET_NAME` | `Slipstream` | Name used to open/create the spreadsheet |
| `SLIPSTREAM_SHARE_EMAIL` | — | If the app creates the sheet, share it with this email |
| `SLIPSTREAM_PORT` | `8787` | Local port |
| `SLIPSTREAM_NO_BROWSER` | — | Set to any value to suppress auto-opening the browser |

## How it works

- **Ingest** — drag/paste a screenshot → `POST /api/parse` sends it to
  `claude-sonnet-4-6` with a strict-JSON system prompt. Parsing is defensive:
  markdown fences stripped, truncated arrays closed at the last complete object,
  and rows that fail validation come back **flagged red and editable** — never
  silently dropped.
- **Verify** — every field is editable inline. Stakes are prefilled by the
  sizing engine. Nothing is saved until **USED** (per row) or **USE ALL CHECKED**.
- **Commit** — `id = sha1(player+market+line+event_time)` (normalized).
  Duplicates are **hard-blocked**, so re-uploading the same screenshot never
  double-enters. Rows append to the sheet's `bets` tab, then the local cache.
- **Settle** — W/L/Push/Void per open bet. Won: `payout = stake × odds`,
  `pnl = payout − stake`. Lost: `pnl = −stake`. Push/void: stake returned,
  `pnl = 0`. The running bankroll updates in the sheet's `config` tab and each
  bet records `bankroll_after`. (One column beyond your spec: `settled_at`, so
  the equity curve orders correctly after a restart.)
- **Dashboard** — bankroll equity curve, cumulative P&L, ROI (on decided
  stakes), W–L record, average EV% taken, and the **calibration check**:
  mean model win-probability on settled bets vs your actual win rate.
- **Source of truth** — on startup the app pulls the `bets` and `config` tabs
  and rebuilds SQLite from them; the local DB is only a cache. Delete
  `slipstream.db` any time; it regenerates from the sheet.

## Sizing engine

- `stake = kelly_fraction × ((odds−1)·p − (1−p)) / (odds−1) × bankroll`
- **Correlation rule:** rows sharing player + match are one position — the
  position stake is the *mean of the legs' individual Kelly stakes × 1.25*,
  split evenly across the legs.
- Rows below `min_ev_floor_pct` get stake 0 and an amber flag (still editable —
  override the stake manually if you want them anyway).
- If committing would push total open exposure past
  `max_open_exposure_pct × bankroll`, the UI warns (it does not block).
- Config lives in the sheet's `config` tab and the Settings page:
  `current_bankroll` (starts 115.95 CAD), `kelly_fraction` (0.25),
  `max_open_exposure_pct` (35), `min_ev_floor_pct` (8).
