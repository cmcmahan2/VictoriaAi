"""Slipstream — local betting tracker.

Run: ./run.sh  (or: uvicorn main:app --port 8787)
"""

import hashlib
import os
import threading
import webbrowser
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import sheets
import sizing

PORT = int(os.environ.get("SLIPSTREAM_PORT", "8787"))
STATIC = Path(__file__).parent / "static"

SETTLE_RESULTS = {"won": "WON", "lost": "LOST", "push": "PUSH", "void": "VOID"}
EDITABLE_SETTINGS = {
    "current_bankroll", "starting_bankroll", "kelly_fraction",
    "max_open_exposure_pct", "min_ev_floor_pct", "default_book", "currency",
}


def bet_id(player: str, market: str, line, event_time: str) -> str:
    key = "".join(str(x).strip().lower() for x in (player, market, line, event_time))
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def sync_from_sheet() -> dict:
    """Sheet is the source of truth: rebuild local bets + config from it."""
    if not sheets.enabled():
        return {"synced": False, "reason": sheets.error() or "sheets not configured"}
    bets = sheets.load_bets()
    db.replace_all_bets(bets)
    for k, v in sheets.load_config().items():
        db.set_config(k, v)
    return {"synced": True, "bets": len(bets)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    sheets.connect()
    try:
        sync_from_sheet()
    except Exception as e:
        print(f"[slipstream] sheet sync failed, using local cache: {e}")
    if not os.environ.get("SLIPSTREAM_NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    print(f"[slipstream] http://localhost:{PORT}  "
          f"(sheets: {'connected' if sheets.enabled() else 'LOCAL-ONLY — ' + str(sheets.error())})")
    yield


app = FastAPI(title="slipstream", lifespan=lifespan)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    return {
        "sheets_enabled": sheets.enabled(),
        "sheet_url": sheets.url(),
        "sheets_error": sheets.error(),
        "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "config": db.get_config(),
    }


@app.get("/api/settings")
def get_settings():
    return db.get_config()


class SettingsBody(BaseModel):
    settings: dict


@app.put("/api/settings")
def put_settings(body: SettingsBody):
    for k, v in body.settings.items():
        if k not in EDITABLE_SETTINGS:
            continue
        db.set_config(k, v)
        if sheets.enabled():
            sheets.set_config(k, v)
    return db.get_config()


@app.post("/api/parse")
async def parse(file: UploadFile):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(400, "ANTHROPIC_API_KEY is not set — export it and restart.")
    media_type = file.content_type or "image/png"
    if media_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        media_type = "image/png"
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty upload")

    import parser as screenshot_parser
    try:
        result = screenshot_parser.parse_screenshot(data, media_type)
    except Exception as e:
        raise HTTPException(502, f"Anthropic API error: {e}")

    cfg = db.get_config()
    rows = sizing.suggest_stakes(result["rows"], cfg)
    for row in rows:
        row["id"] = bet_id(row.get("player"), row.get("market"),
                           row.get("line"), row.get("event_time"))
        row["duplicate"] = db.bet_exists(row["id"])
    new_total = sum((r.get("stake") or 0) for r in rows if not r["duplicate"])
    return {
        "rows": rows,
        "exposure": sizing.exposure_check(new_total, db.open_exposure(), cfg),
        "raw": result["raw"],
    }


class CommitBody(BaseModel):
    rows: list[dict]
    book: str | None = None


@app.post("/api/commit")
def commit(body: CommitBody):
    """Append USED rows to the sheet + cache. Duplicates are hard-blocked."""
    cfg = db.get_config()
    book = body.book or cfg.get("default_book", "")
    results = []
    for r in body.rows:
        bid = bet_id(r.get("player"), r.get("market"), r.get("line"), r.get("event_time"))
        if db.bet_exists(bid):
            results.append({"id": bid, "player": r.get("player"),
                            "committed": False, "reason": "duplicate — already tracked"})
            continue
        try:
            stake = round(float(r.get("stake") or 0), 2)
            odds = float(r.get("odds_decimal") or r.get("odds") or 0)
            win_prob = float(r.get("win_prob") or 0)
            ev_pct = float(r.get("ev_pct")) if r.get("ev_pct") not in (None, "") else None
        except (TypeError, ValueError):
            results.append({"id": bid, "player": r.get("player"),
                            "committed": False, "reason": "stake/odds/win_prob not numeric"})
            continue
        if stake <= 0 or odds <= 1:
            results.append({"id": bid, "player": r.get("player"),
                            "committed": False, "reason": "stake must be > 0 and odds > 1"})
            continue

        bet = {
            "id": bid,
            "date_placed": datetime.now().isoformat(timespec="seconds"),
            "book": book,
            "player": (r.get("player") or "").strip(),
            "league": (r.get("league") or "").strip(),
            "match": (r.get("match") or "").strip(),
            "event_time": (r.get("event_time") or "").strip(),
            "market": (r.get("market") or "").strip(),
            "line": r.get("line"),
            "side": (r.get("side") or "").strip().upper(),
            "odds": odds,
            "win_prob": win_prob,
            "ev_pct": ev_pct,
            "stake": stake,
            "status": "OPEN",
            "payout": None, "pnl": None, "bankroll_after": None,
            "clv": "", "notes": (r.get("notes") or "").strip(), "settled_at": None,
        }
        if sheets.enabled():
            try:
                sheets.append_bet(bet)
            except Exception as e:
                results.append({"id": bid, "player": bet["player"],
                                "committed": False, "reason": f"sheet write failed: {e}"})
                continue
        db.insert_bet(bet)
        results.append({"id": bid, "player": bet["player"], "committed": True})

    cfg = db.get_config()
    return {"results": results,
            "exposure": sizing.exposure_check(0, db.open_exposure(), cfg)}


@app.get("/api/bets")
def get_bets(status: str | None = None):
    return db.list_bets(status)


class SettleBody(BaseModel):
    result: str


@app.post("/api/bets/{bid}/settle")
def settle(bid: str, body: SettleBody):
    result = body.result.strip().lower()
    if result not in SETTLE_RESULTS:
        raise HTTPException(400, f"result must be one of {sorted(SETTLE_RESULTS)}")
    bet = db.get_bet(bid)
    if bet is None:
        raise HTTPException(404, "bet not found")
    if bet["status"] != "OPEN":
        raise HTTPException(409, f"bet already settled ({bet['status']})")

    stake = float(bet["stake"] or 0)
    odds = float(bet["odds"] or 0)
    status_val = SETTLE_RESULTS[result]
    if status_val == "WON":
        payout = round(stake * odds, 2)
        pnl = round(payout - stake, 2)
    elif status_val == "LOST":
        payout, pnl = 0.0, round(-stake, 2)
    else:  # PUSH / VOID — stake returned, no P&L
        payout, pnl = stake, 0.0

    cfg = db.get_config()
    bankroll_after = round(float(cfg.get("current_bankroll", 0)) + pnl, 2)
    fields = {
        "status": status_val, "payout": payout, "pnl": pnl,
        "bankroll_after": bankroll_after,
        "settled_at": datetime.now().isoformat(timespec="seconds"),
    }
    if sheets.enabled():
        try:
            sheets.update_bet(bid, fields)
            sheets.set_config("current_bankroll", bankroll_after)
        except Exception as e:
            raise HTTPException(502, f"sheet write failed, nothing changed locally: {e}")
    db.update_bet(bid, fields)
    db.set_config("current_bankroll", bankroll_after)
    return {**db.get_bet(bid), "current_bankroll": bankroll_after}


@app.post("/api/sync")
def sync():
    if not sheets.enabled():
        sheets.connect()
    return sync_from_sheet()


@app.get("/api/dashboard")
def dashboard():
    cfg = db.get_config()
    bets = db.list_bets()
    settled = [b for b in bets if b["status"] in ("WON", "LOST", "PUSH", "VOID")]
    decided = [b for b in settled if b["status"] in ("WON", "LOST")]
    open_bets = [b for b in bets if b["status"] == "OPEN"]

    wins = sum(1 for b in decided if b["status"] == "WON")
    losses = len(decided) - wins
    pushes = sum(1 for b in settled if b["status"] in ("PUSH", "VOID"))
    total_pnl = round(sum(b["pnl"] or 0 for b in settled), 2)
    staked = sum(b["stake"] or 0 for b in decided)
    roi = round(100 * total_pnl / staked, 2) if staked else None
    avg_ev = (round(sum(b["ev_pct"] for b in bets if b["ev_pct"] is not None)
                    / max(1, sum(1 for b in bets if b["ev_pct"] is not None)), 2)
              if any(b["ev_pct"] is not None for b in bets) else None)
    expected_wr = (round(sum(b["win_prob"] or 0 for b in decided) / len(decided), 2)
                   if decided else None)
    actual_wr = round(100 * wins / len(decided), 2) if decided else None

    curve = [{"t": "start", "bankroll": float(cfg.get("starting_bankroll",
                                                      cfg.get("current_bankroll", 0)))}]
    for b in sorted(settled, key=lambda x: (x.get("settled_at") or "", x.get("seq") or 0)):
        if b["bankroll_after"] is not None:
            curve.append({"t": (b.get("settled_at") or b.get("date_placed") or "")[:16],
                          "bankroll": b["bankroll_after"],
                          "label": f"{b['player']} {b['side']} {b['line']} {b['market']}",
                          "status": b["status"]})

    leagues = {}
    for b in bets:
        lg = (b.get("league") or "?").upper()
        s = leagues.setdefault(lg, {"league": lg, "bets": 0, "wins": 0, "losses": 0,
                                    "pnl": 0.0, "staked": 0.0, "ev_sum": 0.0, "ev_n": 0,
                                    "wp_sum": 0.0, "wp_n": 0})
        s["bets"] += 1
        if b["ev_pct"] is not None:
            s["ev_sum"] += b["ev_pct"]; s["ev_n"] += 1
        if b["status"] == "WON":
            s["wins"] += 1
        if b["status"] == "LOST":
            s["losses"] += 1
        if b["status"] in ("WON", "LOST"):
            s["staked"] += b["stake"] or 0
            s["wp_sum"] += b["win_prob"] or 0; s["wp_n"] += 1
        if b["status"] in ("WON", "LOST", "PUSH", "VOID"):
            s["pnl"] += b["pnl"] or 0
    league_rows = []
    for s in leagues.values():
        n = s["wins"] + s["losses"]
        league_rows.append({
            "league": s["league"], "bets": s["bets"],
            "record": f"{s['wins']}-{s['losses']}",
            "pnl": round(s["pnl"], 2),
            "roi": round(100 * s["pnl"] / s["staked"], 2) if s["staked"] else None,
            "avg_ev": round(s["ev_sum"] / s["ev_n"], 2) if s["ev_n"] else None,
            "expected_wr": round(s["wp_sum"] / s["wp_n"], 2) if s["wp_n"] else None,
            "actual_wr": round(100 * s["wins"] / n, 2) if n else None,
        })
    league_rows.sort(key=lambda r: -r["bets"])

    return {
        "currency": cfg.get("currency", "CAD"),
        "bankroll": float(cfg.get("current_bankroll", 0)),
        "starting_bankroll": float(cfg.get("starting_bankroll",
                                           cfg.get("current_bankroll", 0))),
        "total_pnl": total_pnl,
        "roi_pct": roi,
        "record": {"wins": wins, "losses": losses, "pushes": pushes},
        "avg_ev_pct": avg_ev,
        "expected_win_rate": expected_wr,
        "actual_win_rate": actual_wr,
        "calibration_gap": (round(actual_wr - expected_wr, 2)
                            if actual_wr is not None and expected_wr is not None else None),
        "open_count": len(open_bets),
        "open_exposure": round(sum(b["stake"] or 0 for b in open_bets), 2),
        "equity_curve": curve,
        "leagues": league_rows,
        "settled_count": len(settled),
    }


app.mount("/static", StaticFiles(directory=STATIC), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", port=PORT)
