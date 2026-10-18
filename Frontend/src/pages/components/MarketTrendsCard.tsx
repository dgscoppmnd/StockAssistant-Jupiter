import { FormEvent, useRef, useState } from "react";
import { fetchMarketIntelligence } from "../../api";
import SectionIcon from "./SectionIcon";
import MarketTrendsInfo from "./MarketTrendsInfo";

type Point = { timestamp: number; date: string; value: number };
type Related = { query: string; value: string };
type MarketResult = {
  term: string; country: string; status: string; explanation: string;
  source: { name: string; detail?: string };
  generated_at: string; warnings: string[];
  ai: { provider: string; model: string; used_fallback: boolean } | null;
  data: { interest_over_time: Point[]; related_queries: { top: Related[]; rising: Related[] } } | null;
};

function InterestChart({ points }: { points: Point[] }) {
  const first = points[0].timestamp;
  const range = points[points.length - 1].timestamp - first || 1;
  const x = (point: Point) => 48 + ((point.timestamp - first) / range) * 604;
  const y = (point: Point) => 216 - point.value * 1.9;
  return <figure style={{ margin: "1rem 0" }}>
    <svg viewBox="0 0 680 265" role="img" aria-label="Evolución del interés relativo de búsqueda, de cero a cien" style={{ width: "100%", maxWidth: 800 }}>
      <title>Interés de búsqueda de Google Trends</title>
      {[0, 50, 100].map(value => <g key={value}>
        <line x1="48" x2="652" y1={216 - value * 1.9} y2={216 - value * 1.9} stroke="currentColor" opacity="0.18" />
        <text x="38" y={220 - value * 1.9} textAnchor="end" fill="currentColor" fontSize="12">{value}</text>
      </g>)}
      <polyline points={points.map(point => `${x(point)},${y(point)}`).join(" ")} fill="none" stroke="currentColor" strokeWidth="2.5" />
      {points.map(point => <circle key={point.timestamp} cx={x(point)} cy={y(point)} r="3" fill="currentColor"><title>{point.date}: {point.value}</title></circle>)}
      <text x="48" y="247" fill="currentColor" fontSize="11">{points[0].date}</text>
      <text x="652" y="247" textAnchor="end" fill="currentColor" fontSize="11">{points[points.length - 1].date}</text>
    </svg>
    <figcaption>Índice relativo de 0 a 100. No representa número de búsquedas ni ventas. Se omiten observaciones no válidas o marcadas como parciales.</figcaption>
  </figure>;
}

export default function MarketTrendsCard() {
  const [term, setTerm] = useState("");
  const [loading, setLoading] = useState(false);
  const inFlight = useRef(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<MarketResult | null>(null);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const query = term.trim();
    if (inFlight.current || query.length < 2 || query.length > 100) return;
    inFlight.current = true;
    setLoading(true); setError(""); setResult(null);
    try { setResult(await fetchMarketIntelligence(query) as unknown as MarketResult); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo consultar Tendencias. Vuelve a intentarlo."); }
    finally { inFlight.current = false; setLoading(false); }
  };
  const points = result?.data?.interest_over_time ?? [];
  return <article className="card" aria-busy={loading}>
    <p className="section-label">Inteligencia de mercado</p>
    <div className="routing-info-heading"><h3><SectionIcon kind="market" />Tendencias autorizadas</h3><MarketTrendsInfo /></div>
    <form className="stack" onSubmit={submit}>
      <label htmlFor="market-trends-term">Producto o categoría</label>
      <input id="market-trends-term" required minLength={2} maxLength={100} placeholder="Ej.: auriculares inalámbricos" disabled={loading} value={term} onChange={event => setTerm(event.target.value)} />
      <small>España · Últimos 12 meses · Interés de búsqueda</small>
      <button className="chip-btn" type="submit" disabled={loading || term.trim().length < 2}>{loading ? "Consultando…" : "Consultar SerpAPI Trends"}</button>
    </form>
    <p role="status">{loading ? "Consultando la fuente y preparando el análisis…" : ""}</p>
    {error && <p className="error-line" role="alert">{error}</p>}
    {result && <div className="agent-result">
      <strong>{result.term} · {result.country}</strong>
      <p role="status">{result.status === "ok" ? `${points.length} observaciones válidas recibidas.` : result.status === "no_data" ? "No hay datos válidos para analizar." : "La fuente no está disponible."}</p>
      {!!points.length && <InterestChart points={points} />}
      <h4>{result.ai ? "Análisis de IA" : "Resumen calculado"}</h4>
      <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{result.explanation}</p>
      {result.status === "source_unavailable" && <p>{result.source.detail}</p>}
      {result.data && <>
        <h4>Consultas relacionadas</h4>
        {(["top", "rising"] as const).map(category => <div key={category}>
          <strong>{category === "top" ? "Más consultadas (índice relativo)" : "En aumento (valor indicado por Google)"}</strong>
          {result.data!.related_queries[category].length ? <ul>{result.data!.related_queries[category].map((item, i) => <li key={`${item.query}-${i}`}>{item.query}: {item.value}</li>)}</ul> : <p className="muted">Sin resultados disponibles.</p>}
        </div>)}
      </>}
      {result.warnings.map((warning, i) => <p className="muted" key={i}>{warning}</p>)}
      <small>Fuente: {result.source.name} · Consulta: {new Date(result.generated_at).toLocaleString("es-ES")}</small>
      {!!points.length && <details><summary>Ver valores del gráfico</summary><div style={{ overflowX: "auto" }}><table><thead><tr><th>Periodo</th><th>Índice de interés</th></tr></thead><tbody>{points.map(point => <tr key={point.timestamp}><td>{point.date}</td><td>{point.value}</td></tr>)}</tbody></table></div></details>}
      <details><summary>Ver detalles técnicos</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(result, null, 2)}</pre></details>
    </div>}
  </article>;
}
