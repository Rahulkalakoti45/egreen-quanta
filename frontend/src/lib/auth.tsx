import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  api,
  apiRequest,
  registerAuthLostHandler,
  registerRefreshHandler,
  setAccessToken,
} from "@/lib/api";
import { ROLE_RANK, type Me, type Role, type TokenResponse } from "@/types/api";

interface AuthState {
  user: Me | null;
  status: "loading" | "authenticated" | "anonymous";
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string, totpCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
  hasRole: (...roles: Role[]) => boolean;
  atLeast: (role: Role) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Persist only the refresh token (rotating, low-value) so a reload can re-auth. */
const RT_KEY = "egq.rt";
function readRt(): string | null {
  try {
    return localStorage.getItem(RT_KEY);
  } catch {
    return null;
  }
}
function writeRt(v: string | null): void {
  try {
    if (v) localStorage.setItem(RT_KEY, v);
    else localStorage.removeItem(RT_KEY);
  } catch {
    /* ignore */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, status: "loading" });
  const refreshToken = useRef<string | null>(readRt());

  const applyTokens = useCallback((t: TokenResponse) => {
    setAccessToken(t.access_token);
    refreshToken.current = t.refresh_token;
    writeRt(t.refresh_token);
  }, []);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    refreshToken.current = null;
    writeRt(null);
    setState({ user: null, status: "anonymous" });
  }, []);

  const doRefresh = useCallback(async (): Promise<boolean> => {
    const rt = refreshToken.current;
    if (!rt) return false;
    try {
      const t = await apiRequest<TokenResponse>("/auth/refresh", {
        method: "POST",
        body: { refresh_token: rt },
        skipAuthRetry: true,
      });
      applyTokens(t);
      return true;
    } catch {
      return false;
    }
  }, [applyTokens]);

  const refreshMe = useCallback(async () => {
    const me = await api.get<Me>("/auth/me");
    setState({ user: me, status: "authenticated" });
  }, []);

  const login = useCallback(
    async (email: string, password: string, totpCode?: string) => {
      const t = await apiRequest<TokenResponse>("/auth/login", {
        method: "POST",
        body: { email, password, totp_code: totpCode || undefined },
        skipAuthRetry: true,
      });
      applyTokens(t);
      await refreshMe();
    },
    [applyTokens, refreshMe],
  );

  const logout = useCallback(async () => {
    const rt = refreshToken.current;
    try {
      await apiRequest("/auth/logout", {
        method: "POST",
        body: { refresh_token: rt },
        skipAuthRetry: true,
      });
    } catch {
      /* best effort */
    }
    clearSession();
  }, [clearSession]);

  // Wire the api client's refresh/deauth hooks to this provider.
  useEffect(() => {
    registerRefreshHandler(doRefresh);
    registerAuthLostHandler(clearSession);
    return () => {
      registerRefreshHandler(null);
      registerAuthLostHandler(null);
    };
  }, [doRefresh, clearSession]);

  // Bootstrap: try to resume a session from a stored refresh token.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!refreshToken.current) {
        setState({ user: null, status: "anonymous" });
        return;
      }
      const ok = await doRefresh();
      if (cancelled) return;
      if (!ok) {
        clearSession();
        return;
      }
      try {
        await refreshMe();
      } catch {
        if (!cancelled) clearSession();
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login,
      logout,
      refreshMe,
      hasRole: (...roles: Role[]) => !!state.user && roles.includes(state.user.role),
      atLeast: (role: Role) =>
        !!state.user && ROLE_RANK[state.user.role] >= ROLE_RANK[role],
    }),
    [state, login, logout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
