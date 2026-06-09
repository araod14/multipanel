import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userApi } from "../../api/user";

export function TradesPage() {
  const qc = useQueryClient();
  const trades = useQuery({
    queryKey: ["me-trades"],
    queryFn: () => userApi.trades() as Promise<any>,
    retry: false,
    refetchInterval: 15000,
  });

  const forceExit = useMutation({
    mutationFn: (tradeid: string) => userApi.forceExit(tradeid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me-trades"] }),
  });

  const rows: any[] = trades.data?.trades ?? [];

  return (
    <div className="card">
      <h2>Open trades</h2>
      {trades.isError ? (
        <p className="muted">Unavailable (bot starting or stopped).</p>
      ) : rows.length === 0 ? (
        <p className="muted">No open trades.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Pair</th>
              <th>Amount</th>
              <th>Open rate</th>
              <th>Profit %</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.trade_id}>
                <td>{t.trade_id}</td>
                <td>{t.pair}</td>
                <td>{t.amount}</td>
                <td>{t.open_rate}</td>
                <td>
                  {typeof t.profit_ratio === "number" ? `${(t.profit_ratio * 100).toFixed(2)}%` : "—"}
                </td>
                <td style={{ textAlign: "right" }}>
                  <button
                    className="danger"
                    onClick={() => forceExit.mutate(String(t.trade_id))}
                    disabled={forceExit.isPending}
                  >
                    Force exit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
