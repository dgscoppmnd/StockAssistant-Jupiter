import {useCallback,useEffect,useId,useState,type FormEvent} from 'react';
import {automationRequest,confirmInventoryReceipt,fetchMasterRecords} from '../../api';
import type {InventoryDashboard,InventoryLinePayload,InventoryOperationResponse,MasterRecord} from '../../types';
import {stockDraftLines,type StockOrderDraftGroup} from '../../utils/stockOrderDrafts';
import InventoryCrudCard from './InventoryCrudCard';
import InventoryCardInfo from './InventoryCardInfo';
import SectionIcon from './SectionIcon';
import SupplierCombobox from './SupplierCombobox';
import ProductCombobox from './ProductCombobox';

type StockOrderLine=InventoryLinePayload&{id:number};
type Props={dashboard:InventoryDashboard|null;busy:boolean;setBusy:(value:boolean)=>void;setError:(value:string)=>void;
  runOperation:(operation:Promise<InventoryOperationResponse>,message:string)=>Promise<boolean>;
  initialDraft?:StockOrderDraftGroup;recommendationId?:number;onConfirmed?:()=>Promise<void>};
const createOrderLine = (id: number, productId = 0, unitCode = "unit"): StockOrderLine => ({
  id,
  product_id: productId,
  quantity: 1,
  unit_code: unitCode,
  unit_price: 0,
  currency_code: "EUR",
  exchange_rate: 1,
});


