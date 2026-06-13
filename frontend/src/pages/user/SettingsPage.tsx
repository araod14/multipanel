import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";

import { userApi } from "../../api/user";
import type { BotConfig, BotConfigInput } from "../../api/types";

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
  const [pairs, setPairs] = useState(data.pairs.join(", "));
  const [stakeCurrency, setStakeCurrency] = useState(data.stake_currency);
  const [stakeAmount, setStakeAmount] = useState(String(data.stake_amount));
  const [maxOpen, setMaxOpen] = useState(String(data.max_open_trades));
  const [stoploss, setStoploss] = useState(String(data.stoploss));
  const [roi, setRoi] = useState(String(data.roi));
  const [timeframe, setTimeframe] = useState(data.timeframe);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Keep the form in sync if the server data changes after a save.
  useEffect(() => {
    setStrategy(data.strategy);
    setPairs(data.pairs.join(", "));
    setStakeCurrency(data.stake_currency);
    setStakeAmount(String(data.stake_amount));
    setMaxOpen(String(data.max_open_trades));
    setStoploss(String(data.stoploss));
    setRoi(String(data.roi));
    setTimeframe(data.timeframe);
  }, [data]);

  const save = useMutation({
    mutationFn: () => {
      const body: BotConfigInput = {
        strategy,
        pairs: pairs
          .split(",")
          .map((p) => p.trim())
          .filter(Boolean),
        stake_currency: stakeCurrency.toUpperCase(),
        stake_amount: stakeAmount === "unlimited" ? "unlimited" : Number(stakeAmount),
        max_open_trades: Number(maxOpen),
        stoploss: Number(stoploss),
        roi: Number(roi),
        timeframe,
      };
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

  return (
    <div className="card" style={{ maxWidth: 640 }}>
      <h2>Bot settings</h2>
      <p className="muted">
        Saving applies your settings and restarts the bot. Live trading uses these too —
        review carefully.
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

      <label>Pairs (comma-separated)</label>
      <input value={pairs} onChange={(e) => setPairs(e.target.value)} placeholder="BTC/USDT, ETH/USDT" />

      <div className="row">
        <div style={{ flex: 1 }}>
          <label>Stake currency</label>
          <input value={stakeCurrency} onChange={(e) => setStakeCurrency(e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label>Stake amount ("unlimited" or number)</label>
          <input value={stakeAmount} onChange={(e) => setStakeAmount(e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
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

      <div className="row">
        <div style={{ flex: 1 }}>
          <label>Stoploss (e.g. -0.10)</label>
          <input type="number" step="0.01" value={stoploss} onChange={(e) => setStoploss(e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label>Take-profit ROI (e.g. 0.10)</label>
          <input type="number" step="0.01" value={roi} onChange={(e) => setRoi(e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label>Timeframe</label>
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
            {data.available_timeframes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <button onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? "Saving & restarting…" : "Save settings"}
        </button>
      </div>
      {error && <div className="error">{error}</div>}
      {saved && !error && <p className="muted">Saved. Bot restarted with the new settings.</p>}
    </div>
  );
}
