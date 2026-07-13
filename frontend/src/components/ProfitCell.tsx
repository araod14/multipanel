// % at which the diverging bar reaches its full half-width (visual saturation cap).
const PROFIT_BAR_CAP = 10;

/** Renders the profit % plus a diverging bar: green to the right for gains, red to
 *  the left for losses, with 0 at the center. `pct` is a percentage (e.g. 3.5 = +3.5%). */
export function ProfitCell({ pct }: { pct: number | null }) {
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
