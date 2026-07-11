"""Screenshot → structured bet rows via the Anthropic API (claude-sonnet-4-6 vision).

The model is instructed to return strict JSON only; parsing is defensive
anyway: markdown fences are stripped, the outermost JSON array is located, and
a truncated response is repaired by closing the array at the last complete
object. Rows that fail validation are returned flagged, never dropped.
"""

import json
import re

import anthropic

MODEL = "claude-sonnet-4-6"

FIELDS = [
    "player", "league", "match", "event_time", "market", "line", "side",
    "model_projection", "win_prob", "odds_decimal", "ev_pct", "suggested_units",
]

SYSTEM_PROMPT = """You extract betting-model rows from screenshots of pages like LCSLarry.

Return STRICT JSON only: a single JSON array, no markdown fences, no prose, no
keys other than those specified. One object per visible bet row, in top-to-bottom
order, with exactly these keys:

{
  "player": string,             // player name, e.g. "Nisha"
  "league": string,             // league/game tag, e.g. "DOTA", "VAL", "LOL", "CS"
  "match": string,              // matchup, e.g. "Team Spirit vs PARIVISION"
  "event_time": string,         // event date/time exactly as shown, e.g. "Jul 11, 2:00 PM"
  "market": string,             // market name, e.g. "Map 1 Deaths"
  "line": number,               // the book line, e.g. 3.5
  "side": string,               // "UNDER" or "OVER"
  "model_projection": number,   // the model's projected value
  "win_prob": number,           // win probability as a percentage, e.g. 61.4 (not 0.614)
  "odds_decimal": number,       // decimal odds, e.g. 1.87
  "ev_pct": number,             // expected value percentage, e.g. 12.3
  "suggested_units": number     // suggested units/size if shown, else null
}

Rules:
- Use null for any value that is not visible or not legible. Never invent values.
- If odds are shown in American format (e.g. -115, +120), convert to decimal
  (negative: 1 + 100/|a|; positive: 1 + a/100) and round to 3 decimals.
- If win probability is shown as a fraction (0.614), convert to percent (61.4).
- Ignore page chrome, ads, filters, and header rows — only actual bet rows.
- If there are no bet rows in the image, return []."""


def _repair_truncated(raw: str) -> str:
    """Close the array at the last complete object instead of crashing."""
    cut = raw.rfind("},")
    if cut == -1:
        cut = raw.rfind("}")
        if cut == -1:
            return "[]"
    return raw[: cut + 1] + "]"


def _extract_json_array(text: str) -> list:
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1:
        raise ValueError("no JSON array in model output")
    candidate = cleaned[start : end + 1] if end > start else cleaned[start:]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return json.loads(_repair_truncated(candidate))


def _num(value):
    if value is None or isinstance(value, (int, float)):
        return value
    s = str(value).strip().replace("%", "").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _validate_row(raw: dict) -> dict:
    row = {f: raw.get(f) for f in FIELDS}
    for f in ("line", "model_projection", "win_prob", "odds_decimal", "ev_pct", "suggested_units"):
        row[f] = _num(row[f])
    for f in ("player", "league", "match", "event_time", "market", "side"):
        row[f] = str(row[f]).strip() if row[f] is not None else ""
    row["side"] = row["side"].upper()
    # Normalize a fractional win_prob the model failed to convert
    if row["win_prob"] is not None and 0 < row["win_prob"] <= 1:
        row["win_prob"] = round(row["win_prob"] * 100, 2)

    problems = []
    if not row["player"]:
        problems.append("player missing")
    if not row["market"]:
        problems.append("market missing")
    if row["side"] not in ("UNDER", "OVER"):
        problems.append("side not UNDER/OVER")
    if row["odds_decimal"] is None or row["odds_decimal"] <= 1:
        problems.append("odds missing/invalid")
    if row["win_prob"] is None or not (0 < row["win_prob"] < 100):
        problems.append("win_prob missing/invalid")
    if row["line"] is None:
        problems.append("line missing")

    row["parse_ok"] = not problems
    row["problems"] = problems
    return row


def parse_screenshot(image_bytes: bytes, media_type: str) -> dict:
    """Returns {"rows": [...], "raw": str}. Raises on API failure only."""
    import base64

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.standard_b64encode(image_bytes).decode(),
                    },
                },
                {"type": "text", "text": "Extract all bet rows from this screenshot."},
            ],
        }],
    )

    text = "".join(b.text for b in response.content if b.type == "text")
    try:
        raw_rows = _extract_json_array(text)
        if not isinstance(raw_rows, list):
            raw_rows = [raw_rows]
    except (ValueError, json.JSONDecodeError) as e:
        # Surface the failure as one editable, red-flagged empty row — never drop.
        stub = _validate_row({})
        stub["problems"].insert(0, f"model output was not parseable JSON ({e})")
        return {"rows": [stub], "raw": text}

    rows = [_validate_row(r if isinstance(r, dict) else {}) for r in raw_rows]
    return {"rows": rows, "raw": text}
