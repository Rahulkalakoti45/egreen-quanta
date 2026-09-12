import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Button, Card, Field, Input, LoadingPane, Select, Table, Td, Th } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import type { MlModel, MlStatus } from "@/types/api";

export function MlPanel() {
  const qc = useQueryClient();
  const { atLeast } = useAuth();
  const canTrain = atLeast("analyst");
  const canActivate = atLeast("admin");

  const status = useQuery({
    queryKey: ["ml-status"],
    queryFn: () => api.get<MlStatus>("/ml/status"),
  });
  const models = useQuery({
    queryKey: ["ml-models"],
    queryFn: () => api.get<MlModel[]>("/ml/models"),
  });

  const [algo, setAlgo] = useState("isolation_forest");
  const [source, setSource] = useState("dataset");
  const [contamination, setContamination] = useState("0.08");

  const train = useMutation<MlModel, ApiError>({
    mutationFn: () =>
      api.post<MlModel>("/ml/train", {
        algo,
        source,
        contamination: Number(contamination),
        activate: false,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ml-models"] });
      qc.invalidateQueries({ queryKey: ["ml-status"] });
    },
  });
  const activate = useMutation({
    mutationFn: (id: string) => api.post(`/ml/models/${id}/activate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ml-models"] });
      qc.invalidateQueries({ queryKey: ["ml-status"] });
    },
  });
  const deactivate = useMutation({
    mutationFn: () => api.post("/ml/models/deactivate"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ml-models"] });
      qc.invalidateQueries({ queryKey: ["ml-status"] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/ml/models/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ml-models"] }),
  });

  if (status.isLoading || models.isLoading) return <LoadingPane />;
  const s = status.data;
  const rows = models.data ?? [];

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3">
        <Badge severity={s?.enabled ? "ok" : "medium"}>
          {s?.enabled ? "ML enabled" : "ML disabled"}
        </Badge>
        <span className="text-xs text-muted">
          feature schema v{s?.feature_schema_version} · {s?.feature_count} features · blend weight{" "}
          {s?.anomaly_weight}
        </span>
        {!s?.enabled && (
          <span className="text-xs text-muted">
            Set <code className="rounded bg-hairline/[0.06] px-1">ML_ENABLED=true</code> and restart the
            backend for scores to feed the risk engine. You can still train + evaluate models here.
          </span>
        )}
        {s?.active_model_id && (
          <span className="text-xs text-ok">active model {s.active_model_id.slice(0, 8)}</span>
        )}
      </Card>

      {canTrain && (
        <Card className="grid gap-3 sm:grid-cols-4">
          <Field label="Algorithm" htmlFor="ml-algo">
            <Select id="ml-algo" value={algo} onChange={(e) => setAlgo(e.target.value)}>
              <option value="isolation_forest">Isolation Forest</option>
              <option value="one_class_svm">One-Class SVM</option>
            </Select>
          </Field>
          <Field label="Training data" htmlFor="ml-src">
            <Select id="ml-src" value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="dataset">Bundled dataset (labelled)</option>
              <option value="history">Verification history (30d)</option>
            </Select>
          </Field>
          <Field label="Contamination" htmlFor="ml-cont">
            <Input
              id="ml-cont"
              type="number"
              min={0.01}
              max={0.4}
              step={0.01}
              value={contamination}
              onChange={(e) => setContamination(e.target.value)}
            />
          </Field>
          <div className="flex items-end">
            <Button onClick={() => train.mutate()} disabled={train.isPending}>
              {train.isPending ? "Training…" : "Train model"}
            </Button>
          </div>
          {train.error && (
            <p className="text-xs text-critical sm:col-span-4">{train.error.message}</p>
          )}
        </Card>
      )}

      <Table
        head={
          <>
            <Th>Algorithm</Th>
            <Th>Trained</Th>
            <Th>Samples</Th>
            <Th>Source</Th>
            <Th>Metrics</Th>
            <Th>Status</Th>
            {canActivate && <Th>Actions</Th>}
          </>
        }
      >
        {rows.map((m) => (
          <tr key={m.id}>
            <Td>{m.algo}</Td>
            <Td>{formatDateTime(m.trained_at)}</Td>
            <Td>{m.n_train}</Td>
            <Td>
              <span className="text-xs text-muted">{m.source}</span>
            </Td>
            <Td>
              <span className="text-[11px] text-muted">
                mean {m.metrics.mean_score ?? "—"}
                {m.metrics.eval_recall != null && (
                  <>
                    {" "}
                    · recall {m.metrics.eval_recall} · prec {m.metrics.eval_precision}
                  </>
                )}
              </span>
            </Td>
            <Td>
              <Badge severity={m.is_active ? "ok" : "info"}>
                {m.is_active ? "active" : "idle"}
              </Badge>
            </Td>
            {canActivate && (
              <Td>
                <div className="flex gap-1.5">
                  {m.is_active ? (
                    <Button size="sm" variant="secondary" onClick={() => deactivate.mutate()}>
                      Deactivate
                    </Button>
                  ) : (
                    <Button size="sm" onClick={() => activate.mutate(m.id)}>
                      Activate
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => confirm("Delete this model?") && remove.mutate(m.id)}
                  >
                    Delete
                  </Button>
                </div>
              </Td>
            )}
          </tr>
        ))}
      </Table>
      {rows.length === 0 && (
        <p className="text-sm text-muted">No models yet — train one from the bundled dataset.</p>
      )}
    </div>
  );
}
