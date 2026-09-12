import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge, Card, LoadingPane, type Severity } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatRelative } from "@/lib/format";
import type { Incident, IncidentStatus, Page } from "@/types/api";

const COLUMNS: IncidentStatus[] = ["open", "investigating", "contained", "closed"];

export function IncidentsPanel() {
  const qc = useQueryClient();
  const { atLeast } = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: ["incidents"],
    queryFn: () => api.get<Page<Incident>>("/threats/incidents", { params: { limit: 200 } }),
    refetchInterval: 20_000,
  });

  const move = useMutation({
    mutationFn: (v: { id: string; status: IncidentStatus }) =>
      api.patch(`/threats/incidents/${v.id}`, { status: v.status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["incidents"] }),
  });

  if (isLoading) return <LoadingPane />;
  const incidents = data?.items ?? [];
  const byCol = (s: IncidentStatus) => incidents.filter((i) => i.status === s);

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {COLUMNS.map((col) => (
        <div key={col} className="rounded-xl border border-hairline/10 bg-hairline/[0.03] p-2">
          <div className="mb-2 flex items-center justify-between px-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted">
              {col}
            </span>
            <span className="text-xs text-muted">{byCol(col).length}</span>
          </div>
          <div className="space-y-2">
            {byCol(col).map((inc) => (
              <Card key={inc.id} className="p-2.5">
                <div className="flex items-center gap-2">
                  <Badge severity={inc.severity as Severity}>{inc.severity}</Badge>
                  <span className="text-[11px] text-muted">{inc.alert_count} alerts</span>
                </div>
                <p className="mt-1 text-xs font-medium text-fg">{inc.title}</p>
                <p className="text-[11px] text-muted">
                  cohesion {inc.cohesion_score} · {inc.method} · {formatRelative(inc.last_seen_at)}
                </p>
                {atLeast("analyst") && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {COLUMNS.filter((c) => c !== inc.status).map((c) => (
                      <button
                        key={c}
                        onClick={() => move.mutate({ id: inc.id, status: c })}
                        className="rounded bg-hairline/[0.06] px-1.5 py-0.5 text-[10px] text-muted hover:text-fg"
                      >
                        → {c}
                      </button>
                    ))}
                  </div>
                )}
              </Card>
            ))}
            {byCol(col).length === 0 && (
              <p className="px-1 py-4 text-center text-[11px] text-muted">—</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
