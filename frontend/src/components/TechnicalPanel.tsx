import type { PublicTechnical } from "../api/types";

interface TechnicalPanelProps {
  technical: PublicTechnical[];
}

export default function TechnicalPanel({ technical }: TechnicalPanelProps) {
  if (!technical || technical.length === 0) {
    return (
      <div className="technical-empty">
        No disponible
      </div>
    );
  }

  // Sort by pair name for consistency
  const sorted = [...technical].sort((a, b) => a.pair.localeCompare(b.pair));

  return (
    <div>
      <div className="technical-list">
        {sorted.map((item) => {
          const labelClass = getLabelClass(item.label);
          return (
            <div key={`${item.pair}-${item.timeframe}`} className="technical-item">
              <span className="pair">{item.pair}</span>
              {item.label && (
                <span className={`label ${labelClass}`}>
                  {item.label}
                </span>
              )}
              <span className="timeframe">{item.timeframe}</span>
            </div>
          );
        })}
      </div>
      <div className="technical-credit">
        Fuente: TradingView
        <br />
        <em style={{ fontSize: "10px" }}>No es consejo de inversión</em>
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
