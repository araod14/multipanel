import { PageHeading } from "../../components/PageHeading";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";

import { userApi } from "../../api/user";
import type { BotConfig, BotConfigInput, PairlistMode, RoiStep } from "../../api/types";
import { ModeBadge } from "../../components/StatusBadge";

export function SettingsPage() {
  const qc = useQueryClient();
  const cfg = useQuery({ queryKey: ["me-config"], queryFn: userApi.getConfig, retry: false });

  if (cfg.isLoading) return <div className="card">Cargando…</div>;
  if (cfg.isError)
    return <div className="card error">Tu cuenta todavía no tiene un bot aprovisionado.</div>;

  return <>
    <PageHeading title="Ajustes" description="Configura la estrategia, el capital y los límites de tu bot." />
    <SettingsForm data={cfg.data!} onSaved={() => qc.invalidateQueries()} />
  </>;
}

function SettingsForm({ data, onSaved }: { data: BotConfig; onSaved: () => void }) {
  const [guardEnabled, setGuardEnabled] = useState(data.tradingview_guard_enabled);
  const [strategy, setStrategy] = useState(data.strategy);
  const [pairlistMode, setPairlistMode] = useState<PairlistMode>(data.pairlist_mode);
  const [pairs, setPairs] = useState<string[]>(data.pairs);
  const [volumeN, setVolumeN] = useState(String(data.volume_number_assets));
  const [stakeAmount, setStakeAmount] = useState(String(data.stake_amount));
  const [maxOpen, setMaxOpen] = useState(String(data.max_open_trades));
  const [stoploss, setStoploss] = useState(String(data.stoploss));
  const [roiTable, setRoiTable] = useState<RoiStep[]>(data.roi_table);
  const [timeframe, setTimeframe] = useState(data.timeframe);
  const [trailingStop, setTrailingStop] = useState(data.trailing_stop);
  const [trailingPos, setTrailingPos] = useState(
    data.trailing_stop_positive === null ? "" : String(data.trailing_stop_positive),
  );
  const [trailingOffset, setTrailingOffset] = useState(String(data.trailing_stop_positive_offset));
  const [dryRunWallet, setDryRunWallet] = useState(String(data.dry_run_wallet));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Keep the form in sync if the server data changes after a save.
  useEffect(() => {
    setGuardEnabled(data.tradingview_guard_enabled);
    setStrategy(data.strategy);
    setPairlistMode(data.pairlist_mode);
    setPairs(data.pairs);
    setVolumeN(String(data.volume_number_assets));
    setStakeAmount(String(data.stake_amount));
    setMaxOpen(String(data.max_open_trades));
    setStoploss(String(data.stoploss));
    setRoiTable(data.roi_table);
    setTimeframe(data.timeframe);
    setTrailingStop(data.trailing_stop);
    setTrailingPos(
      data.trailing_stop_positive === null ? "" : String(data.trailing_stop_positive),
    );
    setTrailingOffset(String(data.trailing_stop_positive_offset));
    setDryRunWallet(String(data.dry_run_wallet));
  }, [data]);

  // --- pairs (always BASE/USDT), chosen from a dropdown of base coins ---
  function addCoin(coin: string) {
    if (!coin) return;
    const pair = `${coin}/USDT`;
    if (!pairs.includes(pair)) setPairs([...pairs, pair]);
  }
  function removePair(pair: string) {
    setPairs(pairs.filter((p) => p !== pair));
  }
  // Coins not yet added (compare against the BASE part of each selected pair).
  const selectedCoins = new Set(pairs.map((p) => p.split("/")[0]));
  const availableCoins = data.available_base_coins.filter((c) => !selectedCoins.has(c));

  // --- ROI table ---
  function setRoiStep(i: number, patch: Partial<RoiStep>) {
    setRoiTable(roiTable.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  }
  function addRoiStep() {
    const lastMin = roiTable.length ? Math.max(...roiTable.map((s) => s.minutes)) : 0;
    setRoiTable([...roiTable, { minutes: lastMin + 30, roi: 0.05 }]);
  }
  function removeRoiStep(i: number) {
    setRoiTable(roiTable.filter((_, idx) => idx !== i));
  }

  function settingsPayload(): BotConfigInput {
    const body: BotConfigInput = {
      tradingview_guard_enabled: guardEnabled,
      strategy,
      pairlist_mode: pairlistMode,
      max_open_trades: Number(maxOpen),
      stake_amount: stakeAmount === "unlimited" ? "unlimited" : Number(stakeAmount),
      stoploss: Number(stoploss),
      roi_table: roiTable.map((s) => ({ minutes: Number(s.minutes), roi: Number(s.roi) })),
      timeframe,
      trailing_stop: trailingStop,
      trailing_stop_positive: trailingPos === "" ? null : Number(trailingPos),
      trailing_stop_positive_offset: Number(trailingOffset),
      dry_run_wallet: Number(dryRunWallet),
    };
    if (pairlistMode === "volume") body.volume_number_assets = Number(volumeN);
    else body.pairs = pairs;
    return body;
  }

  const save = useMutation({
    mutationFn: () => userApi.saveConfig(settingsPayload()),
    onSuccess: () => {
      setError(null);
      setSaved(true);
      onSaved();
    },
    onError: (e: AxiosError<{ detail: string }>) => {
      setSaved(false);
      setError(e.response?.data?.detail ?? "No se pudieron guardar los ajustes");
    },
  });

  const isLive = !data.dry_run;
  // Mirrors the server rule (stake x max open trades <= live_max_capital) so you learn you
  // are over the limit while typing, not after a round-trip. The server stays authoritative.
  const exposure =
    stakeAmount === "unlimited" ? null : Number(stakeAmount) * Number(maxOpen) || 0;
  const overCap = isLive && exposure !== null && exposure > data.live_max_capital;

  const onSave = () => {
    const runtimeChanged = Object.entries(settingsPayload()).some(([key, value]) =>
      key !== "tradingview_guard_enabled" && JSON.stringify(value) !== JSON.stringify(data[key as keyof BotConfig]),
    );
    if (
      isLive && runtimeChanged &&
      !confirm(
        `¿Guardar y reiniciar el bot con dinero REAL?\n\n` +
        `Exposición: ${exposure ?? "?"} ${data.stake_currency} ` +
        `(${stakeAmount} x ${maxOpen} operaciones), límite ${data.live_max_capital}.\n` +
        `Pares: ${pairlistMode === "static" ? pairs.join(", ") : `top ${volumeN} por volumen`}.`,
      )
    )
      return;
    save.mutate();
  };

  return (
    <div className="card settings-card">
      <h2>Ajustes del bot</h2>
      {isLive && (
        <div className="row mb-8">
          <ModeBadge dryRun={false} />
          <span>
            Este bot opera con dinero REAL. Cambiar la estrategia o sus parámetros lo reinicia. La exposición máxima es {data.live_max_capital} {data.stake_currency}.
          </span>
        </div>
      )}
      <p className="muted">
        Cambiar parámetros de trading reinicia el bot. Todos los pares cotizan en USDT.
      </p>

      <fieldset className="form-section"><legend>Protección TradingView</legend>
        <label className="checkbox-label">
          <input type="checkbox" className="checkbox-input" checked={guardEnabled}
            onChange={(e) => setGuardEnabled(e.target.checked)} />
          Protección TradingView: {guardEnabled ? "activa" : "inactiva"}
        </label>
        <p className="muted">Cada minuto se evalúa la lista activa en el exchange y timeframe del bot.
          Si todos los pares están en venta, se pausan nuevas compras y se mantienen las salidas.
          Las compras se reanudan cuando más de la mitad está en compra.
          Sin datos completos se conserva el estado. Cambiar solo esta protección no reinicia el bot.</p>
      </fieldset>
      <fieldset className="form-section"><legend>Estrategia y timeframe</legend>
        <label htmlFor="settingspage-field-1">Estrategia</label>
        <select id="settingspage-field-1" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
          {data.available_strategies.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
        {(() => {
          const selected = data.available_strategies.find((s) => s.key === strategy);
          return selected ? <p className="muted">{selected.description}</p> : null;
        })()}

        <div className="field">
          <label htmlFor="settingspage-field-2">Timeframe</label>
          <select id="settingspage-field-2" value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
            {data.available_timeframes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </fieldset>
      <fieldset className="form-section"><legend>Pares de trading</legend>
        <label htmlFor="settingspage-field-3">Selección de pares</label>
        <select id="settingspage-field-3"
          value={pairlistMode}
          onChange={(e) => setPairlistMode(e.target.value as PairlistMode)}
        >
          <option value="static">Lista manual</option>
          <option value="volume">Automática · mayor volumen</option>
        </select>

        {pairlistMode === "static" ? (
          <>
            <label htmlFor="settingspage-field-4">Pares (elige una moneda · cotización USDT)</label>
            <select id="settingspage-field-4"
              value=""
              onChange={(e) => {
                addCoin(e.target.value);
                e.target.value = "";
              }}
              disabled={availableCoins.length === 0}
              className="mb-8"
            >
              <option value="" disabled>
                {availableCoins.length === 0 ? "Todas las monedas añadidas" : "Añadir moneda…"}
              </option>
              {availableCoins.map((c) => (
                <option key={c} value={c}>
                  {c}/USDT
                </option>
              ))}
            </select>
            <div className="row">
              {pairs.length === 0 && <span className="muted">Todavía no has añadido pares.</span>}
              {pairs.map((p) => (
                <span key={p} className="chip">
                  {p}
                  <button type="button" aria-label={`Quitar ${p}`} onClick={() => removePair(p)}>
                    ×
                  </button>
                </span>
              ))}
            </div>
          </>
        ) : (
          <>
            <label htmlFor="settingspage-field-5">Cantidad de pares por volumen de 24 h</label>
            <input id="settingspage-field-5"
              type="number"
              min={1}
              max={100}
              value={volumeN}
              onChange={(e) => setVolumeN(e.target.value)}
            />
            <p className="muted">
              El bot selecciona los {volumeN || "N"} pares USDT con mayor volumen y actualiza
              la lista periódicamente.
            </p>
          </>
        )}

      </fieldset>
      <fieldset className="form-section"><legend>Capital y exposición</legend>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="settingspage-field-6">Moneda de inversión</label>
            <input id="settingspage-field-6" value="USDT" disabled />
          </div>
          <div className="field">
            <label htmlFor="settingspage-field-7">
              {isLive
                ? `Importe por operación (${data.live_min_stake}–${data.live_max_capital})`
                : 'Importe por operación ("unlimited" o número)'}
            </label>
            <input id="settingspage-field-7" value={stakeAmount} onChange={(e) => setStakeAmount(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="settingspage-field-8">Máximo de operaciones abiertas</label>
            <input id="settingspage-field-8"
              type="number"
              value={maxOpen}
              onChange={(e) => setMaxOpen(e.target.value)}
              min={1}
              max={50}
            />
          </div>
        </div>

        <div className="form-grid">
          <div className="field">
            <label htmlFor="settingspage-field-9">Capital de simulación</label>
            <input id="settingspage-field-9"
              type="number"
              step="1"
              min={0}
              value={dryRunWallet}
              onChange={(e) => setDryRunWallet(e.target.value)}
              disabled={isLive}
            />
            {isLive && <p className="muted">No se usa en modo real: el exchange informa tu balance.</p>}
          </div>
        </div>
        {isLive && exposure !== null && (
          <p className={overCap ? "error" : "muted"}>
            Exposición total: {exposure} {data.stake_currency} ({stakeAmount} x {maxOpen} operaciones) —
            límite {data.live_max_capital}.
          </p>
        )}

      </fieldset>
      <fieldset className="form-section"><legend>Riesgo y objetivos</legend>
        <div className="field">
          <label htmlFor="settingspage-field-10">Stoploss (p. ej. -0.10)</label>
          <input id="settingspage-field-10" type="number" step="0.01" value={stoploss} onChange={(e) => setStoploss(e.target.value)} />
        </div>
        <h3 className="subhead">Objetivos de beneficio (ROI)</h3>
        <p className="muted">
          Objetivo de beneficio {`{ROI}`} tras {`{minutos}`} minutos. El escalón de 0 minutos es
          el objetivo inicial; los siguientes lo ajustan con el tiempo.
        </p>
        {roiTable.map((step, i) => (
          <div className="row roi-row" key={i}>
            <div className="field">
              <input
                type="number"
                min={0}
                step="1"
                value={String(step.minutes)}
                onChange={(e) => setRoiStep(i, { minutes: Number(e.target.value) })}
                placeholder="minutos"
                aria-label={`Minutos del escalón ${i + 1}`}
              />
            </div>
            <div className="field">
              <input
                type="number"
                step="0.01"
                value={String(step.roi)}
                onChange={(e) => setRoiStep(i, { roi: Number(e.target.value) })}
                placeholder="ROI (p. ej. 0.10)"
                aria-label={`ROI del escalón ${i + 1}`}
              />
            </div>
            <button
              className="secondary"
              type="button"
              onClick={() => removeRoiStep(i)}
              disabled={roiTable.length <= 1}
              aria-label={`Quitar escalón ${i + 1}`}
            >
              Quitar
            </button>
          </div>
        ))}
        <button type="button" onClick={addRoiStep}>
          Añadir escalón ROI
        </button>

        <label className="checkbox-label mt-12">
          <input
            type="checkbox"
            checked={trailingStop}
            onChange={(e) => setTrailingStop(e.target.checked)}
            className="checkbox-input"
          />
          Activar trailing stop
        </label>
        {trailingStop && (
          <div className="form-grid form-grid--two">
            <div className="field">
              <label htmlFor="settingspage-field-11">Trailing positivo (opcional, p. ej. 0.01)</label>
              <input id="settingspage-field-11"
                type="number"
                step="0.01"
                value={trailingPos}
                onChange={(e) => setTrailingPos(e.target.value)}
                placeholder="Vacío para usar el stoploss"
              />
            </div>
            <div className="field">
              <label htmlFor="settingspage-field-12">Offset del trailing (mayor que el positivo)</label>
              <input id="settingspage-field-12"
                type="number"
                step="0.01"
                value={trailingOffset}
                onChange={(e) => setTrailingOffset(e.target.value)}
              />
            </div>
          </div>
        )}

      </fieldset>
      <div className="mt-16">
        <button className={isLive ? "danger" : undefined} onClick={onSave} disabled={save.isPending}>
          {save.isPending ? "Guardando…" : "Guardar ajustes"}
        </button>
      </div>
      {error && <div className="error">{error}</div>}
      {saved && !error && <p className="muted">Ajustes guardados.</p>}
    </div>
  );
}
