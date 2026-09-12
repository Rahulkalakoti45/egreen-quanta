import { useState } from "react";

import { PageHeader, TabBar } from "@/components/ui";
import { RequireRole } from "@/components/RequireAuth";

import { ApiKeysPanel } from "./ApiKeysPanel";
import { UsersPanel } from "./UsersPanel";

type Tab = "users" | "api-keys";

const TABS = [
  ["users", "Users"],
  ["api-keys", "API keys"],
] as const;

export function AdminPage() {
  const [tab, setTab] = useState<Tab>("users");

  return (
    <RequireRole atLeast="admin">
      <PageHeader
        eyebrow="Administration"
        title="Users & access"
        description="Users and roles, and API keys for machine ingest."
      />
      <TabBar tabs={TABS} value={tab} onChange={setTab} />
      <div key={tab} className="animate-fade-up">
        {tab === "users" ? <UsersPanel /> : <ApiKeysPanel />}
      </div>
    </RequireRole>
  );
}
