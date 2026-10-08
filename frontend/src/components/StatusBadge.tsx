import type { BotStatus, TradingViewGuardState } from "../api/types";

/**
 * Accounts whose trading-mode badge is suppressed in the user and public views.
 *
 * Presentation only — it changes nothing about how the bot trades. ``BotInstance.dry_run``
 * still decides that, and the admin panel deliberately keeps showing the real mode so an
 * admin is never misled about which bots are on real money.
 */
const MODE_BADGE_HIDDEN = new Set(["alfred"]);

/** Bot containers are named ``cp-bot-<username>`` (see ``provisioning._container_name``). */
export function accountOfContainer(containerName: string): string {
  return containerName.replace(/^cp-bot-/, "");
}

export function StatusBadge({ status }: { status: BotStatus }) {
  const labels: Record<BotStatus, string> = { provisioned: "Preparado", running: "En marcha", stopped: "Detenido", error: "No disponible" };
  return <span className={`badge ${status}`}>{labels[status]}</span>;
}

/**
 * Trading-mode badge. Pass ``account`` in views where the badge may be suppressed;
 * omit it (as the admin panel does) to always render the real mode.
 */
export function ModeBadge({ dryRun, account }: { dryRun: boolean; account?: string }) {
  if (account !== undefined && MODE_BADGE_HIDDEN.has(account)) return null;
  return <span className={`badge ${dryRun ? "dry" : "live"}`}>{dryRun ? "Simulación" : "Real"}</span>;
}

/** Enabled is a configuration indicator, independent of trading/container state. */
export function TradingViewGuardStatus({ bot }: { bot: TradingViewGuardState }) {
  const enabled = bot.tradingview_guard_enabled;
  const evaluation = bot.tradingview_evaluation;
  const automaticPause = enabled && bot.tradingview_paused && bot.trading_enabled && !bot.manual_paused;
  return <>
    <span className={`badge ${enabled ? "running" : "stopped"}`}>
      Protección TradingView: {enabled ? "activa" : "inactiva"}
    </span>
    {automaticPause && <span className="badge stopped">{bot.entry_pause_managed && !bot.entry_pause_pending
      ? "Compras pausadas por TradingView" : "Pausa por TradingView pendiente"}</span>}
    {bot.entry_pause_managed && bot.trading_enabled && !bot.manual_paused && !automaticPause &&
      <span className="badge stopped">Reanudación pendiente</span>}
    {bot.manual_paused && bot.trading_enabled && <span className="badge stopped">Pausa manual</span>}
    {enabled && evaluation && !evaluation.data_complete && <span className="badge error">Sin datos completos</span>}
    {enabled && !evaluation && <span className="muted">Pendiente de evaluación</span>}
    {enabled && evaluation && <span className="muted" title={`Última evaluación: ${new Date(evaluation.checked_at).toLocaleString()}`}>
      {evaluation.exchange} · {evaluation.timeframe} · Compra {evaluation.buy}/{evaluation.total} · Venta {evaluation.sell}/{evaluation.total} · Neutral {evaluation.neutral} · Sin datos {evaluation.missing}
    </span>}
  </>;
}
