import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge, Input, LoadingPane, Table, Td, Th, type Severity } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DetectionRule } from "@/types/api";

export function RulesPanel() {
  const qc = useQueryClient();
  const { atLeast } = useAuth();
  const canEdit = atLeast("analyst");

  const { data, isLoading } = useQuery({
    queryKey: ["detection-rules"],
    queryFn: () => api.get<DetectionRule[]>("/detections/rules"),
  });

  const patch = useMutation({
    mutationFn: (v: { code: string; body: Partial<Pick<DetectionRule, "enabled" | "weight">> }) =>
      api.patch(`/detections/rules/${v.code}`, v.body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["detection-rules"] }),
  });

  if (isLoading) return <LoadingPane />;
  const rules = data ?? [];

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        {rules.filter((r) => r.enabled).length} of {rules.length} rules enabled. Weight scales a
        rule&apos;s contribution to the blended risk score.
      </p>
      <Table
        head={
          <>
            <Th>Code</Th>
            <Th>Name</Th>
            <Th>Category</Th>
            <Th>Severity</Th>
            <Th>Enabled</Th>
            <Th>Weight</Th>
          </>
        }
      >
        {rules.map((r) => (
          <tr key={r.code}>
            <Td>
              <span className="font-mono text-xs">{r.code}</span>
            </Td>
            <Td>
              <span title={r.description}>{r.name}</span>
            </Td>
            <Td>
              <span className="text-xs text-muted">{r.category}</span>
            </Td>
            <Td>
              <Badge severity={r.default_severity as Severity}>{r.default_severity}</Badge>
            </Td>
            <Td>
              <input
                type="checkbox"
                checked={r.enabled}
                disabled={!canEdit || patch.isPending}
                onChange={(e) =>
                  patch.mutate({ code: r.code, body: { enabled: e.target.checked } })
                }
              />
            </Td>
            <Td>
              <Input
                type="number"
                min={0}
                max={5}
                step={0.1}
                defaultValue={r.weight}
                disabled={!canEdit}
                onBlur={(e) => {
                  const w = Number(e.target.value);
                  if (w !== r.weight) patch.mutate({ code: r.code, body: { weight: w } });
                }}
                className="h-8 w-20 py-0"
              />
            </Td>
          </tr>
        ))}
      </Table>
    </div>
  );
}
