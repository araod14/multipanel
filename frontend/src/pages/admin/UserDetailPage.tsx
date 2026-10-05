import { PageHeading } from "../../components/PageHeading";
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
      setModeError(e.response?.data?.detail ?? "No se pudo cambiar el modo"),
  });

  const hasBot = bot.isSuccess;
  const busy =
    provision.isPending || start.isPending || stop.isPending || rotate.isPending || setMode.isPending;

  const goLive = () => {
    const exchangeName = exchange.data?.exchange_name ?? "el exchange";
    const cap = bot.data?.live_max_capital;
    const message =
      `¿Activar el trading con dinero REAL?\n\n` +
      `El bot se recreará y enviará órdenes reales a ${exchangeName}.\n` +
      `La exposición máxima es ${cap} ${bot.data?.stake_currency}; el servidor rechaza ` +
      `ajustes que superen ese límite.\n\n` +
      `Las órdenes ya ejecutadas no se pueden deshacer.`;
    if (confirm(message)) setMode.mutate(false);
  };

  return (
    <>
      <PageHeading title="Gestión de cuenta" description="Estado del bot, modo de operación y credenciales." />
      <button className="secondary mb-16" onClick={() => navigate("/admin")}>
        ← Volver
      </button>

      <div className="card">
        <h2>Bot de la cuenta</h2>
        {hasBot ? (
          <>
            <div className="row mb-12">
              <StatusBadge status={bot.data.status} />
              <ModeBadge dryRun={bot.data.dry_run} />
              <span className="muted">Cuenta #{id}</span>
            </div>
            <div className="action-row">
              <button onClick={() => start.mutate()} disabled={busy}>
                Iniciar
              </button>
              <button className="secondary" onClick={() => stop.mutate()} disabled={busy}>
                Detener
              </button>
              <button className="secondary" onClick={() => provision.mutate()} disabled={busy}>
                Recrear bot
              </button>
              <button className="secondary" onClick={() => rotate.mutate()} disabled={busy}>
                Renovar credenciales
              </button>
            </div>
            <div className="action-row danger-zone">
              {bot.data.dry_run ? (
                <button className="danger" onClick={goLive} disabled={busy}>
                  Activar modo real
                </button>
              ) : (
                <button className="secondary" onClick={() => setMode.mutate(true)} disabled={busy}>
                  Volver a simulación
                </button>
              )}
            </div>
            {modeError && <div className="error">{modeError}</div>}
            {(start.isError || stop.isError || provision.isError || rotate.isError) && <p className="error" role="alert">No se pudo completar la acción del bot.</p>}
          </>
        ) : bot.isLoading ? (
          <p className="muted" role="status">Cargando bot…</p>
        ) : (
          <>
            <p className="muted">Todavía no hay un bot aprovisionado.</p>
            <button onClick={() => provision.mutate()} disabled={provision.isPending}>
              Crear bot
            </button>
            {provision.isError && <p className="error" role="alert">No se pudo crear el bot.</p>}
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
      const detail = e.response?.data?.detail ?? "No se pudieron guardar las credenciales";
      // 503 means we could not reach the exchange, which says nothing about the key —
      // offer to store it unverified. A 422 is the exchange itself saying no: never offer.
      if (e.response?.status === 503 && confirm(`${detail}\n\n¿Guardar sin verificar?`)) {
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
      <h2>Credenciales del exchange</h2>
      {loading ? (
        <p className="muted">Cargando…</p>
      ) : meta ? (
        <p className="muted">
          {meta.exchange_name} — clave {meta.key_masked} (actualizadas{" "}
          {new Date(meta.updated_at).toLocaleString()})
        </p>
      ) : (
        <p className="muted">No hay credenciales. El bot solo puede operar en simulación.</p>
      )}

      {probed && (
        <>
          <p className="muted">
            {probed.verified
              ? `Verificadas — ${probed.balance ?? 0} USDT disponibles en el exchange.`
              : "Guardadas sin verificar."}
          </p>
          {probed.can_withdraw && (
            <div className="error">
              Esta clave API permite retiros. Crea una clave con permisos solo para trading spot.
            </div>
          )}
        </>
      )}

      <div className="form-grid exchange-form">
        <div className="field">
          <label htmlFor="userdetailpage-field-1">Exchange</label>
          <select id="userdetailpage-field-1" value={selected} onChange={(e) => setExchangeName(e.target.value)}>
            {(exchanges.data?.supported ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="userdetailpage-field-2">Clave API</label>
          <input id="userdetailpage-field-2" value={key} onChange={(e) => setKey(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="userdetailpage-field-3">Secreto API</label>
          <input id="userdetailpage-field-3" type="password" value={secret} onChange={(e) => setSecret(e.target.value)} />
        </div>
        <div className="field-action mt-12">
          <button
            onClick={() => save.mutate(false)}
            disabled={!key || !secret || !selected || save.isPending}
          >
            {save.isPending ? "Verificando…" : "Guardar y aplicar"}
          </button>
        </div>
      </div>
      <p className="muted">
        Usa una clave HMAC-SHA256 con trading spot activado y retiros desactivados.
        La clave se verifica con el exchange antes de guardarla.
      </p>
      {saveError && <div className="error">{saveError}</div>}
      {remove.isError && <p className="error" role="alert">No se pudieron eliminar las credenciales.</p>}
      {meta && (
        <button
          className="danger mt-12 mobile-full-button"
          onClick={() => {
            if (
              confirm(
                "¿Eliminar las credenciales del exchange?\n\nEl bot volverá a simulación y " +
                "se reiniciará inmediatamente. Las posiciones reales abiertas permanecerán en el exchange.",
              )
            )
              remove.mutate();
          }}
        >
          Eliminar credenciales
        </button>
      )}
    </div>
  );
}
