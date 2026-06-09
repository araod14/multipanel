import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userApi } from "../../api/user";

export function ControlsPage() {
  const qc = useQueryClient();
  const [pair, setPair] = useState("");

  const refreshBot = () => qc.invalidateQueries({ queryKey: ["me-bot"] });
  const start = useMutation({ mutationFn: () => userApi.start(), onSuccess: refreshBot });
  const stop = useMutation({ mutationFn: () => userApi.stop(), onSuccess: refreshBot });
  const forceEnter = useMutation({
    mutationFn: () => userApi.forceEnter(pair),
    onSuccess: () => {
      setPair("");
      qc.invalidateQueries({ queryKey: ["me-trades"] });
    },
  });

  const logs = useQuery({
    queryKey: ["me-logs"],
    queryFn: () => userApi.logs() as Promise<any>,
    retry: false,
    refetchInterval: 10000,
  });

  const logLines: string = Array.isArray(logs.data?.logs)
    ? logs.data.logs.map((l: any[]) => `${l[0]} ${l[2]} ${l[4]}`).join("\n")
    : "";

  return (
    <>
      <div className="card">
        <h2>Trading loop</h2>
        <div className="row">
          <button onClick={() => start.mutate()} disabled={start.isPending}>
            Start
          </button>
          <button className="secondary" onClick={() => stop.mutate()} disabled={stop.isPending}>
            Stop
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Force entry</h2>
        <div className="row">
          <div style={{ flex: 1 }}>
            <label>Pair (e.g. BTC/USDT)</label>
            <input value={pair} onChange={(e) => setPair(e.target.value)} />
          </div>
          <div style={{ alignSelf: "flex-end" }}>
            <button onClick={() => forceEnter.mutate()} disabled={!pair || forceEnter.isPending}>
              Force enter
            </button>
          </div>
        </div>
        {forceEnter.isError && <div className="error">Could not force entry.</div>}
      </div>

      <div className="card">
        <h2>Logs</h2>
        {logs.isError ? (
          <p className="muted">Unavailable.</p>
        ) : (
          <pre className="logs">{logLines || "No recent logs."}</pre>
        )}
      </div>
    </>
  );
}
