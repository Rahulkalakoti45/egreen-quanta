import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge, Button, Dialog, Field, Input, LoadingPane, Select, Table, Td, Th } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import type { Page, Role, User } from "@/types/api";

const ROLES: Role[] = ["admin", "analyst", "auditor", "viewer"];

export function UsersPanel() {
  const qc = useQueryClient();
  const { user: me } = useAuth();
  const [creating, setCreating] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<Page<User>>("/users", { params: { limit: 100 } }),
  });

  const patch = useMutation({
    mutationFn: (vars: { id: string; body: Partial<Pick<User, "role" | "is_active">> }) =>
      api.patch<User>(`/users/${vars.id}`, vars.body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  if (isLoading) return <LoadingPane />;
  if (error) return <p className="text-sm text-critical">{(error as Error).message}</p>;

  const users = data?.items ?? [];

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setCreating(true)}>
          + New user
        </Button>
      </div>

      <Table
        head={
          <>
            <Th>Email</Th>
            <Th>Name</Th>
            <Th>Role</Th>
            <Th>Status</Th>
            <Th>Last login</Th>
            <Th>Actions</Th>
          </>
        }
      >
        {users.map((u) => {
          const isSelf = u.id === me?.id;
          return (
            <tr key={u.id}>
              <Td>{u.email}</Td>
              <Td>{u.full_name || "—"}</Td>
              <Td>
                <Select
                  value={u.role}
                  disabled={isSelf || patch.isPending}
                  onChange={(e) =>
                    patch.mutate({ id: u.id, body: { role: e.target.value as Role } })
                  }
                  className="h-8 py-0"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </Select>
              </Td>
              <Td>
                <Badge severity={u.is_active ? "ok" : "medium"}>
                  {u.is_active ? "active" : "disabled"}
                </Badge>
              </Td>
              <Td>{formatDateTime(u.last_login_at)}</Td>
              <Td>
                <div className="flex gap-1.5">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={isSelf || patch.isPending}
                    onClick={() =>
                      patch.mutate({ id: u.id, body: { is_active: !u.is_active } })
                    }
                  >
                    {u.is_active ? "Disable" : "Enable"}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={isSelf || remove.isPending}
                    onClick={() => {
                      if (confirm(`Delete ${u.email}?`)) remove.mutate(u.id);
                    }}
                  >
                    Delete
                  </Button>
                </div>
              </Td>
            </tr>
          );
        })}
      </Table>

      {(patch.error || remove.error) && (
        <p className="text-xs text-critical">
          {((patch.error || remove.error) as ApiError).message}
        </p>
      )}

      <CreateUserDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function CreateUserDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [password, setPassword] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.post<User>("/users", {
        email,
        full_name: fullName,
        role,
        password,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setEmail("");
      setFullName("");
      setPassword("");
      setRole("viewer");
      onClose();
    },
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Create user"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create"}
          </Button>
        </>
      }
    >
      <Field label="Email" htmlFor="nu-email">
        <Input
          id="nu-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </Field>
      <Field label="Full name" htmlFor="nu-name">
        <Input id="nu-name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
      </Field>
      <Field label="Role" htmlFor="nu-role">
        <Select id="nu-role" value={role} onChange={(e) => setRole(e.target.value as Role)}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Temporary password" htmlFor="nu-pw" hint="At least 12 characters.">
        <Input
          id="nu-pw"
          type="text"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </Field>
      {create.error && (
        <p className="text-xs text-critical">{(create.error as ApiError).message}</p>
      )}
    </Dialog>
  );
}
