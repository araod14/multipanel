import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userApi } from "../../api/user";

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
                  <ProfitCell pct={typeof t.profit_ratio === "number" ? t.profit_ratio * 100 : null} />
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

// % at which the diverging bar reaches its full half-width (visual saturation cap).
const PROFIT_BAR_CAP = 10;

/** Renders the profit % plus a diverging bar: green to the right for gains, red to
 *  the left for losses, with 0 at the center. */
function ProfitCell({ pct }: { pct: number | null }) {
  if (pct === null) return <>—</>;
  const sign = pct >= 0 ? "pos" : "neg";
  const width = `${Math.min(Math.abs(pct) / PROFIT_BAR_CAP, 1) * 50}%`;
  return (
    <div className="profit-cell">
      <span className={`profit-text ${sign}`}>
        {pct >= 0 ? "+" : ""}
        {pct.toFixed(2)}%
      </span>
      <div className="profit-bar" aria-hidden="true">
        <div className="center" />
        <div className={`fill ${sign}`} style={{ width }} />
      </div>
    </div>
  );
}
