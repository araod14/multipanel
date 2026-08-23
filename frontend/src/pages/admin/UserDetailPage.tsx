import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { AxiosError } from "axios";

import { adminApi } from "../../api/admin";
import type { ExchangeCredentialMeta } from "../../api/types";
import { ModeBadge, StatusBadge } from "../../components/StatusBadge";

export function UserDetailPage() {
  const { userId } = useParams();
  const id = Number(userId);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const bot = useQuery({
    queryKey: ["bot", id],
    queryFn: () => adminApi.getBot(id),
    retry: false,
  });
  const exchange = useQuery({
    queryKey: ["exchange", id],
    queryFn: () => adminApi.getExchange(id),
    retry: false,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["bot", id] });
    qc.invalidateQueries({ queryKey: ["exchange", id] });
  };

  const provision = useMutation({ mutationFn: () => adminApi.provision(id), onSuccess: refresh });
  const start = useMutation({ mutationFn: () => adminApi.startBot(id), onSuccess: refresh });
  const stop = useMutation({ mutationFn: () => adminApi.stopBot(id), onSuccess: refresh });
  const rotate = useMutation({ mutationFn: () => adminApi.rotateCredentials(id), onSuccess: refresh });

  const [modeError, setModeError] = useState<string | null>(null);
  const setMode = useMutation({
    mutationFn: (dryRun: boolean) => adminApi.setMode(id, dryRun),
    onSuccess: () => {
      setModeError(null);
      refresh();
    },
    onError: (e: AxiosError<{ detail: string }>) =>
      setModeError(e.response?.data?.detail ?? "Could not change mode"),
  });

  const hasBot = bot.isSuccess;
  const busy =
    provision.isPending || start.isPending || stop.isPending || rotate.isPending || setMode.isPending;

  const goLive = () => {
    const exchangeName = exchange.data?.exchange_name ?? "the exchange";
    const cap = bot.data?.live_max_capital;
    const message =
      `Enable LIVE trading with REAL money?\n\n` +
      `The bot will be recreated and will place real orders on ${exchangeName}.\n` +
      `Total exposure is capped at ${cap} ${bot.data?.stake_currency}; the server refuses ` +
      `settings that would risk more.\n\n` +
      `This cannot be undone for orders already filled.`;
    if (confirm(message)) setMode.mutate(false);
  };

  return (
    <>
      <button className="secondary mb-16" onClick={() => navigate("/admin")}>
        ← Back
      </button>

      <div className="card">
        <h2>Bot — user #{id}</h2>
        {hasBot ? (
          <>
            <div className="row mb-12">
              <StatusBadge status={bot.data.status} />
              <ModeBadge dryRun={bot.data.dry_run} />
              <span className="muted">{bot.data.container_name}</span>
            </div>
            <div className="action-row">
              <button onClick={() => start.mutate()} disabled={busy}>
                Start
              </button>
              <button className="secondary" onClick={() => stop.mutate()} disabled={busy}>
                Stop
              </button>
              <button className="secondary" onClick={() => provision.mutate()} disabled={busy}>
                Re-provision
              </button>
              <button className="secondary" onClick={() => rotate.mutate()} disabled={busy}>
                Rotate credentials
              </button>
            </div>
            <div className="action-row mt-14">
              {bot.data.dry_run ? (
                <button className="danger" onClick={goLive} disabled={busy}>
                  Go LIVE
                </button>
              ) : (
                <button className="secondary" onClick={() => setMode.mutate(true)} disabled={busy}>
                  Back to dry-run
                </button>
              )}
            </div>
            {modeError && <div className="error">{modeError}</div>}
          </>
        ) : (
          <>
            <p className="muted">No bot provisioned yet.</p>
            <button onClick={() => provision.mutate()} disabled={provision.isPending}>
              Provision bot
            </button>
          </>
        )}
      </div>

      <ExchangeCard
        userId={id}
        meta={exchange.data}
        onChanged={refresh}
        loading={exchange.isLoading}
      />
    </>
  );
}

