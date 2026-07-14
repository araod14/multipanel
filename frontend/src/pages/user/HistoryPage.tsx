import { useQuery } from "@tanstack/react-query";

import { userApi } from "../../api/user";
import type { FtTrade } from "../../api/types";
import { ProfitCell } from "../../components/ProfitCell";
import { price, signed } from "../../lib/format";

export function HistoryPage() {
  const history = useQuery({
    queryKey: ["me-history"],
    queryFn: () => userApi.history(200),
    retry: false,
    refetchInterval: 30000,
  });

  const trades: FtTrade[] = history.data?.trades ?? [];
  const total = history.data?.total_trades ?? trades.length;
  const wins = trades.filter((t) => (t.profit_abs ?? 0) > 0).length;
  const losses = trades.filter((t) => (t.profit_abs ?? 0) < 0).length;

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Historial de trades</h2>
        {!history.isError && trades.length > 0 && (
          <span className="muted">
            {total} cerrados · <span style={{ color: "var(--green)" }}>{wins} ganados</span> ·{" "}
            <span style={{ color: "var(--red)" }}>{losses} perdidos</span>
          </span>
        )}
      </div>

      {history.isLoading ? (
        <p className="muted">Cargando…</p>
      ) : history.isError ? (
        <p className="muted">No disponible (el bot está iniciando o detenido).</p>
      ) : trades.length === 0 ? (
        <p className="muted">Aún no hay trades cerrados.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Par</th>
              <th>Lado</th>
              <th>Entrada</th>
              <th>Salida</th>
              <th>Cierre</th>
              <th>Profit %</th>
              <th>Profit</th>
              <th>Motivo</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => {
              const abs = t.profit_abs ?? 0;
              const cls = abs > 0 ? "win" : abs < 0 ? "loss" : "";
              return (
                <tr key={t.trade_id} className={cls}>
                  <td>{t.pair}</td>
                  <td>
                    <span className={`badge ${t.is_short ? "live" : "dry"}`}>
                      {t.is_short ? "short" : "long"}
                    </span>
                  </td>
                  <td className="num">{price(t.open_rate)}</td>
                  <td className="num">{price(t.close_rate)}</td>
                  <td className="muted">{shortDate(t.close_date)}</td>
                  <td>
                    <ProfitCell
                      pct={typeof t.profit_ratio === "number" ? t.profit_ratio * 100 : null}
                    />
                  </td>
                  <td className={`amt ${abs >= 0 ? "pos" : "neg"}`}>{signed(abs)}</td>
                  <td className="muted">{t.exit_reason ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

/** ISO datetime -> compact local "MMM d, HH:mm". */
function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
