/** One labelled figure in a `.grid` of stat tiles. `tone` colours the value green when
 *  positive and red when negative, which is why it takes the raw number rather than a
 *  boolean — 0 stays neutral. */
export function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: number;
}) {
  const toneClass = typeof tone === "number" && tone !== 0 ? (tone > 0 ? "pos" : "neg") : "";
  return (
    <div className="metric">
      <div className="muted">{label}</div>
      <div className={`v ${toneClass}`}>{value}</div>
      {sub !== undefined && <div className="muted">{sub}</div>}
    </div>
  );
}
