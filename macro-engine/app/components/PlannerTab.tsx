"use client";
import { useState } from "react";

function num(s: string): number { const n = parseFloat(s); return isNaN(n) ? 0 : n; }

export default function PlannerTab() {
  const [dir, setDir] = useState<"long" | "short">("long");
  const [entry, setEntry] = useState("100");
  const [sl, setSl] = useState("95");
  const [tp, setTp] = useState("115");
  const [account, setAccount] = useState("10000");
  const [riskPct, setRiskPct] = useState("1");

  const e = num(entry), s = num(sl), t = num(tp), acct = num(account), rp = num(riskPct);
  const riskPerUnit = Math.abs(e - s);
  const rewardPerUnit = Math.abs(t - e);
  const dollarRisk = acct * (rp / 100);
  const units = riskPerUnit > 0 ? dollarRisk / riskPerUnit : 0;
  const notional = units * e;
  const dollarReward = units * rewardPerUnit;
  const rr = riskPerUnit > 0 ? rewardPerUnit / riskPerUnit : 0;
  const slPct = e > 0 ? (riskPerUnit / e) * 100 : 0;
  const tpPct = e > 0 ? (rewardPerUnit / e) * 100 : 0;

  // sanity warnings
  const warns: string[] = [];
  if (e <= 0) warns.push("Enter a positive entry price.");
  if (dir === "long" && s >= e) warns.push("For a LONG, the stop-loss should be BELOW entry.");
  if (dir === "long" && t <= e) warns.push("For a LONG, the take-profit should be ABOVE entry.");
  if (dir === "short" && s <= e) warns.push("For a SHORT, the stop-loss should be ABOVE entry.");
  if (dir === "short" && t >= e) warns.push("For a SHORT, the take-profit should be BELOW entry.");
  if (rr > 0 && rr < 1) warns.push(`Reward:risk is ${rr.toFixed(2)} (below 1) — you're risking more than the target pays.`);
  if (notional > acct) warns.push(`Notional ($${notional.toFixed(0)}) exceeds your account — this needs leverage/margin (extra risk).`);

  const Field = ({ label, val, set, suffix }: any) => (
    <div className="tile">
      <div className="k">{label}</div>
      <input value={val} onChange={(ev) => set(ev.target.value)} style={{ width: "100%", marginTop: 4 }} inputMode="decimal" />
      {suffix && <div className="k" style={{ marginTop: 2 }}>{suffix}</div>}
    </div>
  );

  return (
    <div>
      <div className="card regime">
        <b>Trade Planner.</b> Turns an idea into a sized trade with a take-profit (TP) and
        stop-loss (SL). It computes how many units to buy so a hit stop loses only your chosen
        risk %. It does <b>not</b> place orders — you execute with your broker. Research, not advice.
      </div>

      <div className="card">
        <h2>Inputs</h2>
        <div className="controls">
          <select value={dir} onChange={(ev) => setDir(ev.target.value as any)}>
            <option value="long">Long (betting it rises)</option>
            <option value="short">Short (betting it falls)</option>
          </select>
        </div>
        <div className="tiles">
          {Field({ label: "Entry price", val: entry, set: setEntry })}
          {Field({ label: "Take-profit (TP)", val: tp, set: setTp })}
          {Field({ label: "Stop-loss (SL)", val: sl, set: setSl })}
          {Field({ label: "Account size ($)", val: account, set: setAccount })}
          {Field({ label: "Risk per trade (%)", val: riskPct, set: setRiskPct, suffix: "% of account you'll lose if stopped" })}
        </div>
      </div>

      <div className="card">
        <h2>Trade ticket</h2>
        <div className="tiles">
          <div className="tile"><div className="k">Position size</div><div className="v">{units.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div><div className="k">units</div></div>
          <div className="tile"><div className="k">Notional</div><div className="v">${notional.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div></div>
          <div className="tile"><div className="k">Risk if stopped</div><div className="v neg">-${dollarRisk.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div><div className="k">{slPct.toFixed(1)}% move to SL</div></div>
          <div className="tile"><div className="k">Reward if TP hit</div><div className="v pos">+${dollarReward.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div><div className="k">{tpPct.toFixed(1)}% move to TP</div></div>
          <div className="tile"><div className="k">Reward : Risk</div><div className="v" style={{ color: rr >= 2 ? "var(--pos)" : rr >= 1 ? "var(--ink)" : "var(--neg)" }}>{rr.toFixed(2)} : 1</div></div>
        </div>
        {warns.length > 0 && (
          <div className="card since" style={{ borderLeftColor: "var(--neg)", marginTop: 14 }}>
            {warns.map((w, i) => <div key={i} className="inval">⚠ {w}</div>)}
          </div>
        )}
        <div className="row" style={{ marginTop: 12, fontSize: 13 }}>
          <b style={{ color: "var(--sub)" }}>Plain English: </b>
          Going <b>{dir}</b> at <b>{e}</b>, buy <b>{units.toLocaleString(undefined, { maximumFractionDigits: 2 })} units</b>.
          If it hits your stop at <b>{s}</b> you lose <b>${dollarRisk.toFixed(0)}</b> ({rp}% of the account).
          If it reaches your target at <b>{t}</b> you make <b>${dollarReward.toFixed(0)}</b> — a <b>{rr.toFixed(2)}:1</b> payoff.
        </div>
      </div>
    </div>
  );
}
