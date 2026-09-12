import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/lib/auth";
import { queryClient } from "@/lib/query";

function Probe() {
  const { status, user, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user">{user?.email ?? "none"}</span>
      <button onClick={() => login("admin@egreen.local", "pw")}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

function renderProbe() {
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

const okJson = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });

beforeEach(() => {
  localStorage.clear();
  queryClient.clear();
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("AuthProvider", () => {
  it("starts anonymous when there is no stored refresh token", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(okJson({}));
    renderProbe();
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("anonymous"),
    );
  });

  it("authenticates on login and exposes the user", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/auth/login")) {
        return okJson({
          access_token: "a",
          refresh_token: "r",
          token_type: "bearer",
          expires_in: 900,
          role: "admin",
        });
      }
      if (url.endsWith("/auth/me")) {
        return okJson({
          id: "1",
          email: "admin@egreen.local",
          full_name: "Ada",
          role: "admin",
          totp_enabled: false,
        });
      }
      return okJson({});
    });

    renderProbe();
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("anonymous"),
    );

    await userEvent.click(screen.getByText("login"));
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("authenticated"),
    );
    expect(screen.getByTestId("user").textContent).toBe("admin@egreen.local");
    expect(localStorage.getItem("egq.rt")).toBe("r");
    expect(fetchMock).toHaveBeenCalled();
  });
});
