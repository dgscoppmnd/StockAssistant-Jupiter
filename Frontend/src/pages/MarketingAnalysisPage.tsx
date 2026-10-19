import { Link } from "react-router-dom";
import MarketingOpportunitiesCard from "./components/MarketingOpportunitiesCard";
import SectionIcon from "./components/SectionIcon";

export default function MarketingAnalysisPage() {
  return <div className="grid agent-operations">
    <section className="card">
      <p className="section-label">Marketing</p>
      <h2><SectionIcon kind="market" />Análisis de Marketing</h2>
      <p>Identifica productos con crecimiento de despachos y stock disponible, contrasta su interés público y prepara propuestas de campaña para revisar.</p>
      <p>No necesitas seleccionar un producto: el análisis busca candidatos en el catálogo. También puedes pedir «Busca oportunidades de marketing» desde el <Link to="/ejecutivo">Agente Ejecutivo</Link>.</p>
    </section>
    <MarketingOpportunitiesCard />
  </div>;
}
