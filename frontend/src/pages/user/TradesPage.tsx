import { PageHeading } from "../../components/PageHeading";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userApi } from "../../api/user";
import { ProfitCell } from "../../components/ProfitCell";

export function TradesPage() {
  const qc = useQueryClient();
  const trades = useQuery({
    queryKey: ["me-trades"],
    queryFn: () => userApi.status() as Promise<any>,
    retry: false,
    refetchInterval: 15000,
  });

  const forceExit = useMutation({
    mutationFn: (tradeid: string) => userApi.forceExit(tradeid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me-trades"] }),
  });

  // /status returns an array of open trades directly; tolerate a {trades:[]} shape too.
  const rows: any[] = Array.isArray(trades.data)
    ? trades.data
    : trades.data?.trades ?? [];

  return (
    <>
      <PageHeading title="Operaciones" description="Sigue las posiciones abiertas de tu bot." />
      <div className="card">
        <h2>Operaciones abiertas</h2>
        {trades.isLoading ? (
          <p className="muted" role="status">Cargando operaciones…</p>
        ) : trades.isError ? (
          <p className="muted">No disponible: el bot está iniciando o detenido.</p>
        ) : rows.length === 0 ? (
          <p className="muted">No hay operaciones abiertas.</p>
        ) : (
          <table className="responsive-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Par</th>
                <th>Cantidad</th>
                <th>Precio de entrada</th>
                <th>ROI</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.trade_id}>
                  <td data-label="ID">{t.trade_id}</td>
                  <td data-label="Par" className="table-primary">{t.pair}</td>
                  <td data-label="Cantidad">{t.amount}</td>
                  <td data-label="Entrada">{t.open_rate}</td>
                  <td data-label="Beneficio">
                    <ProfitCell pct={typeof t.profit_ratio === "number" ? t.profit_ratio * 100 : null} />
                  </td>
                  <td data-label="Acción" className="table-actions">
                    <button
                      className="danger"
                      onClick={() => forceExit.mutate(String(t.trade_id))}
                      disabled={forceExit.isPending}
                    >
                      Forzar cierre
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {forceExit.isError && <p className="error" role="alert">No se pudo cerrar la operación. Inténtalo de nuevo.</p>}
      </div>
    </>
  );
}
