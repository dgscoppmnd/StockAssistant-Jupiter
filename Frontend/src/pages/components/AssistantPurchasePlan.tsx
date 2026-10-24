import { useState } from "react";
import type { PurchasePlan } from "../../types";
import { purchasePlanCsv } from "../../utils/assistantConversation";

const quantity = (value: number | string | null | undefined) => value == null ? "Pendiente" : new Intl.NumberFormat("es-ES", { maximumFractionDigits: 4 }).format(Number(value));
const date = (value?: string | null) => value ? new Date(value).toLocaleString("es-ES") : "Sin fecha";

export default function AssistantPurchasePlan({ plan, storageKey }: { plan: PurchasePlan; storageKey: string }) {
  const [status, setStatus] = useState("");
  const save = () => {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(plan));
      setStatus("Borrador guardado en este navegador.");
    } catch { setStatus("No se pudo guardar: el almacenamiento del navegador no está disponible."); }
  };
  const download = () => {
    const url = URL.createObjectURL(new Blob([purchasePlanCsv(plan)], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url; link.download = "borrador-plan-compras.csv"; link.click();
    URL.revokeObjectURL(url);
  };
  return <section aria-label="Propuesta de compras calculada">
    <h4>Propuesta de compras · borrador</h4>
    <p>Estado consultado: {date(plan.generated_at)}. Indicadores de actividad: {plan.period_days} días.</p>
    {plan.truncated && <p role="status">Propuesta parcial: se evaluaron {plan.limit} de {plan.candidate_count} candidatos por prioridad. Los totales cubren esa selección. Filtra por producto o almacén para concretar.</p>}
    {plan.budget != null && <p>Presupuesto: {quantity(plan.budget)} {plan.budget_currency ?? "(falta indicar moneda)"}.</p>}
    {plan.lines.length ? <div className="dashboard-table-wrap"><table>
      <caption>Productos y cantidades calculados con los datos consultados</caption>
      <thead><tr><th>Producto / almacén</th><th>Cantidad</th><th>Coste unitario</th><th>Subtotal</th></tr></thead>
      <tbody>{plan.lines.map(line => <tr key={`${line.product_id}-${line.warehouse_id}`}>
        <td><strong>{line.product_name}</strong><br />{line.warehouse_name} · {line.priority}<br />
          <small>Disponible: {quantity(line.available_qty)}; demanda sin reservar: {quantity(line.sales_unreserved)}; compras pendientes: {quantity(line.pending_qty)}.<br />{line.reason}</small></td>
        <td>{quantity(line.recommended_qty)} {line.base_unit_code}</td>
        <td>{line.unit_cost == null ? "Coste no disponible" : `${quantity(line.unit_cost)} ${line.currency}`}<br />
          <small>{line.cost_source}{line.cost_date ? ` · ${date(line.cost_date)}` : ""}{line.supplier_name ? ` · ${line.supplier_name}` : ""}</small></td>
        <td>{line.subtotal == null ? "Pendiente" : `${quantity(line.subtotal)} ${line.currency}`}</td>
      </tr>)}</tbody>
    </table></div> : <p>No hay líneas de compra que cumplan los criterios y la cobertura actual.</p>}
    {Object.entries(plan.totals_by_currency).map(([currency, total]) => <p key={currency}><strong>Total estimado {currency}: {quantity(total)}</strong></p>)}
    <p>{plan.unpriced_lines} líneas propuestas sin valorar. Costes históricos estimados; impuestos y transporte no incluidos.</p>
    {!!plan.excluded.length && <details><summary>Pendientes y exclusiones ({plan.excluded.length})</summary><ul>{plan.excluded.map(line =>
      <li key={`${line.product_id}-${line.warehouse_id}`}>{line.product_name} · {line.warehouse_name}: {line.reason}</li>)}</ul></details>}
    <details><summary>Criterios de cálculo</summary><ul>{plan.assumptions.map(note => <li key={note}>{note}</li>)}</ul></details>
    <p><button className="chip-btn" type="button" onClick={save}>Guardar borrador local</button>{" "}
      <button className="chip-btn" type="button" onClick={download}>Descargar CSV del plan</button></p>
    <small>El borrador se conserva en este navegador. No crea pedidos ni modifica inventario.</small>
    <p role="status">{status}</p>
  </section>;
}
