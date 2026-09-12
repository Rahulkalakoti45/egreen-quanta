import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  Badge,
  Button,
  Dialog,
  Field,
  Input,
  LoadingPane,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ApiKey, ApiKeyCreated, ApiKeyScope, Page } from "@/types/api";

const SCOPES: ApiKeyScope[] = ["ingest:events", "ingest:signatures"];

export function ApiKeysPanel() {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [freshKey, setFreshKey] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.get<Page<ApiKey>>("/api-keys", { params: { limit: 100 } }),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api.delete(`/api-keys/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  if (isLoading) return <LoadingPane />;
  if (error) return <p className="text-sm text-critical">{(error as Error).message}</p>;

  const keys = data?.items ?? [];

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setCreating(true)}>
          + New API key
        </Button>
      </div>

      {freshKey && (
        <div className="rounded-lg border border-accent/40 bg-accent/10 p-3 text-xs">
          <p className="font-medium text-fg">Copy this key now — it is not shown again.</p>
          <code className="mt-1 block break-all font-mono text-accent">{freshKey}</code>
          <button
            className="mt-2 text-[11px] text-muted underline"
            onClick={() => setFreshKey(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      <Table
        head={
          <>
            <Th>Name</Th>
            <Th>Prefix</Th>
            <Th>Scopes</Th>
            <Th>Last used</Th>
            <Th>Status</Th>
            <Th>Actions</Th>
          </>
        }
      >
        {keys.map((k) => {
          const revoked = !!k.revoked_at;
          return (
            <tr key={k.id}>
              <Td>{k.name}</Td>
              <Td>
                <span className="font-mono text-xs">egq_{k.prefix}…</span>
              </Td>
              <Td>
                <div className="flex flex-wrap gap-1">
                  {k.scopes.map((s) => (
                    <Badge key={s} severity="info">
                      {s}
                    </Badge>
                  ))}
                </div>
              </Td>
              <Td>{formatDateTime(k.last_used_at)}</Td>
              <Td>
                <Badge severity={revoked ? "medium" : "ok"}>
                  {revoked ? "revoked" : "active"}
                </Badge>
              </Td>
              <Td>
                <Button
                  size="sm"
                  variant="danger"
                  disabled={revoked || revoke.isPending}
                  onClick={() => {
                    if (confirm(`Revoke "${k.name}"?`)) revoke.mutate(k.id);
                  }}
                >
                  Revoke
                </Button>
              </Td>
            </tr>
          );
        })}
      </Table>

      {revoke.error && (
        <p className="text-xs text-critical">{(revoke.error as ApiError).message}</p>
      )}

      <CreateKeyDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(key) => setFreshKey(key)}
      />
    </div>
  );
}

function CreateKeyDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (key: string) => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<ApiKeyScope[]>(["ingest:events"]);
  const [expiresInDays, setExpiresInDays] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.post<ApiKeyCreated>("/api-keys", {
        name,
        scopes,
        expires_in_days: expiresInDays ? Number(expiresInDays) : undefined,
      }),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ["api-keys"] });
      onCreated(created.api_key);
      setName("");
      setScopes(["ingest:events"]);
      setExpiresInDays("");
      onClose();
    },
  });

  const toggle = (s: ApiKeyScope) =>
    setScopes((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Create API key"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={create.isPending || !name || scopes.length === 0}
          >
            {create.isPending ? "Creating…" : "Create"}
          </Button>
        </>
      }
    >
      <Field label="Name" htmlFor="nk-name">
        <Input id="nk-name" value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="Scopes">
        <div className="space-y-1.5">
          {SCOPES.map((s) => (
            <label key={s} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={scopes.includes(s)}
                onChange={() => toggle(s)}
              />
              <span className="font-mono text-xs">{s}</span>
            </label>
          ))}
        </div>
      </Field>
      <Field label="Expires in (days)" htmlFor="nk-exp" hint="Leave blank for no expiry.">
        <Input
          id="nk-exp"
          type="number"
          min={1}
          value={expiresInDays}
          onChange={(e) => setExpiresInDays(e.target.value)}
        />
      </Field>
      {create.error && (
        <p className="text-xs text-critical">{(create.error as ApiError).message}</p>
      )}
    </Dialog>
  );
}
