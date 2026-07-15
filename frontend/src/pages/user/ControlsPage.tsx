import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userApi } from "../../api/user";
import { ModeBadge } from "../../components/StatusBadge";

export function ControlsPage() {
  const qc = useQueryClient();
  const [pair, setPair] = useState("");

  // Same query key refreshBot already invalidates, so the badge stays consistent.
  const bot = useQuery({ queryKey: ["me-bot"], queryFn: userApi.myBot, retry: false });
  const isLive = bot.data?.dry_run === false;

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

  // Force entry bypasses the strategy and buys immediately. In live that is real money
  // leaving the account on one click, so make the user say it out loud.
  const confirmForceEnter = () => {
    if (
      isLive &&
      !confirm(
        `Force a REAL buy of ${pair} with real money?\n\n` +
          `This skips the strategy and places the order immediately.`,
      )
    )
      return;
    forceEnter.mutate();
  };

  return (
    <>
      {isLive && (
        <div className="card">
          <div className="row">
            <ModeBadge dryRun={false} />
            <span>This bot is trading with real money on the exchange.</span>
          </div>
        </div>
      )}

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
            <button
              className={isLive ? "danger" : undefined}
              onClick={confirmForceEnter}
              disabled={!pair || forceEnter.isPending}
            >
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
