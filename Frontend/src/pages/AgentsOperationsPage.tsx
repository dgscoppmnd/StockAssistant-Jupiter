import { FormEvent, useEffect, useState } from "react";
import { askCustomerSupport, createPurchaseRecommendation, fetchCompetition, fetchExternalSourceStatuses, fetchFinancialSummary, fetchMarketIntelligence, fetchRisks, fetchSalesForecast, fetchStockAlerts, processReviewBatch } from "../api";
import type { CustomerSupportAnswer, ExternalSourceStatus, FinancialSummary, PurchaseRecommendation, SalesForecast, StockAlert } from "../types";

export default function AgentsOperationsPage() {
  const [sources, setSources] = useState<ExternalSourceStatus[]>([]);
  const [alerts, setAlerts] = useState<StockAlert[]>([]);
  const [recommendation, setRecommendation] = useState<PurchaseRecommendation | null>(null);
  const [productId, setProductId] = useState("");
  const [reviewProductId, setReviewProductId] = useState("");
  const [reviews, setReviews] = useState("");
  const [status, setStatus] = useState("Cargando agentes...");
  const [error, setError] = useState("");
  const [forecast, setForecast] = useState<SalesForecast | null>(null);
  const [financial, setFinancial] = useState<FinancialSummary | null>(null);
  const [competition, setCompetition] = useState<Record<string, unknown> | null>(null);
  const [market, setMarket] = useState<Record<string, unknown> | null>(null);
  const [support, setSupport] = useState<CustomerSupportAnswer | null>(null);
  const [risks, setRisks] = useState<Array<{ type: string; product_name: string; return_rate: number }>>([]);
  const [question, setQuestion] = useState("");
  const [term, setTerm] = useState("");

  const load = async () => {
    try {
      const [nextSources, nextAlerts, nextRisks] = await Promise.all([fetchExternalSourceStatuses(), fetchStockAlerts(), fetchRisks()]);
      setSources(nextSources); setAlerts(nextAlerts); setRisks(nextRisks.alerts); setStatus("Agentes sincronizados con los datos internos."); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudieron cargar los agentes"); }
  };
  useEffect(() => { void load(); }, []);

  const recommend = async (event: FormEvent) => {
    event.preventDefault(); setError("");
    try { setRecommendation(await createPurchaseRecommendation(Number(productId))); setStatus("Recomendacion calculada con evidencia disponible."); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo crear la recomendacion"); }
  };
  const submitReviews = async (event: FormEvent) => {
    event.preventDefault(); setError("");
    const batch = reviews.split("\n").map((text) => text.trim()).filter(Boolean).map((text) => ({ text }));
    try { const result = await processReviewBatch({ product_id: Number(reviewProductId), source: "manual", reviews: batch }); setStatus(`Lote procesado: ${result.processed_reviews} valoraciones.`); setReviews(""); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudieron procesar las valoraciones"); }
  };
  const analyzeProduct = async () => {
    try {
      const id = Number(productId);
      const [nextForecast, nextFinancial, nextCompetition] = await Promise.all([fetchSalesForecast(id), fetchFinancialSummary(id), fetchCompetition(id)]);
      setForecast(nextForecast); setFinancial(nextFinancial); setCompetition(nextCompetition); setStatus("Prevision, margen y competencia calculados con evidencia."); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudo analizar el producto"); }
  };
  const askSupport = async (event: FormEvent) => {
    event.preventDefault(); try { setSupport(await askCustomerSupport(question, productId ? Number(productId) : undefined)); setError(""); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo consultar al asistente"); }
  };
  const analyzeMarket = async (event: FormEvent) => {
    event.preventDefault(); try { setMarket(await fetchMarketIntelligence(term)); setError(""); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo consultar tendencias"); }
  };

  return <div className="grid agent-operations">
    <section className="card agent-hero"><p className="section-label">Fase 3 · Operacion comercial y analisis</p><h3>Señales reales, decisiones humanas</h3><p>Los agentes calculan stock, previsiones y márgenes con datos verificables. Las fuentes externas son solo de lectura.</p><p className="status-line">{status}</p>{error && <p className="error-line">{error}</p>}</section>
    <section className="grid two-columns">
      <article className="card"><p className="section-label">Agente de stock</p><h3>Alertas de reposicion</h3><div className="inventory-table">{alerts.map((alert) => <div className="inventory-table-row" key={`${alert.product_id}-${alert.warehouse_id}`}><span>{alert.product_name}</span><span>{alert.warehouse_name}</span><strong>{alert.available_qty}/{alert.reorder_point} {alert.base_unit_code}</strong></div>)}{!alerts.length && <p className="muted">No hay productos bajo el punto de pedido.</p>}</div></article>
      <article className="card"><p className="section-label">Fuentes externas</p><h3>Disponibilidad y modo</h3><div className="inventory-list">{sources.map((source) => <div className="inventory-list-item" key={source.name}><strong>{source.name}</strong><span className={source.available ? "source-live" : "source-offline"}>{source.available ? "Disponible" : "No disponible"}</span><small>{source.detail}</small></div>)}</div></article>
    </section>
    <section className="grid two-columns">
      <article className="card"><p className="section-label">Agente de compras</p><h3>Recomendacion con evidencia</h3><form className="quick-row" onSubmit={recommend}><input required min="1" placeholder="ID de producto" type="number" value={productId} onChange={(event) => setProductId(event.target.value)} /><button className="primary-btn" type="submit">Analizar compra</button></form><button className="chip-btn" disabled={!productId} onClick={() => void analyzeProduct()} type="button">Analisis comercial</button>{recommendation && <div className="agent-result"><strong>{recommendation.product_name}</strong><p>Pedido sugerido: {recommendation.recommended_qty} {recommendation.base_unit_code}</p><p>Coste estimado: {recommendation.estimated_landed_cost ?? "Sin oferta"} {recommendation.currency}</p><p>{recommendation.explanation}</p><small>Ofertas comparables: {recommendation.offers.length}</small></div>}</article>
      <article className="card"><p className="section-label">Agente de valoraciones</p><h3>Procesar lote</h3><form className="stack" onSubmit={submitReviews}><input required min="1" placeholder="ID de producto" type="number" value={reviewProductId} onChange={(event) => setReviewProductId(event.target.value)} /><textarea required placeholder="Una valoracion por linea" value={reviews} onChange={(event) => setReviews(event.target.value)} rows={5} /><button className="chip-btn" type="submit">Clasificar valoraciones</button></form></article>
    </section>
    <section className="grid two-columns">
      <article className="card"><p className="section-label">Ventas y finanzas</p><h3>Prevision y margen</h3>{forecast ? <div className="agent-result"><strong>{forecast.product_name}</strong><p>Prevision: {forecast.forecast_qty} unidades en {forecast.horizon_days} dias.</p><p>Tendencia: {forecast.trend}. Media diaria: {forecast.daily_average}.</p></div> : <p className="muted">Selecciona un producto y ejecuta Analisis comercial.</p>}{financial && <div className="agent-result"><p>Ingresos: {financial.revenue}</p><p>Coste: {financial.cost}</p><strong>Margen: {financial.margin} ({financial.margin_percent}%)</strong></div>}</article>
      <article className="card"><p className="section-label">Competencia y riesgos</p><h3>Datos con vigencia</h3>{competition ? <div className="agent-result"><p>Ofertas comparables: {Array.isArray(competition.offers) ? competition.offers.length : 0}</p><small>La fuente y fecha se devuelven en cada consulta.</small></div> : <p className="muted">No se ha consultado competencia.</p>}<div className="inventory-list">{risks.map((risk, index) => <div className="inventory-list-item" key={`${risk.product_name}-${index}`}><strong>{risk.product_name}</strong><span>Devoluciones: {(risk.return_rate * 100).toFixed(1)}%</span></div>)}{!risks.length && <p className="muted">No hay riesgos de devolucion sobre el umbral.</p>}</div></article>
    </section>
    <section className="grid two-columns">
      <article className="card"><p className="section-label">Atencion al cliente · RAG</p><h3>Respuesta con fuentes vigentes</h3><form className="stack" onSubmit={askSupport}><textarea required placeholder="Pregunta del cliente" value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} /><button className="primary-btn" type="submit">Consultar contexto</button></form>{support && <div className="agent-result"><p>{support.answer}</p><small>Fuentes: {support.sources.map((source) => source.title).join(", ") || "sin documentos vigentes"}</small></div>}</article>
      <article className="card"><p className="section-label">Inteligencia de mercado</p><h3>Tendencias autorizadas</h3><form className="stack" onSubmit={analyzeMarket}><input required placeholder="Termino de busqueda" value={term} onChange={(event) => setTerm(event.target.value)} /><button className="chip-btn" type="submit">Consultar SerpAPI Trends</button></form>{market && <div className="agent-result"><p>{market.data ? "Datos de tendencia recibidos." : "La fuente no esta disponible."}</p><small>Fuente: {String((market.source as { name?: string })?.name ?? "sin fuente")}</small></div>}</article>
    </section>
  </div>;
}
