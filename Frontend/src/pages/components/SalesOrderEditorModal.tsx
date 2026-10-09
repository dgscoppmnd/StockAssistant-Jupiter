import { useEffect, useRef, useState, type FormEvent } from "react";
import { fetchClientAddresses, fetchInventoryWarehouses, fetchMasterRecords, saveSalesOrder } from "../../api";
import type { ClientAddress, InventoryWarehouse, MasterRecord, SalesClient, SalesDocument, SalesDraftLine } from "../../types";
import ClientCombobox from "./ClientCombobox";
import ProductCombobox from "./ProductCombobox";
import SalesModal from "./SalesModal";

const today = () => new Date().toLocaleDateString("en-CA");
const blankLine = (): SalesDraftLine => ({ product_id: 0, quantity: 1, unit_code: "unit", unit_price: 0, discount_percent: 0, tax_percent: 0 });
const preview = (line: SalesDraftLine) => {
  const net = Math.round(line.quantity * line.unit_price * (1 - line.discount_percent / 100) * 100) / 100;
  return net + Math.round(net * line.tax_percent) / 100;
};

export default function SalesOrderEditorModal({ record, onClose, onSaved }: {
  record: SalesDocument | null; onClose: () => void; onSaved: (id: number) => void;
}) {
  const [client, setClient] = useState<SalesClient | null>(record?.client_id ? { id: record.client_id, name: record.customer_name } : null);
  const [warehouse, setWarehouse] = useState(record?.warehouse_id ?? 0);
  const [day, setDay] = useState(record?.order_date ?? today());
  const [currency, setCurrency] = useState(record?.currency_code ?? "EUR");
  const [reference, setReference] = useState(record?.reference ?? "");
  const [notes, setNotes] = useState(record?.notes ?? "");
  const [address, setAddress] = useState<number | null>(null);
  const [addresses, setAddresses] = useState<ClientAddress[]>([]);
  const [lines, setLines] = useState<SalesDraftLine[]>(record ? record.lines.map(l => ({
    product_id: l.product_id, quantity: Number(l.requested_qty), unit_code: l.unit_code,
    unit_price: Number(l.unit_price), discount_percent: Number(l.discount_percent), tax_percent: Number(l.tax_percent),
  })) : [blankLine()]);
  const [warehouses, setWarehouses] = useState<InventoryWarehouse[]>([]);
  const [units, setUnits] = useState<MasterRecord[]>([]);
  const [currencies, setCurrencies] = useState<MasterRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [addressLoading, setAddressLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [dataError, setDataError] = useState("");
  const [addressError, setAddressError] = useState("");
  const key = useRef({ fingerprint: "", value: "" });
  const busy = useRef(false);
  useEffect(() => {
    let alive = true;
    void Promise.all([fetchInventoryWarehouses(), fetchMasterRecords("units"), fetchMasterRecords("currencies")])
      .then(([w,u,c]) => { if (alive) { setWarehouses(w.filter(item => item.is_active)); setUnits(u); setCurrencies(c); } })
      .catch(err => { if (alive) setDataError(String(err)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    let alive = true;
    setAddresses([]); setAddress(null); setAddressError("");
    if (!client) return;
    setAddressLoading(true);
    void fetchClientAddresses(client.id).then(rows => {
      if (alive) {
        setAddresses(rows);
        if (record?.client_id === client.id && record.address_snapshot?.id) {
          setAddress(rows.find(row => row.global_address_id === Number(record.address_snapshot?.id))?.id ?? null);
        }
      }
    }).catch(err => { if (alive) setAddressError(String(err)); })
      .finally(() => { if (alive) setAddressLoading(false); });
    return () => { alive = false; };
  }, [client?.id, record]);
  const changeLine = (index: number, values: Partial<SalesDraftLine>) => setLines(rows => rows.map((row, i) => i === index ? { ...row, ...values } : row));
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy.current) return;
    if (!client || !warehouse || lines.some(l => !l.product_id)) { setError("Selecciona cliente, bodega y todos los productos."); return; }
    const payload = { client_id: client.id, warehouse_id: warehouse, address_association_id: address, order_date: day, currency_code: currency, reference, notes, lines };
    const fingerprint = JSON.stringify(payload);
    if (fingerprint !== key.current.fingerprint) key.current = { fingerprint, value: crypto.randomUUID() };
    busy.current = true; setSaving(true); setError("");
    try { const result = await saveSalesOrder({ ...payload, operation_key: key.current.value }, record?.id); onSaved(result.id); }
    catch (err) { setError(String(err)); }
    finally { busy.current = false; setSaving(false); }
  };
  return <SalesModal title={record ? "Editar pedido de venta" : "Agregar pedido de venta"} saving={saving} onClose={onClose}>
    {(error || dataError || addressError) && <p className="error-line" role="alert">{error || dataError || addressError}</p>}
    {loading && <p role="status">Cargando maestros…</p>}
    <form className="stack" onSubmit={event => void submit(event)}>
      <fieldset disabled={saving || loading} className="sales-fields">
        <div className="inventory-crud-grid">
          <ClientCombobox selected={client} disabled={saving} onSelect={setClient} />
          <label className="field-group">Bodega<select required value={warehouse || ""} onChange={e => setWarehouse(Number(e.target.value))}>
            <option value="">Seleccionar bodega</option>{warehouses.map(w => <option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}
          </select></label>
          <label className="field-group">Dirección del cliente<select disabled={addressLoading} value={address ?? ""} onChange={e => setAddress(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Sin dirección</option>{addresses.map(a => <option key={a.id} value={a.id}>{a.address_type} · {a.address_line_1}, {a.city}</option>)}
          </select></label>
          <label className="field-group">Fecha<input type="date" required value={day} onChange={e => setDay(e.target.value)} /></label>
          <label className="field-group">Moneda<select value={currency} required onChange={e => setCurrency(e.target.value)}>
            {currencies.map(c => <option key={c.id} value={String(c.iso_code)}>{String(c.iso_code)} · {String(c.name)}</option>)}
          </select></label>
          <label className="field-group">Referencia<input maxLength={200} value={reference} onChange={e => setReference(e.target.value)} /></label>
        </div>
        <h4>Líneas del pedido</h4>
        <p className="muted">Los importes están en la moneda seleccionada. El servidor valida los totales. No se reserva stock al guardar.</p>
        {lines.map((line, index) => <div className="sales-line-editor" key={index}>
          <ProductCombobox selectedId={line.product_id} disabled={saving} onSelect={p => changeLine(index, { product_id: p.pk_product })} />
          <div className="sales-line-values">
            <label>Cantidad<input required type="number" min="0.0001" step="0.0001" value={line.quantity} onChange={e => changeLine(index, { quantity: Number(e.target.value) })} /></label>
            <label>Unidad<select value={line.unit_code} onChange={e => changeLine(index, { unit_code: e.target.value })}>{units.map(u => <option key={u.id} value={String(u.code)}>{String(u.code)}</option>)}</select></label>
            <label>Precio<input required type="number" min="0" step="0.0001" value={line.unit_price} onChange={e => changeLine(index, { unit_price: Number(e.target.value) })} /></label>
            <label>Descuento %<input type="number" min="0" max="100" step="0.0001" value={line.discount_percent} onChange={e => changeLine(index, { discount_percent: Number(e.target.value) })} /></label>
            <label>Impuesto %<input type="number" min="0" max="100" step="0.0001" value={line.tax_percent} onChange={e => changeLine(index, { tax_percent: Number(e.target.value) })} /></label>
            <button type="button" className="danger-btn" disabled={lines.length === 1} onClick={() => setLines(rows => rows.filter((_,i) => i !== index))}>Quitar línea</button>
          </div>
        </div>)}
        <button type="button" className="chip-btn" onClick={() => setLines(rows => [...rows, blankLine()])}>Agregar línea</button>
        <label className="field-group">Notas<textarea maxLength={2000} value={notes} onChange={e => setNotes(e.target.value)} /></label>
        <p>Previsualización del total: <strong>{lines.reduce((sum,l) => sum + preview(l),0).toFixed(2)} {currency}</strong></p>
      </fieldset>
      <div className="actions-row"><button className="primary-btn" type="submit" disabled={saving || loading || addressLoading || Boolean(dataError || addressError)}>{saving ? "Guardando…" : "Guardar borrador"}</button>
        <button className="chip-btn" type="button" disabled={saving} onClick={onClose}>Cancelar</button></div>
    </form>
  </SalesModal>;
}