export default function StockOrderCard({dashboard,busy,setBusy,setError,runOperation,initialDraft,recommendationId,onConfirmed}:Props){
  const prefix=useId();
  const [stockOrderSupplier, setStockOrderSupplier] = useState(initialDraft?.supplier_name ?? "");
  const [stockOrderSupplierCode, setStockOrderSupplierCode] = useState(initialDraft?.supplier_code ?? "");
  const [suppliers, setSuppliers] = useState<MasterRecord[]>([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(initialDraft?.supplier_id ?? null);
  const [creatingSupplier, setCreatingSupplier] = useState(false);
  const [suppliersLoading, setSuppliersLoading] = useState(true);
  const [suppliersError, setSuppliersError] = useState("");
  const [stockOrderNumber, setStockOrderNumber] = useState(initialDraft?.purchase_order_number ?? "");
  const [stockOrderWarehouseId, setStockOrderWarehouseId] = useState(initialDraft?.warehouse_id ?? 0);
  const [stockOrderNotes, setStockOrderNotes] = useState(initialDraft?.notes ?? "");
  const [stockOrderLines, setStockOrderLines] = useState<StockOrderLine[]>(stockDraftLines(initialDraft) ?? [createOrderLine(1)]);
  const loadSuppliers = useCallback(async () => {
    setSuppliersLoading(true);
    setSuppliersError("");
    try {
      setSuppliers(await fetchMasterRecords("suppliers"));
    } catch (err) {
      setSuppliersError(err instanceof Error ? err.message : "No se pudieron cargar los proveedores.");
    } finally {
      setSuppliersLoading(false);
    }
  }, []);

  useEffect(() => { void loadSuppliers(); }, [loadSuppliers]);

  useEffect(() => {
    if (!dashboard) return;

    const firstStockItem = dashboard.stock_snapshot[0];
    setStockOrderWarehouseId((current) => current || dashboard.warehouses[0]?.id || 0);
    setStockOrderLines((current) =>
      current.map((line) =>
        line.product_id || !firstStockItem
          ? line
          : { ...line, product_id: firstStockItem.product_id, unit_code: firstStockItem.base_unit_code },
      ),
    );
  }, [dashboard]);


  const firstProductId=dashboard?.stock_snapshot?.[0]?.product_id??0;
  const submitReceipt=(payload:Parameters<typeof confirmInventoryReceipt>[0])=>
    initialDraft&&recommendationId
      ?automationRequest<InventoryOperationResponse>(`/stock-order-drafts/${recommendationId}/${initialDraft.key}/confirm`,'POST',payload)
      :confirmInventoryReceipt(payload);
  const onSubmitStockOrder = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || suppliersLoading || suppliersError) return;
    const invalidLine = stockOrderLines.some(
      (line) => !Number.isInteger(line.product_id) || line.product_id <= 0 || line.quantity <= 0 || !line.unit_code || line.unit_price === undefined || line.unit_price < 0,
    );

    if (!stockOrderWarehouseId || !stockOrderSupplier.trim() || (!selectedSupplierId && !creatingSupplier) || invalidLine) {
      setError("Indica una bodega, un proveedor y lineas con producto, cantidad y precio validos.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      if (initialDraft && new Date(initialDraft.valid_until).getTime() <= Date.now()) {
        throw new Error("La oferta ha caducado; actualízala en agentes/control.");
      }
      // Recheck the catalog before allowing the receipt endpoint to create a supplier.
      const currentSuppliers = await fetchMasterRecords("suppliers");
      setSuppliers(currentSuppliers);
      const name = stockOrderSupplier.trim();
      const code = stockOrderSupplierCode.trim();
      const existing = selectedSupplierId
        ? currentSuppliers.find((supplier) => supplier.id === selectedSupplierId)
        : currentSuppliers.find((supplier) => String(supplier.name).trim().toLowerCase() === name.toLowerCase());
      if (selectedSupplierId && !existing) {
        setError("El proveedor seleccionado ya no existe. Selecciona otro proveedor o crea uno nuevo.");
        return;
      }
      if (!existing && code && currentSuppliers.some((supplier) => String(supplier.supplier_code ?? "").toLowerCase() === code.toLowerCase())) {
        setError("Ese código ya pertenece a un proveedor. Selecciónalo en el buscador.");
        return;
      }
      if (!existing && !window.confirm(`¿Estás seguro de crear el nuevo proveedor «${name}»${code ? ` con código «${code}»` : ""} y confirmar el pedido?`)) return;

      const completed = await runOperation(
        submitReceipt({
          warehouse_id: stockOrderWarehouseId,
          supplier_name: existing ? String(existing.name) : name,
          supplier_code: existing ? String(existing.supplier_code ?? "") || undefined : code || undefined,
          purchase_order_number: stockOrderNumber.trim() || undefined,
          user_name: "frontend",
          notes: stockOrderNotes.trim() || undefined,
          lines: stockOrderLines.map(({ id: _id, ...line }) => line),
        }),
        "Pedido de stock recibido.",
      );
      if (!completed) return;

      setStockOrderSupplier("");
      setStockOrderSupplierCode("");
      setSelectedSupplierId(null);
      setCreatingSupplier(false);
      setStockOrderNumber("");
      setStockOrderNotes("");
      setStockOrderLines([createOrderLine(Date.now(), firstProductId)]);
      await loadSuppliers();
      await onConfirmed?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo comprobar el proveedor.");
    } finally {
      setBusy(false);
    }
  };

  const updateStockOrderLine = (id: number, changes: Partial<StockOrderLine>) => {
    setStockOrderLines((current) => current.map((line) => (line.id === id ? { ...line, ...changes } : line)));
  };

  return (
        <InventoryCrudCard
          className="stock-order-card"
          sectionLabel="Reposicion de inventario"
          title="Crear pedido de stock"
          titleInfo={<InventoryCardInfo topic="receipt" />}
          titleIcon={<SectionIcon kind="cart" />}
          description="Al confirmarlo, se registra la recepcion, se crea la orden de compra y se actualiza el stock de la bodega."
          onSubmit={onSubmitStockOrder}
          footer={
            <>
              <div className="actions-row">
                <button
                  className="chip-btn"
                  type="button"
                  onClick={() => setStockOrderLines((current) => [...current, createOrderLine(Date.now() + current.length)])}
                >
                  Agregar linea
                </button>
                <button className="primary-btn" disabled={busy || suppliersLoading || Boolean(suppliersError) || !dashboard?.warehouses.length} type="submit">
                  Confirmar pedido y entrada
                </button>
              </div>
              <div className="field-group">
                <label className="input-label" htmlFor={`${prefix}-notes`}>Notas</label>
                <textarea
                  id={`${prefix}-notes`}
                  placeholder="Observaciones opcionales"
                  rows={2}
                  value={stockOrderNotes}
                  onChange={(event) => setStockOrderNotes(event.target.value)}
                />
              </div>
            </>
          }
        >
          <div className="stock-order-meta">
            <SupplierCombobox suppliers={suppliers} selectedId={selectedSupplierId} creating={creatingSupplier}
              disabled={busy || suppliersLoading || Boolean(suppliersError)} loading={suppliersLoading}
              onSelect={(supplier) => {
                setSelectedSupplierId(supplier.id);
                setCreatingSupplier(false);
                setStockOrderSupplier(String(supplier.name));
                setStockOrderSupplierCode(String(supplier.supplier_code ?? ""));
              }}
              onCreate={(name) => {
                setSelectedSupplierId(null);
                setCreatingSupplier(true);
                setStockOrderSupplier(name);
                setStockOrderSupplierCode("");
              }} />
            <div className="field-group">
              <label className="input-label" htmlFor={`${prefix}-warehouse`}>Bodega de destino</label>
              <select
                id={`${prefix}-warehouse`}
                required
                value={stockOrderWarehouseId || ""}
                onChange={(event) => setStockOrderWarehouseId(Number(event.target.value))}
              >
                <option value="">Selecciona una bodega</option>
                {(dashboard?.warehouses ?? []).map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {warehouse.name} ({warehouse.code})
                  </option>
                ))}
              </select>
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor={`${prefix}-number`}>N. pedido</label>
              <input
                id={`${prefix}-number`}
                placeholder="Se genera automaticamente"
                value={stockOrderNumber}
                onChange={(event) => setStockOrderNumber(event.target.value)}
              />
            </div>
          </div>
          {suppliersError && <p className="error-line" role="alert">{suppliersError} <button className="chip-btn" type="button" onClick={() => void loadSuppliers()}>Reintentar</button></p>}
          {creatingSupplier && <div className="stock-order-meta">
            <div className="field-group">
              <label className="input-label" htmlFor={`${prefix}-new-supplier`}>Nombre del nuevo proveedor</label>
              <input id={`${prefix}-new-supplier`} required maxLength={200} disabled={busy}
                value={stockOrderSupplier} onChange={(event) => setStockOrderSupplier(event.target.value)} />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor={`${prefix}-supplier-code`}>Codigo proveedor</label>
              <input
                id={`${prefix}-supplier-code`}
                placeholder="Opcional"
                maxLength={80}
                disabled={busy}
                value={stockOrderSupplierCode}
                onChange={(event) => setStockOrderSupplierCode(event.target.value)}
              />
            </div>
          </div>}

          <div className="stock-order-lines" aria-label="Lineas del pedido">
            <div className="stock-order-line stock-order-line-header" aria-hidden="true">
              <span>Producto · Código y nombre</span>
              <span>Cantidad</span>
              <span>Unidad</span>
              <span>Precio</span>
              <span />
            </div>
            {stockOrderLines.map((line) => (
              <div className="stock-order-line" key={line.id}>
                <ProductCombobox selectedId={line.product_id}
                  disabled={busy}
                  onSelect={(product) => updateStockOrderLine(line.id, {
                    product_id: product.pk_product,
                    unit_code: dashboard?.stock_snapshot.find((item) => item.product_id === product.pk_product)?.base_unit_code ?? "unit",
                  })} />
                <label>
                  <span>Cantidad</span>
                  <input
                    aria-label="Cantidad"
                    min="0.01"
                    required
                    step="any"
                    type="number"
                    value={line.quantity}
                    onChange={(event) => updateStockOrderLine(line.id, { quantity: Number(event.target.value) })}
                  />
                </label>
                <label>
                  <span>Unidad</span>
                  <input
                    aria-label="Unidad"
                    required
                    value={line.unit_code}
                    onChange={(event) => updateStockOrderLine(line.id, { unit_code: event.target.value })}
                  />
                </label>
                <label>
                  <span>Precio</span>
                  <input
                    aria-label="Precio unitario"
                    min="0"
                    required
                    step="any"
                    type="number"
                    value={line.unit_price ?? 0}
                    onChange={(event) => updateStockOrderLine(line.id, { unit_price: Number(event.target.value) })}
                  />
                </label>
                <button
                  aria-label="Eliminar linea"
                  className="chip-btn danger"
                  disabled={stockOrderLines.length === 1}
                  type="button"
                  onClick={() => setStockOrderLines((current) => current.filter((item) => item.id !== line.id))}
                >
                  Eliminar
                </button>
              </div>
            ))}
          </div>
        </InventoryCrudCard>
  );
}
