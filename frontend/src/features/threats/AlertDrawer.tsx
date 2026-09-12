import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Button, Drawer, type Severity } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime, formatRelative } from "@/lib/format";
import type { AlertDetail, AlertStatus } from "@/types/api";

import { VerificationResultCard } from "../signatures/VerificationResultCard";

const NEXT_STATUS: Record<AlertStatus, AlertStatus[]> = {
  open: ["triaged", "closed"],
  triaged: ["closed", "open"],
  closed: ["open"],
};

export function AlertDrawer({ alertId, onClose }: { alertId: string | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["alert", alertId],
    queryFn: () => api.get<AlertDetail>(`/threats/alerts/${alertId}`),
    enabled: !!alertId,
  });

  const patch = useMutation<unknown, ApiError, { status?: AlertStatus; note?: string }>({
    mutationFn: (body) => api.patch(`/threats/alerts/${alertId}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alert", alertId] });
      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["threat-stats"] });
      setNote("");
    },
  });

  return (
    <Drawer open={!!alertId} onClose={onClose} title="Alert detail" width="40rem">
      {isLoading || !data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <div className="space-y-4">
          <div>
            <div className="flex items-center gap-2">
              <Badge severity={data.severity as Severity}>{data.severity}</Badge>
              <Badge severity={data.status === "open" ? "high" : "info"}>{data.status}</Badge>
              <span className="text-xs text-muted">risk {data.risk_score}</span>
            </div>
            <h3 className="mt-1.5 text-sm font-semibold text-fg">{data.title}</h3>
            <p className="text-xs text-muted">
              opened {formatRelative(data.created_at)} · rules {data.rule_codes.join(", ")}
              {data.incident_id ? ` · incident ${data.incident_id.slice(0, 8)}` : ""}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {NEXT_STATUS[data.status].map((s) => (
              <Button
                key={s}
                size="sm"
                variant={s === "closed" ? "secondary" : "primary"}
                disabled={patch.isPending}
                onClick={() => patch.mutate({ status: s })}
              >
                Mark {s}
              </Button>
            ))}
          </div>

          <div>
            <textarea
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Add a triage note…"
              className="w-full rounded-lg border border-hairline/10 bg-hairline/[0.03] px-3 py-2 text-sm text-fg outline-none transition-all placeholder:text-faint focus:border-primary/50 focus:ring-4 focus:ring-primary/10"
            />
            <Button
              size="sm"
              variant="secondary"
              className="mt-1"
              disabled={!note || patch.isPending}
              onClick={() => patch.mutate({ note })}
            >
              Add note
            </Button>
          </div>

          {data.notes && (
            <pre className="whitespace-pre-wrap rounded-lg border border-hairline/10 bg-hairline/[0.04] p-2 text-xs text-muted">
              {data.notes}
            </pre>
          )}
          {patch.error && <p className="text-xs text-critical">{patch.error.message}</p>}

          <div className="border-t border-hairline/10 pt-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
              Verification event · {formatDateTime(data.event.created_at)}
              {data.event.anomaly_score != null && (
                <span className="ml-2 text-accent">
                  ML anomaly {data.event.anomaly_score.toFixed(2)}
                </span>
              )}
            </p>
            <VerificationResultCard result={data.event.result_json} />
          </div>
        </div>
      )}
    </Drawer>
  );
}
