import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { publicApi } from "../../api/public";
import type { BotStatus, PublicAccount, PublicDailyPoint } from "../../api/types";
import { Metric } from "../../components/Metric";
import { ProfitCell } from "../../components/ProfitCell";
import { Sparkline } from "../../components/Sparkline";
import { ModeBadge, StatusBadge } from "../../components/StatusBadge";
import { fmt, pct, signed } from "../../lib/format";

export function ResultsPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const results = useQuery({
    queryKey: ["public-results"],
    queryFn: publicApi.results,
    retry: false,
    refetchInterval: 30000,
  });

  const data = results.data;
  const stake = data?.stake_currency ?? "USDT";
  const accounts = data?.accounts ?? [];
  const account = accounts.find((a) => a.username === selected) ?? null;

  return (
    <div className="public-shell">
      <header className="public-header">
        <div className="brand">
          <div className="brand-mark">CP</div>
          <div>
            <strong>Resultados</strong>
            <span>Rendimiento de cada cuenta, en vivo</span>
          </div>
        </div>
        <Link className="public-login" to="/login">
          Entrar
        </Link>
      </header>

      <main className="content">
        {results.isLoading ? (
          <p className="muted">Cargando…</p>
        ) : results.isError ? (
          <div className="card">
            <p className="error">No se pudieron cargar los resultados ahora mismo.</p>
          </div>
        ) : !data ? null : (
          <>
            <div className="card">
              <div className="row space-between mb-16">
                <h2 className="mb-0">Resumen</h2>
                <span className="muted">
                  {data.totals.reachable} de {data.totals.accounts} bots respondiendo ·
                  actualizado {new Date(data.generated_at).toLocaleTimeString()}
                </span>
              </div>
              <div className="grid">
                <Metric label="Cuentas" value={data.totals.accounts} sub={`${data.totals.running} en marcha`} />
                <Metric
                  label="Beneficio total"
                  value={`${signed(data.totals.profit_all_abs, 2)} ${stake}`}
                  tone={data.totals.profit_all_abs}
                  sub={`${signed(data.totals.profit_closed_abs, 2)} ${stake} cerrado`}
                />
                <Metric
                  label="Winrate global"
                  value={data.totals.winrate === null ? "—" : pct(data.totals.winrate)}
                  sub={`${data.totals.winning_trades}W / ${data.totals.losing_trades}L`}
                />
                <Metric label="Trades cerrados" value={data.totals.closed_trade_count} />
                <Metric
                  label="Capital desplegado"
                  value={`${fmt(data.totals.total_stake_deployed, 2)} ${stake}`}
                  sub={`${data.totals.open_trades} trades abiertos`}
                />
                <Metric
                  label="Balance agregado"
                  value={`${fmt(data.totals.balance_total, 2)} ${stake}`}
                  sub={`${data.totals.live_accounts} live · ${data.totals.dry_accounts} dry-run`}
                />
              </div>
            </div>

            <div className="card">
              <h2>Cuentas</h2>
              {accounts.length === 0 ? (
                <p className="muted">Todavía no hay ninguna cuenta con bot aprovisionado.</p>
              ) : (
                <table className="responsive-table">
                  <thead>
                    <tr>
                      <th>Cuenta</th>
                      <th>Estado</th>
                      <th>Estrategia</th>
                      <th>Beneficio</th>
                      <th>ROI</th>
                      <th>Trades</th>
                      <th>Winrate</th>
                      <th>Drawdown</th>
                      <th>Stake</th>
                      <th>Pares</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map((a) => (
                      <tr key={a.username} className={rowTone(a)}>
                        <td className="table-primary" data-label="Cuenta">
                          {a.username}
                        </td>
                        <td data-label="Estado">
                          <div className="row">
                            <StatusBadge status={badgeStatus(a)} />
                            <TradingBadge account={a} />
                            <ModeBadge dryRun={a.dry_run} />
                          </div>
                        </td>
                        <td data-label="Estrategia">{a.strategy_label}</td>
                        <td data-label="Beneficio" className={`amt ${toneClass(a.profit_all_abs)}`}>
                          {a.profit_all_abs === null ? "—" : `${signed(a.profit_all_abs, 2)} ${stake}`}
                        </td>
                        <td data-label="ROI">
                          <ProfitCell
                            pct={a.profit_all_ratio === null ? null : a.profit_all_ratio * 100}
                          />
                        </td>
                        <td data-label="Trades" className="num">
                          {a.closed_trade_count ?? "—"}
                        </td>
                        <td data-label="Winrate" className="num">
                          {a.winrate === null ? "—" : pct(a.winrate)}
                        </td>
                        <td data-label="Drawdown" className="num">
                          {a.max_drawdown === null ? "—" : pct(a.max_drawdown)}
                        </td>
                        <td data-label="Stake" className="num">
                          {stakeText(a, stake)}
                        </td>
                        <td data-label="Pares" className="num">
                          {(a.whitelist ?? a.pairs).length}
                        </td>
                        <td className="table-actions">
                          <button
                            className="secondary"
                            onClick={() => setSelected(selected === a.username ? null : a.username)}
                          >
                            {selected === a.username ? "Ocultar" : "Detalle"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {account && <AccountDetail account={account} stake={stake} />}
          </>
        )}
      </main>
    </div>
  );
}

function AccountDetail({ account: a, stake }: { account: PublicAccount; stake: string }) {
  const pairs = a.whitelist ?? a.pairs;
  const perf = [...a.performance].sort((x, y) => (y.profit_abs ?? 0) - (x.profit_abs ?? 0));

  return (
    <div className="card">
      <div className="row space-between mb-16">
        <h2 className="mb-0">{a.username}</h2>
        <div className="row">
          <StatusBadge status={badgeStatus(a)} />
          <TradingBadge account={a} />
          <ModeBadge dryRun={a.dry_run} />
          {a.exchange && <span className="chip chip--plain">{a.exchange}</span>}
        </div>
      </div>

      {!a.reachable && (
        <p className="muted mb-16">
          El bot no está respondiendo ahora mismo — se muestra solo su configuración.
        </p>
      )}

      <h3 className="subhead">Resultados</h3>
      <div className="grid">
        <Metric
          label="Beneficio total"
          value={a.profit_all_abs === null ? "—" : `${signed(a.profit_all_abs, 2)} ${stake}`}
          tone={a.profit_all_abs ?? 0}
          sub={a.profit_all_ratio === null ? undefined : pct(a.profit_all_ratio)}
        />
        <Metric
          label="Beneficio cerrado"
          value={a.profit_closed_abs === null ? "—" : `${signed(a.profit_closed_abs, 2)} ${stake}`}
          tone={a.profit_closed_abs ?? 0}
          sub={a.profit_closed_ratio === null ? undefined : pct(a.profit_closed_ratio)}
        />
        <Metric
          label="Winrate"
          value={a.winrate === null ? "—" : pct(a.winrate)}
          sub={`${a.winning_trades ?? 0}W / ${a.losing_trades ?? 0}L`}
        />
        <Metric
          label="Trades"
          value={a.closed_trade_count ?? "—"}
          sub={`${a.trade_count ?? 0} en total`}
        />
        <Metric label="Profit factor" {...profitFactor(a)} />
        <Metric
          label="Expectancy"
          value={fmt(a.expectancy, 4)}
          sub={a.expectancy_ratio === null ? undefined : `ratio ${fmt(a.expectancy_ratio, 2)}`}
        />
        <Metric
          label="Drawdown máx."
          value={a.max_drawdown === null ? "—" : pct(a.max_drawdown)}
          sub={a.max_drawdown_abs === null ? undefined : `${fmt(a.max_drawdown_abs, 2)} ${stake}`}
        />
        <Metric
          label="Drawdown actual"
          value={a.current_drawdown === null ? "—" : pct(a.current_drawdown)}
        />
        <Metric label="Sharpe" value={fmt(a.sharpe, 2)} />
        <Metric label="Sortino" value={fmt(a.sortino, 2)} />
        <Metric label="Calmar" value={fmt(a.calmar, 2)} />
        <Metric label="SQN" value={fmt(a.sqn, 2)} />
        <Metric label="Duración media" value={a.avg_duration ?? "—"} />
        <Metric
          label="Mejor par"
          value={a.best_pair || "—"}
          sub={a.best_pair ? pct(a.best_pair_profit_ratio) : undefined}
        />
      </div>

      <h3 className="subhead">Montos</h3>
      <div className="grid">
        <Metric label="Balance" value={`${fmt(a.balance_total, 2)} ${stake}`} />
        <Metric label="Balance del bot" value={`${fmt(a.balance_total_bot, 2)} ${stake}`} />
        <Metric
          label="Capital inicial"
          value={`${fmt(a.starting_capital, 2)} ${stake}`}
          sub={a.starting_capital_ratio === null ? undefined : pct(a.starting_capital_ratio)}
        />
        <Metric label="Stake por trade" value={stakeText(a, stake)} />
        <Metric
          label="Capital desplegado"
          value={a.total_stake_deployed === null ? "—" : `${fmt(a.total_stake_deployed, 2)} ${stake}`}
          sub={`${a.open_trades ?? 0} / ${a.max_open_trades} trades abiertos`}
        />
        <Metric label="Volumen operado" value={`${fmt(a.trading_volume, 2)} ${stake}`} />
      </div>

      <h3 className="subhead">Configuración</h3>
      <div className="grid">
        <Metric label="Estrategia" value={a.strategy_label} sub={a.strategy_key} />
        <Metric label="Timeframe" value={a.timeframe} />
        <Metric label="Stoploss" value={pct(a.stoploss)} />
        <Metric
          label="ROI objetivo"
          value={a.roi_table.length ? pct(a.roi_table[0].roi) : "—"}
          sub={`${a.roi_table.length} escalón(es)`}
        />
        <Metric
          label="Lista de pares"
          value={a.pairlist_mode === "volume" ? "Por volumen" : "Fija"}
          sub={a.pairlist_mode === "volume" ? `top ${a.volume_number_assets}` : `${a.pairs.length} pares`}
        />
        <Metric label="Máx. trades" value={a.max_open_trades} />
      </div>

      <h3 className="subhead">Pares operados</h3>
      {pairs.length === 0 ? (
        <p className="muted">Sin pares.</p>
      ) : (
        <div className="row">
          {pairs.map((p) => (
            <span key={p} className="chip chip--plain">
              {p}
            </span>
          ))}
        </div>
      )}

      <h3 className="subhead">Evolución (30 días)</h3>
      <Sparkline values={cumulative(a.daily)} label={`Beneficio acumulado de ${a.username}`} />

      <h3 className="subhead">Rendimiento por par</h3>
      {perf.length === 0 ? (
        <p className="muted">Todavía no hay trades cerrados.</p>
      ) : (
        <table className="responsive-table">
          <thead>
            <tr>
              <th>Par</th>
              <th>Beneficio</th>
              <th>ROI</th>
              <th>Trades</th>
            </tr>
          </thead>
          <tbody>
            {perf.map((e) => (
              <tr key={e.pair} className={(e.profit_abs ?? 0) >= 0 ? "win" : "loss"}>
                <td className="table-primary" data-label="Par">
                  {e.pair}
                </td>
                <td data-label="Beneficio" className={`amt ${toneClass(e.profit_abs)}`}>
                  {signed(e.profit_abs, 2)} {stake}
                </td>
                <td data-label="ROI">
                  <ProfitCell pct={e.profit_ratio === null ? null : e.profit_ratio * 100} />
                </td>
                <td data-label="Trades" className="num">
                  {e.count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/** The trading loop, which is a separate thing from the container being up: a bot can
 *  answer its REST API perfectly while doing nothing. `trading_enabled` is what the
 *  owner asked for, so a stopped bot that should be trading reads as "reanudando" —
 *  the server's reconciler will pick it back up within the minute. */
function TradingBadge({ account: a }: { account: PublicAccount }) {
  if (!a.reachable) return null;
  const state = a.bot_state?.toLowerCase();
  if (state === "running") return <span className="badge running">operando</span>;
  if (state === "paused") return <span className="badge stopped">pausado</span>;
  if (a.trading_enabled) return <span className="badge stopped">reanudando…</span>;
  return <span className="badge provisioned">sin operar</span>;
}

/** Running cumulative profit, oldest day first. Freqtrade returns `/daily` newest-first. */
function cumulative(daily: PublicDailyPoint[]): number[] {
  let total = 0;
  return [...daily]
    .reverse()
    .map((d) => (total += d.abs_profit ?? 0));
}

/** Freqtrade reports an infinite profit factor for a bot that has never lost, which
 *  arrives as null. Distinguish that from "no data yet". */
function profitFactor(a: PublicAccount): { value: string; sub?: string } {
  if (typeof a.profit_factor === "number") return { value: fmt(a.profit_factor, 2) };
  if ((a.closed_trade_count ?? 0) > 0 && a.losing_trades === 0) {
    return { value: "∞", sub: "sin pérdidas aún" };
  }
  return { value: "—" };
}

function stakeText(a: PublicAccount, stake: string): string {
  return typeof a.stake_amount === "number" ? `${fmt(a.stake_amount, 2)} ${stake}` : "Sin límite";
}

/** Map the raw Docker container state onto the badge vocabulary the app already uses. */
function badgeStatus(a: PublicAccount): BotStatus {
  if (a.container_state === "running") return "running";
  if (a.container_state === null) return "error";
  return "stopped";
}

function toneClass(n: number | null): string {
  if (typeof n !== "number" || n === 0) return "";
  return n > 0 ? "pos" : "neg";
}

function rowTone(a: PublicAccount): string {
  if (typeof a.profit_all_abs !== "number" || a.profit_all_abs === 0) return "";
  return a.profit_all_abs > 0 ? "win" : "loss";
}
