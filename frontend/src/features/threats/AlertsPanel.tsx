import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, LoadingPane, Select, Table, Td, Th, type Severity } from "@/components/ui";
import { api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { Alert, AlertStatus, Page } from "@/types/api";

import { AlertDrawer } from "./AlertDrawer";

export function AlertsPanel() {
  const [status, setStatus] = useState<AlertStatus | "">("open");
  const [selected, setSelected] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["alerts", status],
    queryFn: () =>
      api.get<Page<Alert>>("/threats/alerts", {
        params: { limit: 100, status: status || undefined },
      }),
    refetchInterval: 15_000,
  });

  if (isLoading) return <LoadingPane />;
  const alerts = data?.items ?? [];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value as AlertStatus | "")}
          className="h-8 w-40 py-0"
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="triaged">Triaged</option>
          <option value="closed">Closed</option>
        </Select>
        <span className="text-xs text-muted">{data?.total ?? 0} alerts</span>
      </div>

      {alerts.length === 0 ? (
        <p className="rounded-xl border border-dashed border-hairline/10 py-10 text-center text-sm text-muted">
          No alerts. Run a verification with a problem to generate one.
        </p>
      ) : (
        <Table
          head={
            <>
              <Th>Severity</Th>
              <Th>Title</Th>
              <Th>Rules</Th>
              <Th>Risk</Th>
              <Th>Status</Th>
              <Th>Opened</Th>
            </>
          }
        >
          {alerts.map((a) => (
            <tr
              key={a.id}
              onClick={() => setSelected(a.id)}
              className="cursor-pointer hover:bg-hairline/[0.04]"
            >
              <Td>
                <Badge severity={a.severity as Severity}>{a.severity}</Badge>
              </Td>
              <Td>{a.title}</Td>
              <Td>
                <span className="font-mono text-xs">{a.rule_codes.join(" ")}</span>
              </Td>
              <Td>{a.risk_score}</Td>
              <Td>
                <Badge severity={a.status === "open" ? "high" : "info"}>{a.status}</Badge>
              </Td>
              <Td>{formatRelative(a.created_at)}</Td>
            </tr>
          ))}
        </Table>
      )}

      <AlertDrawer alertId={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
