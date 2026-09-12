import { useState } from "react";

import { PageHeader, TabBar } from "@/components/ui";

import { AlertsPanel } from "./AlertsPanel";
import { IncidentsPanel } from "./IncidentsPanel";
import { MlPanel } from "./MlPanel";
import { RulesPanel } from "./RulesPanel";

type Tab = "alerts" | "incidents" | "rules" | "ml";

const TABS = [
  ["alerts", "Alerts"],
  ["incidents", "Incidents"],
  ["rules", "Rules"],
  ["ml", "ML model"],
] as const;

export function ThreatsPage() {
  const [tab, setTab] = useState<Tab>("alerts");

  return (
    <>
      <PageHeader
        eyebrow="Threat detection"
        title="Threats & Incidents"
        description="Deterministic + history-aware detections over verification events, blended into a risk score and correlated into incidents."
      />
      <TabBar tabs={TABS} value={tab} onChange={setTab} />
      <div key={tab} className="animate-fade-up">
        {tab === "alerts" && <AlertsPanel />}
        {tab === "incidents" && <IncidentsPanel />}
        {tab === "rules" && <RulesPanel />}
        {tab === "ml" && <MlPanel />}
      </div>
    </>
  );
}
