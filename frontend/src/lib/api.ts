/**
 * HTTP client for the Egreen Quanta API.
 *
 * - Access token is held in memory only (never localStorage).
 * - On a 401 the client attempts a single silent refresh (cookie-based) and retries.
 * - Errors are normalised to `ApiError` with the backend's `{error:{code,message}}` shape.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

let accessToken: string | null = null;
let refreshHandler: (() => Promise<boolean>) | null = null;
let onAuthLost: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}
export function getAccessToken(): string | null {
  return accessToken;
}
export function registerRefreshHandler(fn: (() => Promise<boolean>) | null): void {
  refreshHandler = fn;
}
export function registerAuthLostHandler(fn: (() => void) | null): void {
  onAuthLost = fn;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Skip the automatic refresh-and-retry (used by the refresh call itself). */
  skipAuthRetry?: boolean;
  /** Query-string parameters. */
  params?: Record<string, string | number | boolean | null | undefined>;
}

function buildUrl(path: string, params?: RequestOptions["params"]): string {
  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;
  if (!params) return url;
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined) qs.append(k, String(v));
  }
  const s = qs.toString();
  return s ? `${url}${url.includes("?") ? "&" : "?"}${s}` : url;
}

async function parseError(resp: Response): Promise<ApiError> {
  let code = "http_error";
  let message = resp.statusText || `HTTP ${resp.status}`;
  let details: unknown;
  try {
    const data = (await resp.json()) as Partial<ApiErrorBody>;
    if (data?.error) {
      code = data.error.code ?? code;
      message = data.error.message ?? message;
      details = data.error.details;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(resp.status, code, message, details);
}

export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, params, skipAuthRetry, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  finalHeaders.set("Accept", "application/json");
  let payload: BodyInit | undefined;
  if (body !== undefined) {
    if (body instanceof FormData) {
      payload = body;
    } else {
      finalHeaders.set("Content-Type", "application/json");
      payload = JSON.stringify(body);
    }
  }
  if (accessToken) finalHeaders.set("Authorization", `Bearer ${accessToken}`);

  const doFetch = () =>
    fetch(buildUrl(path, params), {
      ...rest,
      headers: finalHeaders,
      body: payload,
      credentials: "include",
    });

  let resp = await doFetch();

  if (resp.status === 401 && !skipAuthRetry && refreshHandler) {
    const refreshed = await refreshHandler();
    if (refreshed) {
      if (accessToken) finalHeaders.set("Authorization", `Bearer ${accessToken}`);
      resp = await doFetch();
    } else {
      onAuthLost?.();
    }
  }

  if (resp.status === 204) return undefined as T;
  if (!resp.ok) throw await parseError(resp);

  const contentType = resp.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) return (await resp.json()) as T;
  return (await resp.text()) as unknown as T;
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) => apiRequest<T>(path, { ...opts, method: "GET" }),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "PATCH", body }),
  put: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "PUT", body }),
  delete: <T>(path: string, opts?: RequestOptions) =>
    apiRequest<T>(path, { ...opts, method: "DELETE" }),
};