function ExchangeCard({
  userId,
  meta,
  onChanged,
  loading,
}: {
  userId: number;
  meta: ExchangeCredentialMeta | undefined;
  onChanged: () => void;
  loading: boolean;
}) {
  // Fetched rather than hardcoded: a literal here would silently drift from the
  // backend allowlist and 422 on every save.
  const exchanges = useQuery({ queryKey: ["exchanges"], queryFn: adminApi.listExchanges });
  const [exchangeName, setExchangeName] = useState("");
  const [key, setKey] = useState("");
  const [secret, setSecret] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [probed, setProbed] = useState<ExchangeCredentialMeta | null>(null);

  const selected = exchangeName || exchanges.data?.supported[0] || "";

  const save = useMutation({
    mutationFn: (force: boolean) =>
      adminApi.setExchange(userId, { exchange_name: selected, key, secret }, force),
    onSuccess: (result) => {
      setSaveError(null);
      setProbed(result);
      setKey("");
      setSecret("");
      onChanged();
    },
    onError: (e: AxiosError<{ detail: string }>) => {
      const detail = e.response?.data?.detail ?? "Could not save credentials";
      // 503 means we could not reach the exchange, which says nothing about the key —
      // offer to store it unverified. A 422 is the exchange itself saying no: never offer.
      if (e.response?.status === 503 && confirm(`${detail}\n\nStore it without verifying?`)) {
        save.mutate(true);
        return;
      }
      setSaveError(detail);
    },
  });
  const remove = useMutation({
    mutationFn: () => adminApi.deleteExchange(userId),
    onSuccess: () => {
      setProbed(null);
      onChanged();
    },
  });

  return (
    <div className="card">
      <h2>Exchange credentials</h2>
      {loading ? (
        <p className="muted">Loading…</p>
      ) : meta ? (
        <p className="muted">
          {meta.exchange_name} — key {meta.key_masked} (updated{" "}
          {new Date(meta.updated_at).toLocaleString()})
        </p>
      ) : (
        <p className="muted">No credentials set. The bot can only run in dry-run.</p>
      )}

      {probed && (
        <>
          <p className="muted">
            {probed.verified
              ? `Verified — ${probed.balance ?? 0} USDT available on the exchange.`
              : "Stored without verification."}
          </p>
          {probed.can_withdraw && (
            <div className="error">
              This API key has withdrawals enabled. A trading bot never needs that — consider
              re-creating it with Spot Trading only.
            </div>
          )}
        </>
      )}

      <div className="form-grid exchange-form">
        <div className="field">
          <label>Exchange</label>
          <select value={selected} onChange={(e) => setExchangeName(e.target.value)}>
            {(exchanges.data?.supported ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>API key</label>
          <input value={key} onChange={(e) => setKey(e.target.value)} />
        </div>
        <div className="field">
          <label>API secret</label>
          <input type="password" value={secret} onChange={(e) => setSecret(e.target.value)} />
        </div>
        <div className="field-action mt-12">
          <button
            onClick={() => save.mutate(false)}
            disabled={!key || !secret || !selected || save.isPending}
          >
            {save.isPending ? "Verifying…" : "Save & inject"}
          </button>
        </div>
      </div>
      <p className="muted">
        Use an HMAC-SHA256 key with Spot Trading enabled and withdrawals disabled. The key is
        verified against the exchange before it is stored.
      </p>
      {saveError && <div className="error">{saveError}</div>}
      {meta && (
        <button
          className="danger mt-12 mobile-full-button"
          onClick={() => {
            if (
              confirm(
                "Delete exchange credentials?\n\nThe bot will be forced back to dry-run and " +
                  "restarted immediately. Any open live positions are left on the exchange.",
              )
            )
              remove.mutate();
          }}
        >
          Delete credentials
        </button>
      )}
    </div>
  );
}
