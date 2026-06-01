"use client";
import { useState } from "react";
import PlanTab from "./components/PlanTab";
import RadarTab from "./components/RadarTab";
import ResearcherTab from "./components/ResearcherTab";
import PlannerTab from "./components/PlannerTab";

const TABS = [
  { id: "plan", label: "Recommended Plan" },
  { id: "radar", label: "Macro Radar" },
  { id: "researcher", label: "Stock Researcher" },
  { id: "planner", label: "Trade Planner" },
] as const;

export default function Home() {
  const [tab, setTab] = useState<string>("plan");
  return (
    <div className="wrap">
      <h1>Macro Engine</h1>
      <div className="sub">Your personal macro research cockpit — long-term plan, daily radar, and a short-term stock researcher.</div>
      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={"tab" + (tab === t.id ? " active" : "")}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "plan" && <PlanTab />}
      {tab === "radar" && <RadarTab />}
      {tab === "researcher" && <ResearcherTab />}
      {tab === "planner" && <PlannerTab />}
      <div className="disc">
        Research only — not investment advice. Public data; verify before acting. You bear all risk.
      </div>
    </div>
  );
}
