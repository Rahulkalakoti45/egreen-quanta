import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { RequireRole } from "@/components/RequireAuth";
import {
  Badge,
  Button,
  Card,
  Field,
  LoadingPane,
  PageHeader,
  TabBar,
  Table,
  Td,
  textareaClass,
  Th,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import type {
  ObservedCertificate,
  Page,
  TrustAnchor,
  VerificationResult,
} from "@/types/api";

import { VerificationResultCard } from "../signatures/VerificationResultCard";

type Tab = "validate" | "trust-store" | "observed";

export function CertificatesPage() {
  const [tab, setTab] = useState<Tab>("validate");
  const { atLeast } = useAuth();

  const tabs = [
    ["validate", "Validate"],
    ["trust-store", "Trust store"],
    ["observed", "Observed"],
  ] as const;

  return (
    <>
      <PageHeader
        eyebrow="Cryptographic core"
        title="Certificates & trust"
        description="Validate X.509 chains against the trust store, manage CA anchors, and review every certificate the platform has seen."
      />
      <TabBar tabs={tabs} value={tab} onChange={setTab} />

      <div key={tab} className="animate-fade-up">
        {tab === "validate" && <ValidatePanel />}
        {tab === "trust-store" &&
          (atLeast("auditor") ? (
            <TrustStorePanel canEdit={atLeast("admin")} />
          ) : (
            <RequireRole atLeast="auditor">
              <span />
            </RequireRole>
          ))}
        {tab === "observed" && <ObservedPanel />}
      </div>
    </>
  );
}

function ValidatePanel() {
  const [pem, setPem] = useState("");
  const [eku, setEku] = useState("");

  const validate = useMutation<VerificationResult, ApiError>({
    mutationFn: () =>
      api.post<VerificationResult>("/certificates/validate", {
        certificate_pem: pem,
        expected_eku: eku || null,
      }),
  });

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <Field label="Certificate or chain (PEM)">
          <textarea
            rows={8}
            value={pem}
            onChange={(e) => setPem(e.target.value)}
            placeholder="-----BEGIN CERTIFICATE-----"
            className={textareaClass}
          />
        </Field>
        <Field label="Expected extended key usage (optional)" htmlFor="cv-eku">
          <input
            id="cv-eku"
            value={eku}
            onChange={(e) => setEku(e.target.value)}
            placeholder="codeSigning"
            className="w-full rounded-lg border border-hairline/10 bg-hairline/[0.03] px-3 py-2 text-sm text-fg outline-none transition-all placeholder:text-faint focus:border-primary/50 focus:ring-4 focus:ring-primary/10"
          />
        </Field>
        <Button onClick={() => validate.mutate()} disabled={validate.isPending || !pem}>
          {validate.isPending ? "Validating…" : "Validate"}
        </Button>
        {validate.error && (
          <span className="ml-3 text-xs text-critical">{validate.error.message}</span>
        )}
      </Card>
      {validate.data && <VerificationResultCard result={validate.data} />}
    </div>
  );
}

function TrustStorePanel({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [pem, setPem] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["trust-anchors"],
    queryFn: () => api.get<TrustAnchor[]>("/trust-store/anchors"),
  });

  const add = useMutation<TrustAnchor, ApiError>({
    mutationFn: () =>
      api.post<TrustAnchor>("/trust-store/anchors", { name, certificate_pem: pem }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["trust-anchors"] });
      setName("");
      setPem("");
    },
  });
  const toggle = useMutation({
    mutationFn: (v: { id: string; enabled: boolean }) =>
      api.patch(`/trust-store/anchors/${v.id}`, { enabled: v.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["trust-anchors"] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/trust-store/anchors/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["trust-anchors"] }),
  });

  if (isLoading) return <LoadingPane />;
  const anchors = data ?? [];

  return (
    <div className="space-y-4">
      {canEdit && (
        <Card className="space-y-2">
          <Field label="Anchor name" htmlFor="ta-name">
            <input
              id="ta-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-hairline/10 bg-hairline/[0.03] px-3 py-2 text-sm text-fg outline-none transition-all placeholder:text-faint focus:border-primary/50 focus:ring-4 focus:ring-primary/10"
            />
          </Field>
          <Field label="Root CA certificate (PEM)">
            <textarea
              rows={5}
              value={pem}
              onChange={(e) => setPem(e.target.value)}
              className={textareaClass}
            />
          </Field>
          <Button onClick={() => add.mutate()} disabled={add.isPending || !name || !pem}>
            {add.isPending ? "Adding…" : "Add trust anchor"}
          </Button>
          {add.error && <span className="ml-3 text-xs text-critical">{add.error.message}</span>}
        </Card>
      )}

      <Table
        head={
          <>
            <Th>Name</Th>
            <Th>Subject</Th>
            <Th>Expires</Th>
            <Th>Status</Th>
            {canEdit && <Th>Actions</Th>}
          </>
        }
      >
        {anchors.map((a) => (
          <tr key={a.id}>
            <Td>{a.name}</Td>
            <Td>
              <span className="font-mono text-xs">{a.subject}</span>
            </Td>
            <Td>{formatDateTime(a.not_after)}</Td>
            <Td>
              <Badge severity={a.enabled ? "ok" : "medium"}>
                {a.enabled ? "enabled" : "disabled"}
              </Badge>
            </Td>
            {canEdit && (
              <Td>
                <div className="flex gap-1.5">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => toggle.mutate({ id: a.id, enabled: !a.enabled })}
                  >
                    {a.enabled ? "Disable" : "Enable"}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => confirm(`Remove "${a.name}"?`) && remove.mutate(a.id)}
                  >
                    Remove
                  </Button>
                </div>
              </Td>
            )}
          </tr>
        ))}
      </Table>
    </div>
  );
}

function ObservedPanel() {
  const [reuseOnly, setReuseOnly] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["observed-certs", reuseOnly],
    queryFn: () =>
      api.get<Page<ObservedCertificate>>("/certificates", {
        params: { limit: 100, key_reuse_only: reuseOnly },
      }),
  });

  if (isLoading) return <LoadingPane />;
  const rows = data?.items ?? [];

  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-xs text-muted">
        <input
          type="checkbox"
          checked={reuseOnly}
          onChange={(e) => setReuseOnly(e.target.checked)}
        />
        Show only keys reused across identities (T11)
      </label>
      <Table
        head={
          <>
            <Th>Subject</Th>
            <Th>Issuer</Th>
            <Th>Key</Th>
            <Th>Seen</Th>
            <Th>Last seen</Th>
          </>
        }
      >
        {rows.map((c) => (
          <tr key={c.id}>
            <Td>
              <span className="font-mono text-xs">{c.subject}</span>
            </Td>
            <Td>
              <span className="font-mono text-xs">{c.issuer}</span>
            </Td>
            <Td>
              {c.key_type}
              {c.key_bits ? `-${c.key_bits}` : ""} {c.curve ?? ""}
            </Td>
            <Td>{c.times_seen}</Td>
            <Td>{formatDateTime(c.last_seen_at)}</Td>
          </tr>
        ))}
      </Table>
      {rows.length === 0 && (
        <p className="text-sm text-muted">No certificates observed yet — run a verification.</p>
      )}
    </div>
  );
}
