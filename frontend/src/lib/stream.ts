import { getAccessToken } from "@/lib/api";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export interface StreamEvent {
  type: string;
  [k: string]: unknown;
}

/**
 * Consume the SSE alert stream via `fetch` (so we can send the Authorization
 * header, which `EventSource` cannot). Reconnects with backoff until `stop()`.
 */
export function openAlertStream(
  onEvent: (e: StreamEvent) => void,
  onStatus?: (connected: boolean) => void,
): () => void {
  let stopped = false;
  let controller: AbortController | null = null;
  let retry = 1000;

  async function loop() {
    while (!stopped) {
      controller = new AbortController();
      try {
        const resp = await fetch(`${BASE}/stream/alerts`, {
          headers: { Authorization: `Bearer ${getAccessToken() ?? ""}` },
          credentials: "include",
          signal: controller.signal,
        });
        if (!resp.ok || !resp.body) throw new Error(`stream ${resp.status}`);
        onStatus?.(true);
        retry = 1000;

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!stopped) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";
          for (const frame of frames) {
            const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
            if (!dataLine) continue;
            try {
              onEvent(JSON.parse(dataLine.slice(5).trim()) as StreamEvent);
            } catch {
              /* ignore malformed frame */
            }
          }
        }
      } catch {
        onStatus?.(false);
      }
      if (stopped) break;
      await new Promise((r) => setTimeout(r, retry));
      retry = Math.min(retry * 2, 15000);
    }
  }

  void loop();
  return () => {
    stopped = true;
    controller?.abort();
    onStatus?.(false);
  };
}
