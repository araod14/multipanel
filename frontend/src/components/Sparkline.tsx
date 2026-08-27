const WIDTH = 100;
const HEIGHT = 30;

/** A minimal equity curve: cumulative profit over time, green when the series ends up
 *  and red when it ends down. Deliberately hand-rolled SVG — the project ships no chart
 *  library, and the diverging bar in `ProfitCell` sets the same precedent.
 *
 *  `values` are cumulative amounts, oldest first. The viewBox is stretched to the
 *  container width, so the stroke is drawn with `vector-effect` to stay 1px. */
export function Sparkline({ values, label }: { values: number[]; label?: string }) {
  if (values.length < 2) return <p className="muted">Sin histórico suficiente todavía.</p>;

  const min = Math.min(...values);
  const max = Math.max(...values);
  // A flat series (a bot that has never traded) has no range to normalise against, and
  // would otherwise be pinned to the bottom edge; draw it down the middle instead.
  const flat = max === min;
  const x = (i: number) => (i / (values.length - 1)) * WIDTH;
  const y = (v: number) => (flat ? HEIGHT / 2 : HEIGHT - ((v - min) / (max - min)) * HEIGHT);

  const line = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `0,${HEIGHT} ${line} ${WIDTH},${HEIGHT}`;
  const tone = values[values.length - 1] >= values[0] ? "pos" : "neg";

  return (
    <svg
      className={`sparkline ${tone}`}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={label ?? "Evolución del beneficio"}
    >
      <polygon className="fill" points={area} />
      <polyline className="stroke" points={line} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
