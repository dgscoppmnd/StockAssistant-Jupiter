import { useRef, useState } from "react";
import { fetchMarketingOpportunities } from "../../api";
import type { MarketingResult } from "../../types";
import SectionIcon from "./SectionIcon";
import MarketingInfo from "./MarketingInfo";

const number = (value: number | string) => Number(value).toLocaleString("es-ES", { maximumFractionDigits: 2 });
const channels: Record<string, string> = { web: "Web de la tienda", email: "Correo electrónico", redes_sociales: "Redes sociales" };

export default function MarketingOpportunitiesCard() {
  const [loading, setLoading] = useState(false);
  const inFlight = useRef(false);
  const [result, setResult] = useState<MarketingResult | null>(null);
  const [error, setError] = useState("");
  const analyze = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true); setError(""); setResult(null);
    try { setResult(await fetchMarketingOpportunities()); }
    catch (err) { setError(err instanceof Error ? err.message : "No se pudo analizar Marketing. Vuelve a intentarlo."); }
    finally { inFlight.current = false; setLoading(false); }
  };
  return <article className="card" aria-busy={loading}>
    <p className="section-label">Asistente de Marketing</p>
    <div className="routing-info-heading"><h3><SectionIcon kind="market" />Oportunidades y campañas</h3><MarketingInfo /></div>
    <p>Busca hasta tres productos con aumento de despachos y stock disponible y propone campañas para revisar.</p>
    <button className="primary-btn" type="button" disabled={loading} onClick={() => void analyze()}>{loading ? "Analizando…" : "Buscar oportunidades de Marketing"}</button>
    <p role="status">{loading ? "Revisando despachos, consultando tendencias y preparando propuestas…" : ""}</p>
    {error && <p className="error-line" role="alert">{error}</p>}
    {result && <div className="agent-result">
      <p role="status">{result.status === "no_candidates" ? result.explanation : `${result.opportunities.length} oportunidades para revisar.`}</p>
      <small>Periodos UTC: {result.selection.previous_start} → {result.selection.recent_start} → {result.selection.end_exclusive} (fin excluido).</small>
      {result.opportunities.map(opportunity => <section key={opportunity.product_id} style={{ marginTop: "1.5rem", overflowWrap: "anywhere" }}>
        <h4>{opportunity.product_name}</h4>
        <dl className="operations-result-metrics">
          <div><dt>Despachos anteriores → recientes</dt><dd>{number(opportunity.previous_qty)} → {number(opportunity.recent_qty)} <small>{opportunity.base_unit_code}</small></dd></div>
          <div><dt>Aumento</dt><dd>+{number(opportunity.increase_qty)} <small>({number(opportunity.increase_percent)} %)</small></dd></div>
          <div><dt>Stock disponible</dt><dd>{number(opportunity.available_qty)} <small>{opportunity.base_unit_code}</small></dd></div>
        </dl>
        <p><strong>Interés externo:</strong> {opportunity.external.status === "ok" ? opportunity.external.summary?.status === "descriptive_comparison" ? `Cambio de ${number(opportunity.external.summary.change_index_points ?? 0)} puntos del índice entre bloques completos.` : "Hay datos, pero no suficientes intervalos completos para comparar." : "Sin evidencia externa suficiente; la propuesta se apoya en los datos internos."}</p>
        {opportunity.external.status !== "ok" && opportunity.external.source.detail && <p className="muted">{opportunity.external.source.detail}</p>}
        <small>Fuente: {opportunity.external.source.name} · Término: {opportunity.external.term}</small>
        <p><strong>{opportunity.campaign_origin === "ai" ? "Propuesta de IA" : "Borrador de plantilla"} · Pendiente de revisión</strong></p>
        <p><strong>Objetivo:</strong> {opportunity.campaign.objective}</p>
        <p><strong>Público sugerido:</strong> {opportunity.campaign.audience_hypothesis}</p>
        <p><strong>Canal:</strong> {channels[opportunity.campaign.channel] ?? opportunity.campaign.channel}</p>
        <p><strong>Mensaje propuesto:</strong> {opportunity.campaign.message}</p>
        <p><strong>Motivo:</strong> {opportunity.campaign.reason}</p>
      </section>)}
      {result.warnings.map((warning, i) => <p className="muted" key={i}>{warning}</p>)}
      <small>Consulta: {new Date(result.generated_at).toLocaleString("es-ES")}</small>
      <details><summary>Ver detalles técnicos</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(result, null, 2)}</pre></details>
    </div>}
  </article>;
}
