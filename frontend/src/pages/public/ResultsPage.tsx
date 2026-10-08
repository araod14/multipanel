import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { publicApi } from "../../api/public";
import type { BotStatus, PublicAccount, PublicDailyPoint, PublicResults } from "../../api/types";
import { BrandMark } from "../../components/BrandMark";
import { Metric } from "../../components/Metric";
import { ProfitCell } from "../../components/ProfitCell";
import { Sparkline } from "../../components/Sparkline";
import { ModeBadge, StatusBadge, TradingViewGuardStatus } from "../../components/StatusBadge";
import TechnicalPanel from "../../components/TechnicalPanel";
import { fmt, pct, signed } from "../../lib/format";
import { filterAccounts, type AccountMode, type AccountOrder } from "../../lib/results";

export function ResultsPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<AccountMode>("all");
  const [order, setOrder] = useState<AccountOrder>("name");
  const results = useQuery({
    queryKey: ["public-results"],
    queryFn: publicApi.results,
    retry: false,
    refetchInterval: 30000,
  });
  const data = results.data;
  const stake = data?.stake_currency ?? "USDT";
  const accounts = data?.accounts ?? [];
  const visible = filterAccounts(accounts, search, mode, order);
  const toggle = (username: string) => setSelected(selected === username ? null : username);

  return (
    <div className="public-shell">
      <header className="public-header">
        <Link className="brand" to="/results" aria-label="Control Plane · Resultados">
          <BrandMark />
          <div><strong>Control Plane</strong><span>Monitor de trading</span></div>
        </Link>
        <Link className="public-login" to="/login">
          Entrar <span aria-hidden="true">↗</span>
        </Link>
      </header>
      <main className="content results-content" id="main-content" tabIndex={-1}>
        <div className="page-heading">
          <div>
            <span className="eyebrow">VISTA GENERAL</span>
            <h1>Resultados</h1>
            <p className="muted">Tus cuentas, de un vistazo.</p>
          </div>
          <div className="refresh-controls">
            <span className="muted">
              {data
                ? `Datos de ${new Date(data.generated_at).toLocaleTimeString("es", {
                  hour: "2-digit", minute: "2-digit", second: "2-digit",
                })}`
                : "Actualización cada 30 s"}
            </span>
            <button className="secondary" onClick={() => void results.refetch()} disabled={results.isFetching}>
              {results.isFetching ? "Actualizando…" : "Actualizar"}
            </button>
          </div>
        </div>
        {results.isError && (
          <div className="notice notice--error" role="alert">
            <p>{data
              ? "No se pudo actualizar. Se muestran los últimos datos disponibles."
              : "No se pudieron cargar los resultados."}</p>
            <button className="secondary" onClick={() => void results.refetch()} disabled={results.isFetching}>
              Reintentar
            </button>
          </div>
        )}
        {!data && results.isLoading && (
          <div className="loading-state" role="status"><span className="loading-dot" />Cargando resultados…</div>
        )}
        {data && (
          <>
            <ResultsSummary data={data} stake={stake} />
            <section className="accounts-section" aria-labelledby="accounts-title">
              <div className="section-heading">
                <h2 id="accounts-title">Cuentas</h2>
                <span className="muted" role="status">{visible.length} de {accounts.length}</span>
              </div>
              <div className="accounts-toolbar">
                <div className="search-field">
                  <label htmlFor="account-search">Buscar cuenta</label>
                  <input id="account-search" type="search" placeholder="Nombre de la cuenta…"
                    value={search} onChange={(e) => setSearch(e.target.value)} />
                </div>
                <div>
                  <label htmlFor="account-mode">Modo</label>
                  <select id="account-mode" value={mode} onChange={(e) => setMode(e.target.value as AccountMode)}>
                    <option value="all">Todas</option>
                    <option value="live">Real</option>
                    <option value="dry">Simulación</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="account-order">Ordenar por</label>
                  <select id="account-order" value={order} onChange={(e) => setOrder(e.target.value as AccountOrder)}>
                    <option value="name">Nombre · A–Z</option>
                    <option value="profit">Beneficio · mayor primero</option>
                    <option value="roi">ROI · mayor primero</option>
                  </select>
                </div>
              </div>
              {visible.length === 0 ? (
                <div className="empty-state">
                  <h3>{accounts.length === 0 ? "Todavía no hay cuentas" : "Sin coincidencias"}</h3>
                  <p className="muted">{accounts.length === 0
                    ? "Las cuentas aparecerán cuando tengan un bot aprovisionado."
                    : "Prueba otro nombre o cambia el modo."}</p>
                  {accounts.length > 0 && (
                    <button className="secondary" onClick={() => { setSearch(""); setMode("all"); }}>
                      Limpiar filtros
                    </button>
                  )}
                </div>
              ) : (
                <>
                  <div className="mobile-accounts">
                    {visible.map((a) => (
                      <AccountCard key={a.username} account={a} stake={stake}
                        expanded={selected === a.username} onToggle={() => toggle(a.username)} />
                    ))}
                  </div>
                  <div className="desktop-accounts card">
                    <table className="accounts-table">
                      <caption className="sr-only">Comparación de rendimiento de las cuentas</caption>
                      <thead>
                        <tr>
                          <th>Cuenta / estrategia</th><th>Estado</th><th>Beneficio</th>
                          <th>ROI</th><th>Trades</th><th>Winrate</th><th><span className="sr-only">Detalle</span></th>
                        </tr>
                      </thead>
                      <tbody>
                        {visible.map((a) => (
                          <AccountRow key={a.username} account={a} stake={stake}
                            expanded={selected === a.username} onToggle={() => toggle(a.username)} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </section>
            <details className="card market-disclosure disclosure">
              <summary>
                <span>Valoración técnica <span className="muted">TradingView · {data.technical?.length ?? 0} pares</span></span>
              </summary>
              <div className="disclosure-body"><TechnicalPanel technical={data.technical ?? []} /></div>
            </details>
            <footer className="results-footer muted">
              Control Plane <span>Actualización automática cada 30 segundos</span>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}

function ResultsSummary({ data, stake }: { data: PublicResults; stake: string }) {
  const totals = data.totals;
  return (
    <section className="summary-section" aria-labelledby="summary-title">
      <div className="section-heading">
        <h2 id="summary-title">Resumen global</h2>
        <span className="muted">{totals.accounts} cuentas · real y simulación</span>
      </div>
      <div className="grid summary-grid">
        <Metric label="Beneficio total" value={`${signed(totals.profit_all_abs, 2)} ${stake}`}
          tone={totals.profit_all_abs} sub={`${signed(totals.profit_closed_abs, 2)} ${stake} cerrado`} />
        <Metric label="Balance agregado" value={`${fmt(totals.balance_total, 2)} ${stake}`}
          sub={`${totals.live_accounts} real · ${totals.dry_accounts} simulación`} />
        <Metric label="Winrate global" value={pct(totals.winrate)}
          sub={`${totals.winning_trades} ganados / ${totals.losing_trades} perdidos`} />
        <Metric label="Operaciones cerradas" value={totals.closed_trade_count} sub={`${totals.open_trades} abiertas`} />
        <Metric label="Capital desplegado" value={`${fmt(totals.total_stake_deployed, 2)} ${stake}`} />
        <Metric label="Bots disponibles" value={`${totals.reachable} / ${totals.accounts}`} sub={`${totals.running} en marcha`} />
      </div>
    </section>
  );
}

type AccountViewProps = {
  account: PublicAccount;
  stake: string;
  expanded: boolean;
  onToggle: () => void;
};

function AccountCard({ account: a, stake, expanded, onToggle }: AccountViewProps) {
  const target = `mobile-detail-${a.username}`;
  return (
    <article className={`account-card ${rowTone(a)}`}>
      <div className="account-card-heading">
        <div><h3>{a.username}</h3><p className="muted">{a.strategy_label} · {a.timeframe}</p></div>
        <ModeBadge dryRun={a.dry_run} account={a.username} />
      </div>
      <AccountState account={a} />
      <div className="account-figures">
        <div>
          <span className="muted">Beneficio total</span>
          <strong className={`amt ${toneClass(a.profit_all_abs)}`}>
            {a.profit_all_abs === null ? "—" : `${signed(a.profit_all_abs, 2)} ${stake}`}
          </strong>
        </div>
        <div><span className="muted">ROI</span><strong className={`amt ${toneClass(a.profit_all_ratio)}`}>{pct(a.profit_all_ratio)}</strong></div>
      </div>
      <DetailButton account={a} expanded={expanded} onClick={onToggle} target={target} />
      {expanded && <div id={target}><AccountDetail account={a} stake={stake} /></div>}
    </article>
  );
}

function AccountRow({ account: a, stake, expanded, onToggle }: AccountViewProps) {
  const target = `desktop-detail-${a.username}`;
  return (
    <Fragment>
      <tr className={rowTone(a)}>
        <td className="table-primary"><strong>{a.username}</strong><span className="table-subtitle">{a.strategy_label} · {a.timeframe}</span></td>
        <td><AccountState account={a} /><div className="mt-8"><ModeBadge dryRun={a.dry_run} account={a.username} /></div></td>
        <td className={`amt ${toneClass(a.profit_all_abs)}`}>
          {a.profit_all_abs === null ? "—" : `${signed(a.profit_all_abs, 2)} ${stake}`}
        </td>
        <td><ProfitCell pct={a.profit_all_ratio === null ? null : a.profit_all_ratio * 100} /></td>
        <td className="num">{a.closed_trade_count ?? "—"}</td>
        <td className="num">{pct(a.winrate)}</td>
        <td><DetailButton account={a} expanded={expanded} onClick={onToggle} target={target} /></td>
      </tr>
      {expanded && (
        <tr className="detail-row">
          <td colSpan={7}><div id={target}><AccountDetail account={a} stake={stake} /></div></td>
        </tr>
      )}
    </Fragment>
  );
}

function DetailButton({ account, expanded, onClick, target }: {
  account: PublicAccount; expanded: boolean; onClick: () => void; target: string;
}) {
  return (
    <button className="secondary detail-button"
      aria-label={`${expanded ? "Ocultar" : "Ver"} detalle de ${account.username}`}
      aria-expanded={expanded} aria-controls={expanded ? target : undefined} onClick={onClick}>
      {expanded ? "Ocultar detalle" : "Ver detalle"}<span aria-hidden="true">{expanded ? "−" : "+"}</span>
    </button>
  );
}

function AccountState({ account }: { account: PublicAccount }) {
  return (
    <div className="row account-state">
      <StatusBadge status={badgeStatus(account)} />
      <TradingBadge account={account} />
      <TradingViewGuardStatus bot={account} />
      {!account.reachable && <span className="badge error">Sin conexión</span>}
    </div>
  );
}

function AccountDetail({ account: a, stake }: { account: PublicAccount; stake: string }) {
  const pairs = a.whitelist ?? a.pairs;
  const perf = [...a.performance].sort((x, y) => (y.profit_abs ?? 0) - (x.profit_abs ?? 0));

  return (
    <div className="account-detail">
      <div className="row space-between mb-16">
        <h2 className="mb-0">{a.username}</h2>
        <div className="row">
          <StatusBadge status={badgeStatus(a)} />
          <TradingBadge account={a} />
          <TradingViewGuardStatus bot={a} />
          <ModeBadge dryRun={a.dry_run} account={a.username} />
          {a.exchange && <span className="chip chip--plain">{a.exchange}</span>}
        </div>
      </div>

      {!a.reachable && (
        <p className="muted mb-16">
          El bot no está respondiendo ahora mismo — se muestra solo su configuración.
        </p>
      )}

      <h3 className="subhead">Rendimiento</h3>
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
          sub={`${a.winning_trades ?? "—"} ganados / ${a.losing_trades ?? "—"} perdidos`}
        />
        <Metric
          label="Trades"
          value={a.closed_trade_count ?? "—"}
          sub={`${a.trade_count ?? 0} en total`}
        />
      </div>
      <h3 className="subhead">Evolución del beneficio · últimos 30 días</h3>
      <Sparkline values={cumulative(a.daily)} label={`Beneficio acumulado de ${a.username}`} />

      <details className="disclosure">
        <summary>Métricas avanzadas</summary>
        <div className="disclosure-body grid">
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

      </details>
      <details className="disclosure">
        <summary>Capital y montos</summary>
        <div className="disclosure-body grid">
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
            sub={`${a.open_trades ?? "—"} / ${a.max_open_trades} trades abiertos`}
          />
          <Metric label="Volumen operado" value={`${fmt(a.trading_volume, 2)} ${stake}`} />
        </div>

      </details>
      <details className="disclosure">
        <summary>Configuración y pares</summary>
        <div className="disclosure-body">
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

        </div>
      </details>
      <details className="disclosure">
        <summary>Rendimiento por par</summary>
        <div className="disclosure-body">
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
      </details>
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
  if (a.manual_paused || (a.tradingview_guard_enabled && a.tradingview_paused)) return <span className="badge stopped">compras pausadas</span>;
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
