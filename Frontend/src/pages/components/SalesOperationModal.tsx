import { useEffect, useRef, useState, type FormEvent } from "react";
import { fetchSalesDocument, fetchSalesDocuments, salesAction, saveSalesInvoice } from "../../api";
import type { SalesDocument, SalesLine } from "../../types";
import SalesModal from "./SalesModal";

export type SalesOperationMode = "reserve" | "dispatch" | "return" | "invoice";
const labels = { reserve: "Confirmar / reservar", dispatch: "Despachar y facturar", return: "Registrar devolución", invoice: "Agregar factura" };
const maximum = (line: SalesLine, mode: SalesOperationMode) => Math.max(0,
  mode === "reserve" ? Number(line.pending_qty) - Number(line.reserved_qty) :
  mode === "dispatch" ? Number(line.reserved_qty) :
  mode === "return" ? Number(line.dispatched_qty) - Number(line.returned_qty) :
  Number(line.dispatched_qty) - Number(line.invoiced_qty));

export default function SalesOperationModal({ mode, order: initial, invoice, onClose, onSaved }: {
  mode: SalesOperationMode; order: SalesDocument | null; invoice?: SalesDocument;
  onClose: () => void; onSaved: (id: number) => void;
}) {
  const [order, setOrder] = useState(initial);
  const [orderId, setOrderId] = useState(initial?.id ?? invoice?.sales_order_id ?? 0);
  const [options, setOptions] = useState<SalesDocument[]>([]);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [reason, setReason] = useState("");
  const [day, setDay] = useState(invoice?.invoice_date ?? new Date().toLocaleDateString("en-CA"));
  const [due, setDue] = useState(invoice?.due_date ?? "");
  const [reference, setReference] = useState(invoice?.reference ?? "");
  const [notes, setNotes] = useState(invoice?.notes ?? "");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const key = useRef({ fingerprint: "", value: "" });
  const busy = useRef(false);
  useEffect(() => {
    if (mode !== "invoice" || initial || invoice) return;
    const controller = new AbortController();
    void fetchSalesDocuments("orders", { q: query, page, size: 20 }, controller.signal)
      .then(result => { if (!controller.signal.aborted) { setOptions(result.items); setTotal(result.total); } })
      .catch(err => { if (!controller.signal.aborted) setError(String(err)); });
    return () => controller.abort();
  }, [mode, initial, invoice, query, page]);
  useEffect(() => {
    if (!orderId) { setOrder(null); return; }
    const controller = new AbortController();
    setLoading(true); setError(""); setOrder(null); setQuantities({});
    void fetchSalesDocument("orders", orderId, controller.signal).then(data => {
      if (!controller.signal.aborted) {
        setOrder(data);
        setQuantities(Object.fromEntries(data.lines.map(line => [line.id,
          invoice ? Number(invoice.lines.find(l => l.sales_order_line_id === line.id)?.invoiced_qty ?? 0) : 0])));
      }
    }).catch(err => { if (!controller.signal.aborted) setError(String(err)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [orderId, invoice]);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!order || busy.current) return;
    const lines = order.lines.filter(l => quantities[l.id] > 0).map(l => ({ line_id: l.id, quantity: quantities[l.id] }));
    if (!lines.length) { setError("Indica al menos una cantidad."); return; }
    const data = mode === "invoice" ? { sales_order_id: order.id, invoice_date: day, due_date: due || null, reference, notes, lines }
      : { reason: reason || labels[mode], lines };
    const fingerprint = JSON.stringify(data);
    if (key.current.fingerprint !== fingerprint) key.current = { fingerprint, value: crypto.randomUUID() };
    busy.current = true; setSaving(true); setError("");
    try {
      const result = mode === "invoice"
        ? await saveSalesInvoice({ ...data, sales_order_id: order.id, invoice_date: day, due_date: due || null, reference, notes, operation_key: key.current.value }, invoice?.id)
        : await salesAction("orders", order.id, mode, { ...data, operation_key: key.current.value });
      onSaved(result.id);
    } catch (err) { setError(String(err)); }
    finally { busy.current = false; setSaving(false); }
  };
  return <SalesModal title={labels[mode]} saving={saving} onClose={onClose}>
    {error && <p className="error-line" role="alert">{error}</p>}
    <form className="stack" onSubmit={event => void submit(event)}>
      <fieldset disabled={saving} className="sales-fields">
        {mode === "invoice" && !initial && !invoice && <div className="stack">
          <label>Buscar pedido<input value={query} onChange={e => { setQuery(e.target.value); setPage(1); }} /></label>
          <label>Pedido<select required value={orderId || ""} onChange={e => setOrderId(Number(e.target.value))}>
            <option value="">Seleccionar</option>{options.map(o => <option key={o.id} value={o.id}>{o.sales_order_number} · {o.customer_name}</option>)}
          </select></label>
          <div className="actions-row"><button type="button" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button>
            <span>Página {page}</span><button type="button" disabled={page * 20 >= total} onClick={() => setPage(page + 1)}>Siguiente</button></div>
        </div>}
        {loading && <p role="status">Cargando pedido…</p>}
        {order && <>
          <p><strong>{order.sales_order_number}</strong> · {order.customer_name}</p>
          <p className="muted">Cantidades en unidad base. {mode === "dispatch" ? "El despacho descontará stock y generará una sola factura." : mode === "invoice" ? "Facturar no modifica existencias. Solo se admiten despachos aún no facturados." : mode === "return" ? "Confirma únicamente mercancía físicamente recibida." : "La reserva cambia el disponible, no las existencias físicas."}</p>
          {order.lines.map(line => <label key={line.id} className="sales-operation-line">
            <span>{line.description_snapshot || `Producto #${line.product_id}`} · {line.unit_code} · Máximo {maximum(line, mode)}</span>
            <input aria-label={`Cantidad de ${line.description_snapshot || line.product_id}`} type="number" min="0" max={maximum(line,mode)} step="0.0001"
              value={quantities[line.id] ?? 0} onChange={e => setQuantities(current => ({ ...current, [line.id]: Number(e.target.value) }))} />
          </label>)}
          {!order.lines.some(l => maximum(l,mode) > 0) && <p role="status">No hay cantidades disponibles para esta operación.</p>}
        </>}
        {mode === "invoice" ? <div className="inventory-crud-grid">
          <label>Fecha<input required type="date" value={day} onChange={e => setDay(e.target.value)} /></label>
          <label>Vencimiento<input type="date" min={day} value={due} onChange={e => setDue(e.target.value)} /></label>
          <label>Referencia<input maxLength={200} value={reference} onChange={e => setReference(e.target.value)} /></label>
          <label>Notas<textarea maxLength={2000} value={notes} onChange={e => setNotes(e.target.value)} /></label>
        </div> : <label>Motivo<textarea required={mode === "return"} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>}
      </fieldset>
      <div className="actions-row"><button type="submit" className="primary-btn" disabled={saving || loading || !order}>{saving ? "Procesando…" : mode === "invoice" ? "Guardar borrador" : "Confirmar operación"}</button>
        <button type="button" className="chip-btn" disabled={saving} onClick={onClose}>Cancelar</button></div>
    </form>
  </SalesModal>;
}
