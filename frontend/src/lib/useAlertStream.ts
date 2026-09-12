import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { openAlertStream, type StreamEvent } from "@/lib/stream";

/** Global: subscribe to the SSE alert stream while authenticated, refresh queries + toast. */
export function useAlertStream(): { connected: boolean } {
  const { status } = useAuth();
  const qc = useQueryClient();
  const { push } = useToast();
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (status !== "authenticated") return;
    const stop = openAlertStream(
      (e: StreamEvent) => {
        if (e.type !== "alert") return;
        qc.invalidateQueries({ queryKey: ["alerts"] });
        qc.invalidateQueries({ queryKey: ["incidents"] });
        qc.invalidateQueries({ queryKey: ["threat-stats"] });
        push({
          title: String(e.title ?? "New alert"),
          body: `risk ${e.risk_score ?? "?"} · ${(e.rule_codes as string[] | undefined)?.join(", ") ?? ""}`,
          tone: (e.severity as "critical" | "high" | "medium" | "low" | "info") ?? "info",
        });
      },
      setConnected,
    );
    return stop;
  }, [status, qc, push]);

  return { connected };
}
