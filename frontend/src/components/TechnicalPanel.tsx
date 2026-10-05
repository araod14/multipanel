import type { PublicTechnical } from "../api/types";

interface TechnicalPanelProps {
  technical: PublicTechnical[];
}

export default function TechnicalPanel({ technical }: TechnicalPanelProps) {
  if (!technical || technical.length === 0) {
    return (
      <div>
        <div className="technical-header">
          <h3>Análisis de mercado</h3>
          <div className="subtitle">Sin datos disponibles</div>
        </div>
        <div className="technical-empty">
          El servicio no está disponible en este momento
        </div>
      </div>
    );
  }

  // Sort by pair name for consistency
  const sorted = [...technical].sort((a, b) => a.pair.localeCompare(b.pair));

  // Count ratings by category
  const counts = sorted.reduce((acc, item) => {
    const label = item.label?.toLowerCase() || "unknown";
    if (label.includes("compra fuerte")) acc.strongBuy++;
    else if (label.includes("compra")) acc.buy++;
    else if (label === "neutral") acc.neutral++;
    else if (label.includes("venta fuerte")) acc.strongSell++;
    else if (label.includes("venta")) acc.sell++;
    return acc;
  }, { strongBuy: 0, buy: 0, neutral: 0, sell: 0, strongSell: 0 });

  return (
    <div>
      <div className="technical-header">
        <h3>Análisis de mercado</h3>
        <div className="subtitle">
          <span>{sorted.length} pares en análisis</span>
          {counts.strongBuy > 0 && (
            <span className="badge running">
              {counts.strongBuy} compra fuerte
            </span>
          )}
        </div>
      </div>

      <div className="technical-list">
        {sorted.map((item) => {
          const labelClass = getLabelClass(item.label);
          return (
            <div key={`${item.pair}-${item.timeframe}`} className="technical-item">
              <div className="technical-item-header">
                <span className="pair">{item.pair}</span>
                <span className="timeframe">{item.timeframe}</span>
              </div>
              {item.label && (
                <span className={`technical-item-label label ${labelClass}`}>
                  {item.label}
                </span>
              )}
              {!item.label && <span className="muted">Sin valoración</span>}
            </div>
          );
        })}
      </div>

      <div className="technical-credit">
        Fuente: TradingView
        <br />
        <em>Fines informativos, no es consejo</em>
      </div>
    </div>
  );
}

function getLabelClass(label: string | null): string {
  if (!label) return "";
  switch (label.toLowerCase()) {
    case "compra fuerte":
      return "strong-buy";
    case "compra":
      return "buy";
    case "neutral":
      return "neutral";
    case "venta":
      return "sell";
    case "venta fuerte":
      return "strong-sell";
    default:
      return "";
  }
}
