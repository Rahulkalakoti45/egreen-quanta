import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { RequireRole } from "@/components/RequireAuth";
import { Badge, Button, Card, Input, LoadingPane, PageHeader, Table, Td, Th } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { getAccessToken } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AuditPage as AuditPageT, ChainVerification } from "@/types/api";

export function AuditPage() {
  return (
    <RequireRole atLeast="auditor">
      <PageHeader
        eyebrow="Tamper-evident"
        title="Audit Log"
        description="Append-only, SHA-256 hash-chained record of every state change. Any tampering with a historic row is detectable and located by sequence number."
      />
      <AuditView />
    </RequireRole>
  );
}

function AuditView() {
  const qc = useQueryClient();
  const [actionFilter, setActionFilter] = useState("");
  const [page, setPage] = useState(0);
  const limit = 100;

  const list = useQuery({
    queryKey: ["audit", actionFilter, page],
    queryFn: () =>
      api.get<AuditPageT>("/audit", {
        params: { limit, offset: page * limit, action: actionFilter || undefined },
      }),
  });

  const verify = useMutation<ChainVerification, ApiError>({
    mutationFn: () => api.get<ChainVerification>("/audit/verify"),
  });
  const anchor = useMutation({
    mutationFn: () => api.post("/audit/anchor"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["audit"] }),
  });

  function download() {
    const base = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
    fetch(`${base}/audit/export`, {
      headers: { Authorization: `Bearer ${getAccessToken() ?? ""}` },
      credentials: "include",
    })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "audit-export.json";
        a.click();
        URL.revokeObjectURL(url);
      });
  }

  if (list.isLoading) return <LoadingPane />;
  const data = list.data;
  const v = verify.data;

  return (
    <div className="space-y-3">
      <Card className="flex flex-wrap items-center gap-3">
        <Button size="sm" onClick={() => verify.mutate()} disabled={verify.isPending}>
          {verify.isPending ? "Verifying…" : "Verify chain integrity"}
        </Button>
        {v && (
          <Badge severity={v.ok ? "ok" : "critical"}>
            {v.ok
              ? `chain intact · ${v.checked} rows · head #${v.head_seq}`
              : `TAMPERED · first break at seq ${v.break_at}`}
          </Badge>
        )}
        <Button size="sm" variant="secondary" onClick={download}>
          Export (signed JSON)
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => anchor.mutate()}
          disabled={anchor.isPending}
        >
          Write anchor
        </Button>
        <div className="ml-auto flex items-center gap-2">
          <Input
            placeholder="filter action prefix…"
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPage(0);
            }}
            className="h-8 w-56 py-0"
          />
        </div>
      </Card>

      <Table
        head={
          <>
            <Th>Seq</Th>
            <Th>Time</Th>
            <Th>Actor</Th>
            <Th>Action</Th>
            <Th>Target</Th>
            <Th>Row hash</Th>
          </>
        }
      >
        {(data?.items ?? []).map((r) => (
          <tr
            key={r.seq}
            className={v && !v.ok && v.break_at != null && r.seq >= v.break_at ? "bg-critical/5" : ""}
          >
            <Td>{r.seq}</Td>
            <Td>{formatDateTime(r.ts)}</Td>
            <Td>
              <span className="text-xs">
                {r.actor_type}
                {r.actor_id ? ` · ${r.actor_id.slice(0, 8)}` : ""}
              </span>
            </Td>
            <Td>
              <span className="font-mono text-xs">{r.action}</span>
            </Td>
            <Td>
              <span className="text-xs text-muted">
                {r.target_type ?? "—"}
                {r.target_id ? `:${r.target_id}` : ""}
              </span>
            </Td>
            <Td>
              <span className="font-mono text-[10px] text-muted" title={r.row_hash}>
                {r.row_hash.slice(0, 12)}…
              </span>
            </Td>
          </tr>
        ))}
      </Table>

      <div className="flex items-center justify-between text-xs text-muted">
        <span>{data?.total ?? 0} rows</span>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            Prev
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={(page + 1) * limit >= (data?.total ?? 0)}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
