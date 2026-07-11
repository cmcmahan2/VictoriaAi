"""Google Sheets persistence — the system of record.

Auth is a service-account JSON file (GOOGLE_SERVICE_ACCOUNT_FILE, default
./service_account.json). On first run the spreadsheet and its "bets" /
"config" tabs are created if missing. If credentials are absent the app runs
in local-only mode and every function here is a no-op guarded by enabled().
"""

import os
from pathlib import Path

import db

SHEET_ID_ENV = "SLIPSTREAM_SHEET_ID"
SHEET_NAME = os.environ.get("SLIPSTREAM_SHEET_NAME", "Slipstream")
SA_FILE = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_FILE", str(Path(__file__).parent / "service_account.json")
)
SHARE_EMAIL = os.environ.get("SLIPSTREAM_SHARE_EMAIL", "")

HEADER = db.BET_COLUMNS

_client = None
_spreadsheet = None
_error: str | None = None


def enabled() -> bool:
    return _spreadsheet is not None


def error() -> str | None:
    return _error


def url() -> str | None:
    return _spreadsheet.url if _spreadsheet else None


def connect() -> bool:
    """Connect, creating the spreadsheet and tabs if needed. Never raises."""
    global _client, _spreadsheet, _error
    if not Path(SA_FILE).exists():
        _error = f"service account file not found: {SA_FILE} (running local-only)"
        return False
    try:
        import gspread

        _client = gspread.service_account(filename=SA_FILE)
        sheet_id = os.environ.get(SHEET_ID_ENV, "").strip()
        if sheet_id:
            _spreadsheet = _client.open_by_key(sheet_id)
        else:
            try:
                _spreadsheet = _client.open(SHEET_NAME)
            except gspread.SpreadsheetNotFound:
                _spreadsheet = _client.create(SHEET_NAME)
                if SHARE_EMAIL:
                    _spreadsheet.share(SHARE_EMAIL, perm_type="user", role="writer")
        _ensure_tabs()
        _error = None
        return True
    except Exception as e:  # bad creds, no API access, network — degrade, don't crash
        _spreadsheet = None
        _error = f"{type(e).__name__}: {e}"
        return False


def _ensure_tabs():
    titles = [ws.title for ws in _spreadsheet.worksheets()]
    if "bets" not in titles:
        ws = _spreadsheet.add_worksheet("bets", rows=1000, cols=len(HEADER))
        ws.append_row(HEADER)
    else:
        ws = _spreadsheet.worksheet("bets")
        if ws.row_values(1) != HEADER:
            ws.update(range_name="A1", values=[HEADER])
    if "config" not in titles:
        cfg = _spreadsheet.add_worksheet("config", rows=50, cols=2)
        cfg.append_rows([["key", "value"]] + [[k, v] for k, v in db.DEFAULT_CONFIG.items()])
    # Drop the default empty Sheet1 on a freshly created spreadsheet
    if "Sheet1" in titles and len(titles) == 1:
        try:
            _spreadsheet.del_worksheet(_spreadsheet.worksheet("Sheet1"))
        except Exception:
            pass


def _bets_ws():
    return _spreadsheet.worksheet("bets")


def _config_ws():
    return _spreadsheet.worksheet("config")


def load_bets() -> list[dict]:
    records = _bets_ws().get_all_records(expected_headers=HEADER)
    out = []
    for r in records:
        if not str(r.get("id", "")).strip():
            continue
        bet = {c: r.get(c, "") for c in HEADER}
        for f in ("odds", "win_prob", "ev_pct", "stake", "payout", "pnl", "bankroll_after"):
            try:
                bet[f] = float(bet[f]) if str(bet[f]).strip() != "" else None
            except (TypeError, ValueError):
                bet[f] = None
        out.append(bet)
    return out


def append_bet(bet: dict) -> None:
    row = ["" if bet.get(c) is None else bet.get(c) for c in HEADER]
    _bets_ws().append_row(row, value_input_option="USER_ENTERED")


def update_bet(bet_id: str, fields: dict) -> None:
    ws = _bets_ws()
    cell = ws.find(bet_id, in_column=1)
    if cell is None:
        raise ValueError(f"bet {bet_id} not found in sheet")
    updates = []
    for k, v in fields.items():
        if k in HEADER:
            col = HEADER.index(k) + 1
            updates.append({
                "range": ws.cell(cell.row, col).address,
                "values": [["" if v is None else v]],
            })
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")


def load_config() -> dict:
    values = _config_ws().get_all_values()
    cfg = {}
    for row in values[1:]:
        if len(row) >= 2 and row[0].strip():
            cfg[row[0].strip()] = row[1]
    return cfg


def set_config(key: str, value) -> None:
    ws = _config_ws()
    cell = ws.find(key, in_column=1)
    if cell:
        ws.update_cell(cell.row, 2, str(value))
    else:
        ws.append_row([key, str(value)])
