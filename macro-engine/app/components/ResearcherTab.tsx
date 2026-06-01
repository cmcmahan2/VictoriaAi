"use client";
import { useState } from "react";

type Idea = {
  name: string; conviction?: string; thesis?: string;
  catalyst?: string; risks?: string; invalidation?: string;
};
type Result = { regime?: string; ideas?: Idea[]; note?: string; error?: string };

const TF = [
  { id: "day", label: "Best of the Day (tactical)" },
  { id: "month", label: "Best of the Month (swing)" },
  { id: "year", label: "Best of the Year (position)" },
];

function pill(c?: string) {
  const k = (c || "").toLowerCase();
  if (k.includes("high")) return "hi";
  if (k.includes("low")) return "lo";
  return "me";
}

export default function ResearcherTab() {
  const [timeframe, setTimeframe] = useState("month");
  const [focus, setFocus] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<Result | null>(null);

  async function run() {
    setLoading(true); setRes(null);
    try {
      const r = await fetch("/api/researcher", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeframe, focus }),
      });
      setRes(await r.json());
    } catch (e) {
      setRes({ error: String(e) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="card regime">
        Short-term <b>researcher</b>, not a crystal ball. It ranks <b>candidates</b> for your
        horizon with a thesis and the risks — no tool can name a guaranteed &quot;best buy.&quot;
      </div>

      <div className="controls">
        <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
          {TF.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
        </select>
        <input
          placeholder="Focus (optional): e.g. global stocks, semis, energy, AAPL"
          value={focus}
          onChange={(e) => setFocus(e.target.value)}
          style={{ flex: 1, minWidth: 220 }}
        />
        <button className="go" onClick={run} disabled={loading}>
          {loading ? "Researching…" : "Research"}
        </button>
      </div>

      {loading && <div className="card spinner">Pulling live quotes and reasoning through candidates…</div>}

      {res?.error && (
        <div className="card">Researcher error: {res.error}
          <br /><span className="sub">Make sure ANTHROPIC_API_KEY is set in macro-engine/.env.local.</span>
        </div>
      )}

      {res?.regime && <div className="card"><b>Backdrop:</b> {res.regime}</div>}

      {res?.ideas?.map((it, i) => (
        <div className="idea" key={i}>
          <h3>{i + 1}. {it.name}{it.conviction && <span className={"pill " + pill(it.conviction)}>{it.conviction}</span>}</h3>
          {it.thesis && <div className="row"><b>Thesis: </b>{it.thesis}</div>}
          {it.catalyst && <div className="row"><b>Catalyst: </b>{it.catalyst}</div>}
          {it.risks && <div className="row"><b>Risks: </b>{it.risks}</div>}
          {it.invalidation && <div className="row inval"><b>Invalidated if: </b>{it.invalidation}</div>}
        </div>
      ))}

      {res?.note && <div className="card sub">{res.note}</div>}
    </div>
  );
}
