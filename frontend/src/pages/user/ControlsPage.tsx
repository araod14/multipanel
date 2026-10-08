import { PageHeading } from "../../components/PageHeading";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userApi } from "../../api/user";
import { ModeBadge, TradingViewGuardStatus } from "../../components/StatusBadge";

export function ControlsPage() {
  const qc = useQueryClient();
  const [pair, setPair] = useState("");

  // Same query key refreshBot already invalidates, so the badge stays consistent.
  const bot = useQuery({ queryKey: ["me-bot"], queryFn: userApi.myBot, retry: false, refetchInterval: 15000 });
  const isLive = bot.data?.dry_run === false;
  const entriesPaused = bot.data?.manual_paused || (
    bot.data?.tradingview_guard_enabled && bot.data.tradingview_paused
  );

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
        `¿Forzar una compra REAL de ${pair} con dinero real?\n\n` +
        `Se omite la estrategia y se envía la orden inmediatamente.`,
      )
    )
      return;
    forceEnter.mutate();
  };

  return (
    <>
      <PageHeading title="Control" description="Gestiona la operación del bot y consulta sus registros." />
      {isLive && (
        <div className="card">
          <div className="row">
            <ModeBadge dryRun={false} />
            <span>Este bot está operando con dinero real en el exchange.</span>
          </div>
        </div>
      )}

      <div className="card">
        <h2>Operación del bot</h2>
        {bot.data && <div className="row mb-12"><TradingViewGuardStatus bot={bot.data} /></div>}
        {bot.data?.tradingview_guard_enabled && bot.data.tradingview_paused &&
          <p className="muted">Iniciar respetará la pausa de TradingView. Puedes desactivar la protección en Ajustes.</p>}
        <div className="row">
          <button onClick={() => start.mutate()} disabled={start.isPending || stop.isPending}>
            Iniciar
          </button>
          <button className="secondary" onClick={() => stop.mutate()} disabled={start.isPending || stop.isPending}>
            Detener
          </button>
        </div>
        {(start.isError || stop.isError) && <p className="error" role="alert">No se pudo cambiar el estado del bot.</p>}
      </div>

      <div className="card manual-entry-card">
        <h2>Entrada manual</h2>
        <p className="muted">Abre una operación inmediatamente, sin esperar una señal de la estrategia.</p>
        <div className="row mobile-stack">
          <div className="field grow">
            <label htmlFor="controlspage-field-1">Par (p. ej. BTC/USDT)</label>
            <input id="controlspage-field-1" value={pair} onChange={(e) => setPair(e.target.value)} />
          </div>
          <div className="field-action">
            <button className={`mobile-full-button${isLive ? " danger" : ""}`}
              onClick={confirmForceEnter}
              disabled={!pair || forceEnter.isPending || entriesPaused}
            >
              Abrir operación
            </button>
          </div>
        </div>
        {entriesPaused && <p className="muted">Las nuevas compras están pausadas.</p>}
        {forceEnter.isError && <div className="error">No se pudo abrir la operación.</div>}
      </div>

      <div className="card">
        <h2>Registros</h2>
        {logs.isError ? (
          <p className="muted">No disponible.</p>
        ) : (
          <pre className="logs">{logLines || "No hay registros recientes."}</pre>
        )}
      </div>
    </>
  );
}
