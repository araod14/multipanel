import { useQuery } from "@tanstack/react-query";

import { userApi } from "../../api/user";
import { ModeBadge, StatusBadge } from "../../components/StatusBadge";

export function DashboardPage() {
  const bot = useQuery({ queryKey: ["me-bot"], queryFn: userApi.myBot, retry: false });
  const profit = useQuery({
    queryKey: ["me-profit"],
    queryFn: () => userApi.profit() as Promise<any>,
    retry: false,
    refetchInterval: 15000,
  });
  const balance = useQuery({
    queryKey: ["me-balance"],
    queryFn: () => userApi.balance() as Promise<any>,
    retry: false,
    refetchInterval: 15000,
  });
  const whitelist = useQuery({
    queryKey: ["me-whitelist"],
    queryFn: () => userApi.whitelist() as Promise<any>,
    retry: false,
    refetchInterval: 30000,
  });

  return (
    <>
      <div className="card">
        <h2>Status</h2>
        {bot.isLoading ? (
          <p className="muted">Loading…</p>
        ) : bot.isError ? (
          <p className="error">No bot is provisioned for your account yet.</p>
        ) : (
          <div className="row">
            <StatusBadge status={bot.data!.status} />
            <ModeBadge dryRun={bot.data!.dry_run} />
            <span className="muted">stake: {bot.data!.stake_currency}</span>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Performance</h2>
        {profit.isError ? (
          <p className="muted">Unavailable (bot starting or stopped).</p>
        ) : (
          <div className="grid">
            <Metric label="Closed profit" value={fmt(profit.data?.profit_closed_coin)} />
            <Metric label="Total profit %" value={pct(profit.data?.profit_all_percent)} />
            <Metric label="Open trades" value={profit.data?.trade_count ?? "—"} />
            <Metric label="Winning trades" value={profit.data?.winning_trades ?? "—"} />
          </div>
        )}
      </div>

      <div className="card">
        <h2>Trading pairs</h2>
        {whitelist.isError ? (
          <p className="muted">Unavailable (bot starting or stopped).</p>
        ) : (whitelist.data?.whitelist?.length ?? 0) === 0 ? (
          <p className="muted">No pairs configured.</p>
        ) : (
          <>
            <p className="muted">
              {whitelist.data.whitelist.length} pairs
              {whitelist.data.method?.length ? ` · ${whitelist.data.method.join(", ")}` : ""}
            </p>
            <div className="row">
              {whitelist.data.whitelist.map((pair: string) => (
                <span key={pair} className="chip chip--plain">
                  {pair}
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="card">
        <h2>Balance</h2>
        {balance.isError ? (
          <p className="muted">Unavailable.</p>
        ) : (
          <div className="grid">
            <Metric label="Total" value={fmt(balance.data?.total)} />
            <Metric label="Currencies" value={balance.data?.currencies?.length ?? "—"} />
          </div>
        )}
      </div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="metric">
      <div className="muted">{label}</div>
      <div className="v">{value}</div>
    </div>
  );
}

function fmt(n: unknown): string {
  return typeof n === "number" ? n.toFixed(4) : "—";
}
function pct(n: unknown): string {
  return typeof n === "number" ? `${(n * 100).toFixed(2)}%` : "—";
}
