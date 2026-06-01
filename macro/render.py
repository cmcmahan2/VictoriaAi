"""
macro/render.py — render a macro-scan snapshot as a Gmail-safe HTML radar.

WHY TABLE/CSS BARS (not SVG): Gmail (and most email clients) strip <svg>, <script>,
<style> blocks, and external/much-inline CSS for security. What DOES render reliably
is table layout with inline styles and colored <td> width bars. So the charts here are
hand-built from nested tables + background colors — they show up in an actual inbox,
not just a browser. (The browser-only report can use richer SVG; this module targets
the email body.)

Input: a snapshot dict (see macro/history.py). Optional `history` list (prior
snapshots, oldest→newest) enables a "Since last" delta line.

CLI:
  python macro/render.py --date 2026-06-01            # render that day's snapshot
  python macro/render.py --date 2026-06-01 --out path.html
"""
from __future__ import annotations

import argparse
import html
import os

import history as H  # sibling module (run from inside macro/ or with macro on path)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "macro-reports")

POS, NEG, INK, SUB, LINE, BG, CARD = (
    "#15803d", "#b91c1c", "#0f172a", "#64748b", "#e2e8f0", "#f1f5f9", "#ffffff",
)


def _esc(x) -> str:
    return html.escape(str(x))


def _sign_color(v: float) -> str:
    return POS if v >= 0 else NEG


def _bar(value: float, max_abs: float, w_px: int = 180) -> str:
    """A single-direction colored bar (width ∝ |value|), inline-styled for email."""
    frac = 0.0 if max_abs <= 0 else min(1.0, abs(value) / max_abs)
    width = max(2, int(frac * w_px))
    color = _sign_color(value)
    track = (f'<table role="presentation" cellpadding="0" cellspacing="0" '
             f'style="width:{w_px}px;background:{LINE};border-radius:3px;"><tr>'
             f'<td style="width:{width}px;background:{color};height:12px;'
             f'border-radius:3px;font-size:0;line-height:0;">&nbsp;</td>'
             f'<td style="font-size:0;line-height:0;">&nbsp;</td></tr></table>')
    return track


def _tiles(levels: dict, vix) -> str:
    order = ["S&P 500", "Nasdaq 100", "Dow", "Russell 2000 (IWM)", "Gold",
             "WTI Crude", "Copper", "Silver", "US Dollar Index", "EUR/USD",
             "Bitcoin", "Ethereum"]
    cells = []
    if vix is not None:
        cells.append(("VIX", vix, None))
    for name in order:
        lv = levels.get(name)
        if isinstance(lv, dict) and lv.get("close") is not None:
            cells.append((name, lv["close"], lv.get("chg_pct")))
    out = []
    for i, (name, val, chg) in enumerate(cells):
        if i % 3 == 0:
            out.append("<tr>")
        chg_html = ""
        if chg is not None:
            chg_html = (f'<div style="font-size:12px;color:{_sign_color(chg)};">'
                        f'{chg:+.2f}%</div>')
        valfmt = f"{val:,.2f}" if val < 1000 else f"{val:,.0f}"
        out.append(
            f'<td style="padding:8px;border:1px solid {LINE};border-radius:6px;'
            f'vertical-align:top;width:33%;">'
            f'<div style="font-size:11px;color:{SUB};">{_esc(name)}</div>'
            f'<div style="font-size:17px;font-weight:700;color:{INK};">{valfmt}</div>'
            f'{chg_html}</td>')
        if i % 3 == 2:
            out.append("</tr>")
    if len(cells) % 3 != 0:
        out.append("</tr>")
    return ('<table role="presentation" cellpadding="0" cellspacing="6" '
            f'style="width:100%;border-collapse:separate;">{"".join(out)}</table>')


