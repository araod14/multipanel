import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";

import { userApi } from "../../api/user";
import type { BotConfig, BotConfigInput, PairlistMode, RoiStep } from "../../api/types";
import { ModeBadge } from "../../components/StatusBadge";

export function SettingsPage() {
  const qc = useQueryClient();
  const cfg = useQuery({ queryKey: ["me-config"], queryFn: userApi.getConfig, retry: false });

  if (cfg.isLoading) return <div className="card">Loading…</div>;
  if (cfg.isError)
    return <div className="card error">No bot is provisioned for your account yet.</div>;

  return <SettingsForm data={cfg.data!} onSaved={() => qc.invalidateQueries()} />;
}

function SettingsForm({ data, onSaved }: { data: BotConfig; onSaved: () => void }) {
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

  const save = useMutation({
    mutationFn: () => {
      const body: BotConfigInput = {
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
      return userApi.saveConfig(body);
    },
    onSuccess: () => {
      setError(null);
      setSaved(true);
      onSaved();
    },
    onError: (e: AxiosError<{ detail: string }>) => {
      setSaved(false);
      setError(e.response?.data?.detail ?? "Could not save settings");
    },
  });

  const isLive = !data.dry_run;
  // Mirrors the server rule (stake x max open trades <= live_max_capital) so you learn you
  // are over the limit while typing, not after a round-trip. The server stays authoritative.
  const exposure =
    stakeAmount === "unlimited" ? null : Number(stakeAmount) * Number(maxOpen) || 0;
  const overCap = isLive && exposure !== null && exposure > data.live_max_capital;

  const onSave = () => {
    if (
      isLive &&
      !confirm(
        `Save and restart the bot with REAL money?\n\n` +
          `Exposure: ${exposure ?? "?"} ${data.stake_currency} ` +
          `(${stakeAmount} x ${maxOpen} trades), limit ${data.live_max_capital}.\n` +
          `Pairs: ${pairlistMode === "static" ? pairs.join(", ") : `top ${volumeN} by volume`}.`,
      )
    )
      return;
    save.mutate();
  };

  return (
    <div className="card settings-card">
      <h2>Bot settings</h2>
      {isLive && (
        <div className="row mb-8">
          <ModeBadge dryRun={false} />
          <span>
            This bot trades REAL money. Saving restarts it immediately. Total exposure is
            capped at {data.live_max_capital} {data.stake_currency}.
          </span>
        </div>
      )}
      <p className="muted">
        Saving applies your settings and restarts the bot. All pairs are quoted in USDT.
      </p>

      <label>Strategy</label>
      <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
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

      <label>Pair selection</label>
      <select
        value={pairlistMode}
        onChange={(e) => setPairlistMode(e.target.value as PairlistMode)}
      >
        <option value="static">Manual list</option>
        <option value="volume">Automatic — top by volume</option>
      </select>

      {pairlistMode === "static" ? (
        <>
          <label>Pairs (choose a coin — quoted in USDT)</label>
          <select
            value=""
            onChange={(e) => {
              addCoin(e.target.value);
              e.target.value = "";
            }}
            disabled={availableCoins.length === 0}
            className="mb-8"
          >
            <option value="" disabled>
              {availableCoins.length === 0 ? "All coins added" : "Add a coin…"}
            </option>
            {availableCoins.map((c) => (
              <option key={c} value={c}>
                {c}/USDT
              </option>
            ))}
          </select>
          <div className="row">
            {pairs.length === 0 && <span className="muted">No pairs added yet.</span>}
            {pairs.map((p) => (
              <span key={p} className="chip">
                {p}
                <button type="button" aria-label={`Remove ${p}`} onClick={() => removePair(p)}>
                  ×
                </button>
              </span>
            ))}
          </div>
        </>
      ) : (
        <>
          <label>Top N pairs by 24h volume</label>
          <input
            type="number"
            min={1}
            max={100}
            value={volumeN}
            onChange={(e) => setVolumeN(e.target.value)}
          />
          <p className="muted">
            The bot auto-selects the {volumeN || "N"} highest-volume USDT pairs and refreshes
            the list periodically.
          </p>
        </>
      )}

      <div className="form-grid">
        <div className="field">
          <label>Stake currency</label>
          <input value="USDT" disabled />
        </div>
        <div className="field">
          <label>
            {isLive
              ? `Stake amount (${data.live_min_stake}–${data.live_max_capital} per trade)`
              : 'Stake amount ("unlimited" or number)'}
          </label>
          <input value={stakeAmount} onChange={(e) => setStakeAmount(e.target.value)} />
        </div>
        <div className="field">
          <label>Max open trades</label>
          <input
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
          <label>Stoploss (e.g. -0.10)</label>
          <input type="number" step="0.01" value={stoploss} onChange={(e) => setStoploss(e.target.value)} />
        </div>
        <div className="field">
          <label>Timeframe</label>
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
            {data.available_timeframes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Dry-run wallet</label>
          <input
            type="number"
            step="1"
            min={0}
            value={dryRunWallet}
            onChange={(e) => setDryRunWallet(e.target.value)}
            disabled={isLive}
          />
          {isLive && <p className="muted">Ignored in live — the exchange reports your real balance.</p>}
        </div>
      </div>
      {isLive && exposure !== null && (
        <p className={overCap ? "error" : "muted"}>
          Total exposure: {exposure} {data.stake_currency} ({stakeAmount} x {maxOpen} trades) —
          limit {data.live_max_capital}.
        </p>
      )}

      <label className="mt-12">Take-profit ROI table</label>
      <p className="muted">
        Take {`{ROI}`} profit after {`{minutes}`} minutes. The step at 0 minutes is the
        initial target; later steps lower the bar over time.
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
              placeholder="minutes"
            />
          </div>
          <div className="field">
            <input
              type="number"
              step="0.01"
              value={String(step.roi)}
              onChange={(e) => setRoiStep(i, { roi: Number(e.target.value) })}
              placeholder="roi (e.g. 0.10)"
            />
          </div>
          <button
            type="button"
            onClick={() => removeRoiStep(i)}
            disabled={roiTable.length <= 1}
          >
            Remove
          </button>
        </div>
      ))}
      <button type="button" onClick={addRoiStep}>
        Add ROI step
      </button>

      <label className="checkbox-label mt-12">
        <input
          type="checkbox"
          checked={trailingStop}
          onChange={(e) => setTrailingStop(e.target.checked)}
          className="checkbox-input"
        />
        Enable trailing stop
      </label>
      {trailingStop && (
        <div className="form-grid form-grid--two">
          <div className="field">
            <label>Trailing positive (optional, e.g. 0.01)</label>
            <input
              type="number"
              step="0.01"
              value={trailingPos}
              onChange={(e) => setTrailingPos(e.target.value)}
              placeholder="leave empty to trail from stoploss"
            />
          </div>
          <div className="field">
            <label>Trailing offset (must exceed positive)</label>
            <input
              type="number"
              step="0.01"
              value={trailingOffset}
              onChange={(e) => setTrailingOffset(e.target.value)}
            />
          </div>
        </div>
      )}

      <div className="mt-16">
        <button className={isLive ? "danger" : undefined} onClick={onSave} disabled={save.isPending}>
          {save.isPending ? "Saving & restarting…" : "Save settings"}
        </button>
      </div>
      {error && <div className="error">{error}</div>}
      {saved && !error && <p className="muted">Saved. Bot restarted with the new settings.</p>}
    </div>
  );
}
