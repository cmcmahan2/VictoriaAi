import { NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// A curated, liquid global-equity watchlist (Stooq symbols). Free, no key.
// Without an FMP key we reason over this watchlist + live quotes rather than the
// whole market — honest scope, stated in the UI.
const WATCH: Record<string, string> = {
  "spy.us": "S&P 500 (SPY)", "qqq.us": "Nasdaq 100 (QQQ)", "iwm.us": "Small caps (IWM)",
  "efa.us": "Developed intl (EFA)", "eem.us": "Emerging mkts (EEM)",
  "xlk.us": "Tech (XLK)", "xlf.us": "Financials (XLF)", "xlv.us": "Healthcare (XLV)",
  "xle.us": "Energy (XLE)", "xly.us": "Cons. discretionary (XLY)", "xlp.us": "Staples (XLP)",
  "gld.us": "Gold (GLD)",
};

async function quote(sym: string): Promise<string | null> {
  try {
    const r = await fetch(`https://stooq.com/q/l/?s=${sym}&f=sd2t2ohlcvn&e=csv`, {
      headers: { "User-Agent": "Mozilla/5.0 (macro-engine)" },
    });
    const line = (await r.text()).trim();
    const p = line.split(",");
    if (p.length < 7 || p[1] === "N/D") return null;
    const open = parseFloat(p[3]), close = parseFloat(p[6]);
    const chg = open ? (((close - open) / open) * 100).toFixed(2) : "0";
    return `${WATCH[sym]}: ${close} (${chg}% today)`;
  } catch {
    return null;
  }
}

const HORIZON: Record<string, string> = {
  day: "the next 1-5 trading days (tactical: momentum, technicals, positioning, near-term catalysts)",
  month: "the next 1-3 months (swing: macro prints, earnings, sector rotation)",
  year: "the next ~12 months (position: valuation + business-cycle stage)",
};

export async function POST(req: Request) {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) {
    return NextResponse.json({ error: "ANTHROPIC_API_KEY not set in macro-engine/.env.local" });
  }
  let body: any = {};
  try { body = await req.json(); } catch {}
  const timeframe = (body.timeframe as string) || "month";
  const focus = ((body.focus as string) || "").slice(0, 120);

  const quotes = (await Promise.all(Object.keys(WATCH).map(quote))).filter(Boolean);
  const context = quotes.length ? quotes.join("\n") : "(live quotes unavailable this request)";

  const system =
    "You are a disciplined equity/macro researcher producing RESEARCH (not advice, no guarantees) " +
    "for the user's personal account. You rank CANDIDATES for a given horizon with honest reasoning " +
    "and explicit risks. You never claim a guaranteed 'best buy'. Cite the provided live quotes where " +
    "relevant; do not fabricate prices. Markets are largely efficient — frame ideas as probabilistic. " +
    "Return STRICT JSON only, no prose outside it, shape: " +
    '{"regime":"one-line backdrop","ideas":[{"name":"ticker/theme","conviction":"High|Medium|Low",' +
    '"thesis":"...","catalyst":"...","risks":"...","invalidation":"..."}],"note":"caveats/limits"}. ' +
    "Provide 3-5 ideas suited to the horizon.";

  const user =
    `Horizon: ${HORIZON[timeframe] || HORIZON.month}.\n` +
    (focus ? `Focus area: ${focus}.\n` : "") +
    `Live watchlist quotes (Stooq):\n${context}\n\n` +
    "Rank the best candidates for this horizon. Be specific and honest about risk. " +
    "Note in 'note' that this reasons over a curated watchlist + your knowledge, not a full-market screen.";

  try {
    const client = new Anthropic({ apiKey: key });
    const msg = await client.messages.create({
      model: "claude-sonnet-4-6",
      max_tokens: 3000,
      system,
      messages: [{ role: "user", content: user }],
    });
    const text = msg.content.map((b: any) => (b.type === "text" ? b.text : "")).join("");
    const parsed = parseModel(text);
    if (!parsed) return NextResponse.json({ error: "could not parse model output", note: text.slice(0, 300) });
    return NextResponse.json(parsed);
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || String(e) });
  }
}

// Tolerant JSON parse: handles a clean object, or a response truncated mid-array
// by trimming to the last complete idea object and closing the array/root.
function parseModel(text: string): any | null {
  const start = text.indexOf("{");
  if (start < 0) return null;
  const body = text.slice(start);
  try { return JSON.parse(body); } catch {}
  const lastObj = body.lastIndexOf("}");
  if (lastObj > 0) {
    const head = body.slice(0, lastObj + 1);  // drops any trailing ``` fence
    // "" handles a complete object that only failed due to trailing fence chars;
    // the rest close an array/root truncated mid-ideas.
    for (const suffix of ["", "]}", "}", "]}}", "}}"]) {
      try { return JSON.parse(head + suffix); } catch {}
    }
  }
  return null;
}