def _sector_bars(perf: dict) -> str:
    if not perf:
        return ""
    items = sorted(perf.items(), key=lambda kv: kv[1], reverse=True)
    max_abs = max((abs(v) for _, v in items), default=1.0)
    rows = []
    for name, v in items:
        rows.append(
            f'<tr><td style="font-size:12px;color:{INK};padding:3px 8px 3px 0;'
            f'white-space:nowrap;">{_esc(name)}</td>'
            f'<td style="padding:3px 0;">{_bar(v, max_abs)}</td>'
            f'<td style="font-size:12px;color:{_sign_color(v)};padding:3px 0 3px 8px;">'
            f'{v:+.2f}%</td></tr>')
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="width:100%;">{"".join(rows)}</table>')


def _curve_row(curve: dict) -> str:
    if not curve:
        return ""
    tenors = [("3m", "m3"), ("2y", "y2"), ("5y", "y5"), ("10y", "y10"), ("30y", "y30")]
    cells = []
    for lbl, key in tenors:
        y = curve.get(key)
        if y is None:
            continue
        cells.append(
            f'<td style="text-align:center;padding:6px 10px;border:1px solid {LINE};'
            f'border-radius:6px;"><div style="font-size:11px;color:{SUB};">{lbl}</div>'
            f'<div style="font-size:15px;font-weight:700;color:{INK};">{y:.2f}%</div></td>')
    s = curve.get("s2s10")
    tag = ""
    if s is not None:
        tag = (f'<span style="font-size:12px;color:{_sign_color(s)};">'
               f'2s10s {s:+.2f} ({"normal" if s >= 0 else "INVERTED"})</span>')
    return (f'<table role="presentation" cellpadding="0" cellspacing="6"><tr>'
            f'{"".join(cells)}</tr></table><div style="margin-top:4px;">{tag}</div>')


def build_email_html(snap: dict, history: list | None = None) -> str:
    date = snap.get("date", "")
    regime = snap.get("regime", "")
    deltas = ""
    if history:
        prior = [s for s in history if s.get("date", "") < date]
        if prior:
            d = H.compute_deltas(snap, prior[-1])
            if d:
                deltas = (f'<div style="background:{BG};border-left:4px solid #2563eb;'
                          f'padding:8px 12px;border-radius:6px;font-size:13px;color:{INK};'
                          f'margin:12px 0;"><b>Since {prior[-1]["date"]}:</b> '
                          f'{_esc(", ".join(d))}</div>')

    def section(title, body):
        if not body:
            return ""
        return (f'<div style="font-size:13px;font-weight:700;color:{SUB};'
                f'text-transform:uppercase;letter-spacing:.04em;margin:18px 0 8px;">'
                f'{title}</div>{body}')

    return f"""<!doctype html><html><body style="margin:0;background:{BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};padding:20px 0;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="background:{CARD};border-radius:12px;padding:24px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">
  <tr><td>
    <div style="font-size:20px;font-weight:800;color:{INK};">Macro Radar</div>
    <div style="font-size:13px;color:{SUB};margin-bottom:6px;">{_esc(date)}</div>
    <div style="font-size:14px;color:{INK};background:{BG};border-left:4px solid #f59e0b;padding:10px 12px;border-radius:6px;">{_esc(regime)}</div>
    {deltas}
    {section("Cross-asset", _tiles(snap.get("levels", {}), snap.get("vix")))}
    {section("Sector moves (latest session)", _sector_bars(snap.get("sectors_perf", {})))}
    {section("Yield curve", _curve_row(snap.get("curve", {})))}
    <div style="margin-top:20px;font-size:11px;color:{SUB};font-style:italic;border-top:1px solid {LINE};padding-top:10px;">
      Research only — not investment advice. Public data; verify before acting. You bear all risk.
    </div>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a macro snapshot as Gmail-safe HTML.")
    ap.add_argument("--date", help="snapshot date YYYY-MM-DD (default: latest)")
    ap.add_argument("--out", help="output path (default: macro-reports/radar-<date>.html)")
    args = ap.parse_args()

    snaps = H.load_all()
    if not snaps:
        print("no snapshots in macro/history/ — run /macro-scan first."); return
    snap = next((s for s in snaps if s.get("date") == args.date), snaps[-1]) if args.date else snaps[-1]

    htmlout = build_email_html(snap, history=snaps)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out = args.out or os.path.join(REPORTS_DIR, f"radar-{snap['date']}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(htmlout)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
