import type { AssistantEvidence, PurchasePlan } from "../types";

export type AssistantMessage = {
  role: "user" | "assistant"; text: string; createdAt: string;
  plan?: PurchasePlan; evidence?: AssistantEvidence;
};

export function conversationHistory(messages: AssistantMessage[]) {
  return messages.slice(-8).map(({ role, text, plan }) => ({
    role,
    text: (text.slice(0, 10000) + (plan ? `\nRestricciones de la propuesta anterior: ${JSON.stringify({ ...plan.filters, budget: plan.budget, currency: plan.budget_currency })}` : "")).slice(0, 16000),
  }));
}

export function readAssistantHistory(key: string): AssistantMessage[] {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(key) ?? "[]");
    return Array.isArray(value) ? value.filter((item): item is AssistantMessage =>
      item && (item.role === "user" || item.role === "assistant") && typeof item.text === "string" && typeof item.createdAt === "string").slice(-20) : [];
  } catch { return []; }
}

export function purchasePlanCsv(plan: PurchasePlan): string {
  const rows = [
    ["Estado", "Prioridad", "Producto", "Almacén", "Disponible", "Demanda sin reservar", "Compras pendientes", "Cantidad", "Unidad", "Coste unitario", "Moneda", "Subtotal", "Fuente coste", "Fecha coste", "Motivo"],
    ...[...plan.lines.map(line => ({ ...line, state: "Propuesto" })), ...plan.excluded.map(line => ({ ...line, state: "Pendiente / excluido" }))].map(line =>
      [line.state, line.priority, line.product_name, line.warehouse_name, line.available_qty, line.sales_unreserved, line.pending_qty,
        line.recommended_qty, line.base_unit_code, line.unit_cost, line.currency, line.subtotal, line.cost_source, line.cost_date, line.reason]),
    ...Object.entries(plan.totals_by_currency).map(([currency, total]) => ["Total estimado", currency, total]),
    ["Sin valorar", plan.unpriced_lines], ["Fecha consulta", plan.generated_at],
    ...plan.assumptions.map(note => ["Supuesto", note]),
  ];
  // A catalog name may begin with a spreadsheet formula. Keep exports as literal text.
  return "\ufeff" + rows.map(row => row.map(value => {
    const text = String(value ?? "");
    return `"${(/^[=+@\-\t\r]/.test(text) ? "'" : "") + text.replace(/"/g, '""')}"`;
  }).join(";")).join("\r\n");
}
