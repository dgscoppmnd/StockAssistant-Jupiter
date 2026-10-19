import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createPurchaseRecommendation, fetchCompetition, fetchExternalSourceStatuses, fetchFinancialSummary, fetchRisks, fetchSalesForecast, fetchStockAlerts, processReviewBatch } from "../api";
import type { ExternalSourceStatus, FinancialSummary, ProductOption, PurchaseRecommendation, SalesForecast, StockAlert } from "../types";
import SectionIcon from "./components/SectionIcon";
import ProductCombobox from "./components/ProductCombobox";
import CustomerSupportChat from "./components/CustomerSupportChat";
import PurchaseRecommendationInfo from "./components/PurchaseRecommendationInfo";
import ReviewBatchInfo from "./components/ReviewBatchInfo";
import MarketTrendsCard from "./components/MarketTrendsCard";

const sourceModes: Record<string, string> = { read_only: 'Solo lectura', disabled: 'Deshabilitada' };
const formatNumber = (value: number) => Number(value).toLocaleString('es-ES', { maximumFractionDigits: 2 });
const formatAmount = (value: number) => Number(value).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function AgentsOperationsPage() {
  const [sources, setSources] = useState<ExternalSourceStatus[]>([]);
  const [alerts, setAlerts] = useState<StockAlert[]>([]);
  const [recommendation, setRecommendation] = useState<PurchaseRecommendation | null>(null);
  const [productId, setProductId] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<ProductOption | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const canAnalyze = Boolean(selectedProduct) && !analyzing;
  const [reviewProductId, setReviewProductId] = useState("");
  const [reviews, setReviews] = useState("");
  const [processingReviews, setProcessingReviews] = useState(false);
  const [selectedReviewProduct, setSelectedReviewProduct] = useState<ProductOption | null>(null);
  const canProcessReviews = Boolean(selectedReviewProduct) && Boolean(reviews.trim()) && !processingReviews;
  const [status, setStatus] = useState("Cargando agentes...");
  const [error, setError] = useState("");
  const [forecast, setForecast] = useState<SalesForecast | null>(null);
  const [financial, setFinancial] = useState<FinancialSummary | null>(null);
  const [competition, setCompetition] = useState<Record<string, unknown> | null>(null);
  const [risks, setRisks] = useState<Array<{ type: string; product_name: string; return_rate: number }>>([]);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [nextSources, nextAlerts, nextRisks] = await Promise.all([fetchExternalSourceStatuses(), fetchStockAlerts(), fetchRisks()]);
      setSources(nextSources); setAlerts(nextAlerts); setRisks(nextRisks.alerts); setLoaded(true); setStatus("Datos internos sincronizados"); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudieron cargar los agentes"); setStatus("No se pudieron actualizar los datos internos"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const recommend = async (event: FormEvent) => {
    event.preventDefault();
    if (!canAnalyze) return;
    setError(""); setAnalyzing(true);
    try { setRecommendation(await createPurchaseRecommendation(Number(productId))); setStatus("Recomendación calculada con evidencia disponible."); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo crear la recomendacion"); }
    finally { setAnalyzing(false); }
  };
  const submitReviews = async (event: FormEvent) => {
    event.preventDefault();
    if (!canProcessReviews) return;
    setError(""); setProcessingReviews(true);
    const batch = reviews.split("\n").map((text) => text.trim()).filter(Boolean).map((text) => ({ text }));
    try { const result = await processReviewBatch({ product_id: Number(reviewProductId), source: "manual", reviews: batch }); setStatus(`Lote procesado: ${result.processed_reviews} valoraciones.`); setReviews(""); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudieron procesar las valoraciones"); }
    finally { setProcessingReviews(false); }
  };
  const analyzeProduct = async () => {
    if (!canAnalyze) return;
    setAnalyzing(true);
    try {
      const id = Number(productId);
      const [nextForecast, nextFinancial, nextCompetition] = await Promise.all([fetchSalesForecast(id), fetchFinancialSummary(id), fetchCompetition(id)]);
      setForecast(nextForecast); setFinancial(nextFinancial); setCompetition(nextCompetition); setStatus("Previsión, margen y competencia calculados con evidencia."); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudo analizar el producto"); }
    finally { setAnalyzing(false); }
  };

  return <div className="agent-operations operations-workspace">
    <section className="card operations-header">
      <div className="operations-header-top"><div><p className="section-label">Operación comercial · inteligencia de negocio</p><h3><SectionIcon kind="assistant"/>Agentes y análisis</h3><p className="operations-description">Datos internos verificables y fuentes externas de solo lectura.</p></div><div className="operations-header-actions"><Link className="chip-btn" to="/agentes/reglas">Editor de reglas <span aria-hidden="true">↗</span></Link><button className="chip-btn" disabled={loading} onClick={()=>void load()}>{loading ? 'Actualizando…' : 'Actualizar datos'}</button></div></div>
      <div className="operations-overview"><div><span className="operations-dot operations-dot--amber"/><strong>{loaded ? alerts.length : '—'}</strong><span>Alertas de stock</span></div><div><span className="operations-dot operations-dot--green"/><strong>{loaded ? `${sources.filter(s=>s.available).length}/${sources.length}` : '—'}</strong><span>Fuentes disponibles</span></div><div><span className="operations-dot operations-dot--rose"/><strong>{loaded ? risks.length : '—'}</strong><span>Riesgos de devolución</span></div></div>
      <div className="operations-feedback" role="status" aria-live="polite"><span className="operations-dot"/>{loading ? 'Sincronizando datos internos…' : status}</div>
      {error && <div className="operations-error" role="alert"><span>{error}</span><button type="button" className="chip-btn" disabled={loading} onClick={()=>void load()}>Reintentar carga</button></div>}
    </section>
    <nav className="operations-nav" aria-label="Secciones de agentes"><a href="#agent-signals">Señales del negocio</a><a href="#agent-tools">Herramientas de análisis</a><a href="#agent-results">Resultados comerciales</a><a href="#agent-support">Soporte y mercado</a></nav>
    <section className="operations-section" id="agent-signals" aria-labelledby="agent-signals-title">
      <div className="operations-section-heading"><h3 id="agent-signals-title"><span>01</span>Señales del negocio</h3><span>Stock y disponibilidad de fuentes</span></div>
      <div className="operations-columns operations-monitor">
        <article className="card operations-alerts" aria-busy={loading}><div className="operations-card-heading"><div><p className="section-label">Agente de stock</p><h3><SectionIcon kind="alert"/>Alertas de reposición</h3></div><span className="operations-count">{loaded ? alerts.length : '—'}</span></div>
          {alerts.length ? <div className="operations-stock-list"><div className="operations-stock-labels" aria-hidden="true"><span>Producto / almacén</span><span>Disponible / umbral</span></div>{alerts.map(alert=><div className="operations-stock-row" key={`${alert.product_id}-${alert.warehouse_id}`}><div><strong>{alert.product_name}</strong><span>{alert.warehouse_name}</span></div><div><strong>{alert.available_qty.toLocaleString('es-ES')}<span> / {alert.reorder_point.toLocaleString('es-ES')}</span></strong><small>{alert.base_unit_code}</small></div></div>)}</div> : <div className="operations-empty"><SectionIcon kind="stock"/><strong>{loading ? 'Revisando niveles de stock…' : loaded ? 'Sin alertas de reposición' : 'Stock pendiente de consulta'}</strong><p>{loaded ? 'No hay productos que necesiten reposición por este criterio.' : 'Las alertas aparecerán cuando se sincronicen los datos.'}</p></div>}
        </article>
        <article className="card" aria-busy={loading}><div className="operations-card-heading"><div><p className="section-label">Fuentes externas</p><h3><SectionIcon kind="source"/>Disponibilidad y modo</h3></div><span className="operations-badge">Solo lectura</span></div>
          <div className="operations-sources">{sources.map(source=><div className="operations-source" key={source.name}><div><strong>{source.name}</strong><span className={`operations-badge ${source.available ? 'operations-badge--green' : 'operations-badge--amber'}`}><span className="operations-dot"/>{source.available ? 'Disponible' : 'No disponible'}</span></div><p>{source.detail}</p><small>Modo: {sourceModes[source.mode] ?? source.mode}</small></div>)}{!sources.length && <p className="operations-empty">{loading ? 'Consultando fuentes…' : loaded ? 'No hay fuentes externas configuradas.' : 'Disponibilidad pendiente de consulta.'}</p>}</div>
        </article>
      </div>
    </section>
    <section className="operations-section" id="agent-tools" aria-labelledby="agent-tools-title">
      <div className="operations-section-heading"><h3 id="agent-tools-title"><span>02</span>Herramientas de análisis</h3><span>Selecciona un producto para empezar</span></div>
      <div className="operations-columns">
        <article className="card operations-purchasing"><p className="section-label">Agente de compras</p><div className="routing-info-heading"><h3><SectionIcon kind="cart"/>Recomendación con evidencia</h3><PurchaseRecommendationInfo/></div><p className="operations-hint">Consulta cantidades sugeridas y ofertas comparables para un producto.</p>
          <form className="stack" onSubmit={recommend}><ProductCombobox selectedProduct={selectedProduct} selectedId={Number(productId)} disabled={analyzing} onSelect={product=>{if(product.pk_product===Number(productId))return;setSelectedProduct(product);setProductId(String(product.pk_product));setRecommendation(null);setForecast(null);setFinancial(null);setCompetition(null);setError('');}}/>
            <div className="operations-form-actions"><button className="primary-btn" disabled={!canAnalyze} type="submit">{analyzing ? 'Analizando…' : 'Analizar compra'}</button><button className="chip-btn" disabled={!canAnalyze} onClick={()=>void analyzeProduct()} type="button">Análisis comercial</button></div>
          </form>
          {analyzing && <p className="operations-hint" role="status">Consultando la evidencia disponible para el producto…</p>}
          {recommendation && <div className="agent-result" role="status"><span className="operations-result-label">Recomendación de compra</span><strong>{recommendation.product_name}</strong><dl className="operations-result-metrics"><div><dt>Pedido sugerido</dt><dd>{formatNumber(recommendation.recommended_qty)} <small>{recommendation.base_unit_code}</small></dd></div><div><dt>Coste estimado</dt><dd>{recommendation.estimated_landed_cost == null ? 'Sin oferta' : formatAmount(recommendation.estimated_landed_cost)} <small>{recommendation.currency}</small></dd></div></dl><p>{recommendation.explanation}</p><small>Ofertas comparables: {recommendation.offers.length}</small></div>}
        </article>
        <article className="card operations-reviews"><p className="section-label">Agente de valoraciones</p><div className="routing-info-heading"><h3><SectionIcon kind="review"/>Procesar valoraciones</h3><ReviewBatchInfo/></div><p className="operations-hint">Añade las opiniones de un producto, una por línea.</p>
          <form className="stack" onSubmit={submitReviews}><ProductCombobox selectedProduct={selectedReviewProduct} selectedId={Number(reviewProductId)} disabled={processingReviews} onSelect={product=>{setSelectedReviewProduct(product);setReviewProductId(String(product.pk_product));setError('');}}/>
            <label>Valoraciones<textarea required disabled={processingReviews} placeholder={'El producto es excelente.\nLa entrega llegó tarde.\nBuen acabado y presentación.'} value={reviews} onChange={event=>setReviews(event.target.value)} rows={4}/></label>
            <div className="operations-form-actions"><span className="operations-hint">{reviews.split('\n').filter(line=>line.trim()).length} líneas con texto</span><button className="primary-btn" disabled={!canProcessReviews} type="submit">{processingReviews ? 'Procesando…' : 'Clasificar valoraciones'}</button></div>
          </form>
        </article>
      </div>
    </section>
    <section className="operations-section" id="agent-results" aria-labelledby="agent-results-title">
      <div className="operations-section-heading"><h3 id="agent-results-title"><span>03</span>Resultados comerciales</h3><span>Previsión, margen y riesgo</span></div>
      <div className="operations-columns">
        <article className="card"><p className="section-label">Ventas y finanzas</p><h3><SectionIcon kind="trend"/>Previsión y margen</h3>{forecast ? <div className="agent-result"><strong>{forecast.product_name}</strong><dl className="operations-result-metrics"><div><dt>Previsión · {forecast.horizon_days} días</dt><dd>{formatNumber(forecast.forecast_qty)} <small>unidades</small></dd></div><div><dt>Media diaria</dt><dd>{formatNumber(forecast.daily_average)}</dd></div></dl><p>Tendencia: {forecast.trend}</p></div> : <div className="operations-empty"><SectionIcon kind="trend"/><strong>Tu análisis aparecerá aquí</strong><p>Selecciona un producto en compras y ejecuta «Análisis comercial».</p><a href="#agent-tools">Ir al análisis de producto <span aria-hidden="true">↑</span></a></div>}{financial && <dl className="operations-financial"><div><dt>Ingresos</dt><dd>{formatAmount(financial.revenue)}</dd></div><div><dt>Coste</dt><dd>{formatAmount(financial.cost)}</dd></div><div><dt>Margen</dt><dd>{formatAmount(financial.margin)} <span>({formatNumber(financial.margin_percent)} %)</span></dd></div></dl>}</article>
        <article className="card"><p className="section-label">Competencia y riesgos</p><h3><SectionIcon kind="risk"/>Datos con vigencia</h3>{competition ? <div className="operations-competition"><span>Ofertas comparables</span><strong>{Array.isArray(competition.offers) ? competition.offers.length : 0}</strong><small>La fuente y fecha se devuelven en cada consulta.</small></div> : <p className="operations-hint">Ejecuta «Análisis comercial» para consultar la competencia.</p>}<div className="operations-risks">{risks.map((risk,index)=><div className="operations-risk" key={`${risk.product_name}-${index}`}><strong>{risk.product_name}</strong><span className="operations-badge operations-badge--rose">Devoluciones: {(risk.return_rate*100).toFixed(1)} %</span></div>)}{!risks.length && <p className="operations-hint">{loading ? 'Revisando riesgos…' : loaded ? 'No hay riesgos de devolución sobre el umbral.' : 'Riesgos pendientes de consulta.'}</p>}</div></article>
      </div>
    </section>
    <section className="operations-section" id="agent-support" aria-labelledby="agent-support-title">
      <div className="operations-section-heading"><h3 id="agent-support-title"><span>04</span>Soporte y mercado</h3><span>Consultas con fuentes</span></div>
      <div className="operations-columns"><CustomerSupportChat/>
        <MarketTrendsCard />
      </div>
    </section>
  </div>;
}
