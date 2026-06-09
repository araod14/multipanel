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

  return (
    <>
      <button className="secondary" onClick={() => navigate("/admin")} style={{ marginBottom: 16 }}>
        ← Back
      </button>

      <div className="card">
        <h2>Bot — user #{id}</h2>
        {hasBot ? (
          <>
            <div className="row" style={{ marginBottom: 12 }}>
              <StatusBadge status={bot.data.status} />
              <ModeBadge dryRun={bot.data.dry_run} />
              <span className="muted">{bot.data.container_name}</span>
            </div>
            <div className="row">
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
            <div className="row" style={{ marginTop: 14 }}>
              {bot.data.dry_run ? (
                <button
                  className="danger"
                  onClick={() => {
                    if (confirm("Enable LIVE trading with real funds?")) setMode.mutate(false);
                  }}
                  disabled={busy}
                >
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
  const [exchangeName, setExchangeName] = useState("binance");
  const [key, setKey] = useState("");
  const [secret, setSecret] = useState("");

  const save = useMutation({
    mutationFn: () =>
      adminApi.setExchange(userId, { exchange_name: exchangeName, key, secret }),
    onSuccess: () => {
      setKey("");
      setSecret("");
      onChanged();
    },
  });
  const remove = useMutation({
    mutationFn: () => adminApi.deleteExchange(userId),
    onSuccess: onChanged,
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

      <div className="row">
        <div style={{ width: 160 }}>
          <label>Exchange</label>
          <input value={exchangeName} onChange={(e) => setExchangeName(e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label>API key</label>
          <input value={key} onChange={(e) => setKey(e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label>API secret</label>
          <input type="password" value={secret} onChange={(e) => setSecret(e.target.value)} />
        </div>
        <div style={{ alignSelf: "flex-end" }}>
          <button onClick={() => save.mutate()} disabled={!key || !secret || save.isPending}>
            Save & inject
          </button>
        </div>
      </div>
      {meta && (
        <button
          className="danger"
          style={{ marginTop: 12 }}
          onClick={() => {
            if (confirm("Delete exchange credentials?")) remove.mutate();
          }}
        >
          Delete credentials
        </button>
      )}
    </div>
  );
}
