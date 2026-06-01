const CORE = [
  { slice: "Global stocks", pct: "50%", what: "Low-cost index — ~30% US, ~20% international", why: "US is expensive (Tech ~58 P/E); ex-US is cheaper → diversify, don't go US-only" },
  { slice: "Bonds", pct: "20%", what: "Intermediate US Treasuries", why: "10yr pays ~4.45% — real income + a cushion when stocks fall" },
  { slice: "Real assets", pct: "12%", what: "Gold + broad commodities + TIPS", why: "Record gold + firm oil + soft dollar = live inflation hedge. Phase in — don't chase gold" },
  { slice: "Cash / T-bills", pct: "8%", what: "Money-market / short T-bills", why: "~3.7% yield, dry powder, prudent given low-VIX complacency" },
];

export default function PlanTab() {
  return (
    <div>
      <div className="card regime">
        <b>Recommended Plan — v1.</b> Assumes a long-term growth investor, multi-decade
        horizon, moderate risk, money you won&apos;t need soon. The percentages shift with
        your real details — tell the assistant your age, capital, risk tolerance, and goal
        to tailor them.
      </div>

      <div className="card">
        <h2>Where your money lives (the core ~90%)</h2>
        <table>
          <thead>
            <tr><th>Slice</th><th>Target</th><th>What</th><th>Why (from the current read)</th></tr>
          </thead>
          <tbody>
            {CORE.map((r) => (
              <tr key={r.slice}>
                <td><b>{r.slice}</b></td>
                <td>{r.pct}</td>
                <td>{r.what}</td>
                <td style={{ color: "var(--sub)" }}>{r.why}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>How to lean (tilts from the macro read)</h2>
        <div className="row">• Favor the cheap sectors (<b>Healthcare, Financials ~26 P/E</b>) over the priciest (Consumer Discretionary ~90, Tech ~58).</div>
        <div className="row">• Hold a little <b>cheap downside protection</b> — VIX ~17.6 means insurance is on sale.</div>
        <div className="row">• <b>Don&apos;t chase</b> the leveraged-ETF / meme froth showing up in the data.</div>
      </div>

      <div className="card">
        <h2>Mechanics that matter more than picks</h2>
        <div className="row">Low-fee index funds · dollar-cost average monthly · rebalance once a year · stay invested.</div>
      </div>

      <div className="card">
        <h2>Optional tactical sleeve (≤10%, hands-on only)</h2>
        <div className="row">Curve steepener · long gold / short dollar · long energy vs short expensive consumer · long volatility. Higher risk, active management.</div>
      </div>
    </div>
  );
}
