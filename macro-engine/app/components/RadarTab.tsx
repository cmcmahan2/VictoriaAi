"use client";
import { useEffect, useState } from "react";

type Lvl = { close: number; chg_pct?: number };
type Snap = {
  date: string; regime?: string; vix?: number;
  levels?: Record<string, Lvl>;
  curve?: Record<string, number>;
  sectors_perf?: Record<string, number>;
};

const TILE_ORDER = ["S&P 500", "Nasdaq 100", "Dow", "Russell 2000 (IWM)", "Gold",
  "WTI Crude", "Copper", "Silver", "US Dollar Index", "EUR/USD", "Bitcoin", "Ethereum"];

export default function RadarTab() {
  const [snap, setSnap] = useState<Snap | null>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    fetch("/api/radar")
      .then((r) => r.json())
      .then((d) => (d.error ? setErr(d.error) : setSnap(d.snapshot)))
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="card">Couldn&apos;t load the latest snapshot: {err}<br /><span className="sub">Run <code>/macro-scan</code> to create one in macro/history/.</span></div>;
  if (!snap) return <div className="card spinner">Loading latest radar…</div>;

  const perf = snap.sectors_perf || {};
  const maxAbs = Math.max(1, ...Object.values(perf).map((v) => Math.abs(v)));
  const c = snap.curve || {};

  return (
    <div>
      {snap.regime && <div className="card regime"><b>Regime:</b> {snap.regime}</div>}

      <div className="card">
        <h2>Cross-asset ({snap.date})</h2>
        <div className="tiles">
          {snap.vix != null && (
            <div className="tile"><div className="k">VIX</div><div className="v">{snap.vix}</div></div>
          )}
          {TILE_ORDER.map((name) => {
            const lv = snap.levels?.[name];
            if (!lv) return null;
            return (
              <div className="tile" key={name}>
                <div className="k">{name}</div>
                <div className="v">{lv.close.toLocaleString()}</div>
                {lv.chg_pct != null && (
                  <div className={lv.chg_pct >= 0 ? "pos" : "neg"} style={{ fontSize: 12 }}>
                    {lv.chg_pct >= 0 ? "+" : ""}{lv.chg_pct}%
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {Object.keys(perf).length > 0 && (
        <div className="card">
          <h2>Sector moves (latest session)</h2>
          <table><tbody>
            {Object.entries(perf).sort((a, b) => b[1] - a[1]).map(([name, v]) => (
              <tr key={name}>
                <td style={{ whiteSpace: "nowrap" }}>{name}</td>
                <td>
                  <span className="barTrack">
                    <span className="barFill" style={{
                      width: Math.max(2, Math.round((Math.abs(v) / maxAbs) * 180)),
                      background: v >= 0 ? "var(--pos)" : "var(--neg)",
                      display: "block",
                    }} />
                  </span>
                </td>
                <td className={v >= 0 ? "pos" : "neg"}>{v >= 0 ? "+" : ""}{v.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody></table>
        </div>
      )}

      {Object.keys(c).length > 0 && (
        <div className="card">
          <h2>Yield curve</h2>
          <div className="tiles">
            {[["3m", "m3"], ["2y", "y2"], ["5y", "y5"], ["10y", "y10"], ["30y", "y30"]].map(([lbl, key]) =>
              c[key] != null ? (
                <div className="tile" key={key}><div className="k">{lbl}</div><div className="v">{c[key]}%</div></div>
              ) : null
            )}
          </div>
          {c.s2s10 != null && (
            <div style={{ marginTop: 8 }} className={c.s2s10 >= 0 ? "pos" : "neg"}>
              2s10s {c.s2s10 >= 0 ? "+" : ""}{c.s2s10} ({c.s2s10 >= 0 ? "normal" : "INVERTED"})
            </div>
          )}
        </div>
      )}
    </div>
  );
}
