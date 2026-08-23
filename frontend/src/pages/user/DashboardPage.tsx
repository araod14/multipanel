import { useQuery } from "@tanstack/react-query";

import { userApi } from "../../api/user";
import type { FtPerformanceEntry, FtProfit } from "../../api/types";
import { ModeBadge, StatusBadge } from "../../components/StatusBadge";
import { fmt, pct, signed } from "../../lib/format";

export function DashboardPage() {
  const bot = useQuery({ queryKey: ["me-bot"], queryFn: userApi.myBot, retry: false });
  const profit = useQuery({
    queryKey: ["me-profit"],
    queryFn: userApi.profit,
    retry: false,
    refetchInterval: 15000,
  });
  const balance = useQuery({
    queryKey: ["me-balance"],
    queryFn: userApi.balance,
    retry: false,
    refetchInterval: 15000,
  });
  const performance = useQuery({
    queryKey: ["me-performance"],
    queryFn: userApi.performance,
    retry: false,
    refetchInterval: 30000,
  });
  const stats = useQuery({
    queryKey: ["me-stats"],
    queryFn: userApi.stats,
    retry: false,
    refetchInterval: 30000,
  });
  const whitelist = useQuery({
    queryKey: ["me-whitelist"],
    queryFn: () => userApi.whitelist() as Promise<any>,
    retry: false,
    refetchInterval: 30000,
  });

  const stake = bot.data?.stake_currency ?? balance.data?.stake ?? "";
  const p = profit.data;

  // Rank pairs by absolute profit for the winners / losers columns.
  const perf = performance.data ?? [];
  const winners = [...perf].filter((e) => e.profit_abs > 0).sort((a, b) => b.profit_abs - a.profit_abs).slice(0, 5);
  const losers = [...perf].filter((e) => e.profit_abs < 0).sort((a, b) => a.profit_abs - b.profit_abs).slice(0, 5);

  const exitReasons = stats.data ? Object.entries(stats.data.exit_reasons) : [];
  const pf = profitFactor(p);

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
            <Metric
              label="Closed profit"
              value={`${signed(p?.profit_closed_coin)} ${stake}`}
              sub={pct(p?.profit_closed_ratio)}
              tone={p?.profit_closed_coin}
            />
            <Metric
              label="Total profit"
              value={`${signed(p?.profit_all_coin)} ${stake}`}
              sub={pct(p?.profit_all_ratio)}
              tone={p?.profit_all_coin}
            />
            <Metric label="Closed trades" value={p?.closed_trade_count ?? "—"} />
            <Metric label="Winrate" value={pct(p?.winrate)} />
            <Metric label="Ganados" value={p?.winning_trades ?? "—"} tone={1} />
            <Metric label="Perdidos" value={p?.losing_trades ?? "—"} tone={p?.losing_trades ? -1 : 0} />
          </div>
        )}
      </div>

      <div className="card">
        <h2>Estrategia</h2>
        {profit.isError ? (
          <p className="muted">Unavailable (bot starting or stopped).</p>
        ) : (
          <>
            <div className="grid">
              <Metric label="Profit factor" value={pf.value} sub={pf.sub} />
              <Metric label="Expectancy" value={fmt(p?.expectancy, 4)} />
              <Metric label="Duración media" value={p?.avg_duration || "—"} />
              <Metric
                label="Max drawdown"
                value={pct(p?.max_drawdown)}
                tone={p?.max_drawdown ? -1 : 0}
              />
              <Metric label="Mejor par" value={p?.best_pair || "—"} sub={p ? signed(p.best_pair_profit_abs) : undefined} />
            </div>

            <h3 className="subhead">Razones de salida</h3>
            {stats.isError || exitReasons.length === 0 ? (
              <p className="muted">Sin datos de salidas todavía.</p>
            ) : (
              <table className="responsive-table">
                <thead>
                  <tr>
                    <th>Razón</th>
                    <th>Ganados</th>
                    <th>Perdidos</th>
                    <th>Empates</th>
                  </tr>
                </thead>
                <tbody>
                  {exitReasons.map(([reason, s]) => (
                    <tr key={reason}>
                      <td data-label="Razón" className="table-primary">{reason}</td>
                      <td data-label="Ganados" className="amt pos">{s.wins}</td>
                      <td data-label="Perdidos" className="amt neg">{s.losses}</td>
                      <td data-label="Empates" className="muted">{s.draws}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>

      <div className="card">
        <h2>Monedas</h2>
        {performance.isError ? (
          <p className="muted">Unavailable (bot starting or stopped).</p>
        ) : perf.length === 0 ? (
          <p className="muted">Aún no hay trades cerrados.</p>
        ) : (
          <div className="grid ranking-grid">
            <PairRanking title="Más ganadoras" entries={winners} empty="Sin ganadoras aún." stake={stake} />
            <PairRanking title="Más perdedoras" entries={losers} empty="Sin perdedoras aún." stake={stake} />
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
            <Metric label="Total" value={`${fmt(balance.data?.total)} ${stake}`} />
            <Metric label="Gestionado por el bot" value={`${fmt(balance.data?.total_bot)} ${stake}`} />
            <Metric label="Capital inicial" value={`${fmt(balance.data?.starting_capital)} ${stake}`} />
            <Metric label="Monedas" value={balance.data?.currencies?.length ?? "—"} />
          </div>
        )}
      </div>
    </>
  );
}

/** Freqtrade computes `winning_profit / abs(losing_profit)`, which is infinite when a bot
 *  has no losing trades; Pydantic serializes that as null. Distinguish that case from
 *  "no data yet" so a flawless bot reads as ∞ rather than an empty dash. */
function profitFactor(p: FtProfit | undefined): { value: string; sub?: string } {
  if (!p) return { value: "—" };
  if (typeof p.profit_factor === "number" && Number.isFinite(p.profit_factor)) {
    return { value: fmt(p.profit_factor, 2) };
  }
  if (p.closed_trade_count > 0 && p.losing_trades === 0) {
    return { value: "∞", sub: "sin pérdidas aún" };
  }
  return { value: "—" };
}

function PairRanking({
  title,
  entries,
  empty,
  stake,
}: {
  title: string;
  entries: FtPerformanceEntry[];
  empty: string;
  stake: string;
}) {
  return (
    <div>
      <h3 className="subhead">{title}</h3>
      {entries.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <table>
          <tbody>
            {entries.map((e) => (
              <tr key={e.pair}>
                <td>{e.pair}</td>
                <td className={`amt ${e.profit_abs >= 0 ? "pos" : "neg"}`}>
                  {signed(e.profit_abs)} {stake}
                </td>
                <td className="muted">{e.count} trades</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: number;
}) {
  const toneClass = typeof tone === "number" && tone !== 0 ? (tone > 0 ? "pos" : "neg") : "";
  return (
    <div className="metric">
      <div className="muted">{label}</div>
      <div className={`v ${toneClass}`}>{value}</div>
      {sub !== undefined && <div className="muted">{sub}</div>}
    </div>
  );
}
