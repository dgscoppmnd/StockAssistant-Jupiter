import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  configureInventoryProduct,
  confirmInventoryReceipt,
  createWarehouse,
  fetchInventoryDashboard,
  transferInventoryStock,
} from "../api";
import type {
  InventoryDashboard,
  InventoryLinePayload,
  InventoryOperationResponse,
  InventoryProductConfigPayload,
  InventoryWarehousePayload,
} from "../types";

const emptyWarehouse: InventoryWarehousePayload = {
  code: "",
  name: "",
  description: "",
  is_active: true,
};

const emptyProductConfig: InventoryProductConfigPayload = {
  product_id: 0,
  base_unit_code: "unit",
  reorder_point: 0,
  reorder_quantity: 0,
  allow_negative_stock: false,
};

type StockOrderLine = InventoryLinePayload & { id: number };

const createOrderLine = (id: number, productId = 0, unitCode = "unit"): StockOrderLine => ({
  id,
  product_id: productId,
  quantity: 1,
  unit_code: unitCode,
  unit_price: 0,
  currency_code: "EUR",
  exchange_rate: 1,
});

export default function InventoryPage() {
  const [dashboard, setDashboard] = useState<InventoryDashboard | null>(null);
  const [warehouseForm, setWarehouseForm] = useState<InventoryWarehousePayload>(emptyWarehouse);
  const [productConfig, setProductConfig] = useState<InventoryProductConfigPayload>(emptyProductConfig);
  const [stockOrderSupplier, setStockOrderSupplier] = useState("");
  const [stockOrderSupplierCode, setStockOrderSupplierCode] = useState("");
  const [stockOrderNumber, setStockOrderNumber] = useState("");
  const [stockOrderWarehouseId, setStockOrderWarehouseId] = useState(0);
  const [stockOrderNotes, setStockOrderNotes] = useState("");
  const [stockOrderLines, setStockOrderLines] = useState<StockOrderLine[]>([createOrderLine(1)]);
  const [status, setStatus] = useState("Cargando inventario...");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadDashboard = useCallback(async () => {
    try {
      const data = await fetchInventoryDashboard();
      setDashboard(data);
      setStatus("Inventario sincronizado.");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el inventario");
      setStatus("No fue posible cargar el dashboard.");
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (!dashboard) return;

    const firstStockItem = dashboard.stock_snapshot[0];
    setStockOrderWarehouseId((current) => current || dashboard.warehouses[0]?.id || 0);
    setStockOrderLines((current) => current.map((line) => (
      line.product_id || !firstStockItem
        ? line
        : { ...line, product_id: firstStockItem.product_id, unit_code: firstStockItem.base_unit_code }
    )));
  }, [dashboard]);

  const runOperation = async (operation: Promise<InventoryOperationResponse>, message: string) => {
    setBusy(true);
    setError("");
    try {
      const result = await operation;
      setStatus(`${message} Documento ${result.document_number} procesado.`);
      await loadDashboard();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Operacion no completada");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const onCreateWarehouse = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await createWarehouse(warehouseForm);
      setWarehouseForm(emptyWarehouse);
      setStatus("Bodega creada correctamente.");
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear la bodega");
    } finally {
      setBusy(false);
    }
  };

  const onConfigureProduct = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await configureInventoryProduct(productConfig);
      setProductConfig(emptyProductConfig);
      setStatus("Configuracion de inventario guardada.");
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la configuracion");
    } finally {
      setBusy(false);
    }
  };

  const onSubmitStockOrder = async (event: FormEvent) => {
    event.preventDefault();
    const invalidLine = stockOrderLines.some((line) => !line.product_id || line.quantity <= 0 || !line.unit_code || line.unit_price === undefined || line.unit_price < 0);
    if (!stockOrderWarehouseId || !stockOrderSupplier.trim() || invalidLine) {
      setError("Indica una bodega, un proveedor y lineas con producto, cantidad y precio validos.");
      return;
    }

    const completed = await runOperation(
      confirmInventoryReceipt({
        warehouse_id: stockOrderWarehouseId,
        supplier_name: stockOrderSupplier.trim(),
        supplier_code: stockOrderSupplierCode.trim() || undefined,
        purchase_order_number: stockOrderNumber.trim() || undefined,
        user_name: "frontend",
        notes: stockOrderNotes.trim() || undefined,
        lines: stockOrderLines.map(({ id: _id, ...line }) => line),
      }),
      "Pedido de stock recibido."
    );
    if (!completed) return;

    setStockOrderSupplier("");
    setStockOrderSupplierCode("");
    setStockOrderNumber("");
    setStockOrderNotes("");
    setStockOrderLines([createOrderLine(Date.now(), firstProductId)]);
  };

  const updateStockOrderLine = (id: number, changes: Partial<StockOrderLine>) => {
    setStockOrderLines((current) => current.map((line) => line.id === id ? { ...line, ...changes } : line));
  };

  const firstWarehouseId = dashboard?.warehouses?.[0]?.id ?? 0;
  const secondWarehouseId = dashboard?.warehouses?.[1]?.id ?? firstWarehouseId;
  const firstProductId = dashboard?.stock_snapshot?.[0]?.product_id ?? 0;

  return (
    <div className="grid">
      <section className="card">
        <p className="section-label">Inventario · Dashboard operativo</p>
        <h3>Visibilidad de stock por bodega</h3>
        <div className="quick-row">
          <div className="inventory-stat-card">
            <span>Productos</span>
            <strong>{dashboard?.total_products ?? 0}</strong>
          </div>
          <div className="inventory-stat-card">
            <span>Bodegas</span>
            <strong>{dashboard?.total_warehouses ?? 0}</strong>
          </div>
          <div className="inventory-stat-card">
            <span>Stock fisico</span>
            <strong>{dashboard?.total_stock_units ?? 0}</strong>
          </div>
          <div className="inventory-stat-card">
            <span>Disponible</span>
            <strong>{dashboard?.total_available_units ?? 0}</strong>
          </div>
          <div className="inventory-stat-card">
            <span>Bajo minimo</span>
            <strong>{dashboard?.low_stock_items ?? 0}</strong>
          </div>
        </div>
        <p className="status-line">{status}</p>
        {error && <p className="error-line">{error}</p>}
      </section>

      <section className="grid two-columns">
        <article className="card stock-order-card">
          <p className="section-label">Reposicion de inventario</p>
          <h3>Crear pedido de stock</h3>
          <p className="muted">Al confirmarlo, se registra la recepcion, se crea la orden de compra y se actualiza el stock de la bodega.</p>
          <form className="stack" onSubmit={onSubmitStockOrder}>
            <div className="stock-order-meta">
              <div className="field-group">
                <label className="input-label" htmlFor="stock-order-supplier">Proveedor</label>
                <input id="stock-order-supplier" placeholder="Nombre del proveedor" required value={stockOrderSupplier} onChange={(event) => setStockOrderSupplier(event.target.value)} />
              </div>
              <div className="field-group">
                <label className="input-label" htmlFor="stock-order-warehouse">Bodega de destino</label>
                <select id="stock-order-warehouse" required value={stockOrderWarehouseId || ""} onChange={(event) => setStockOrderWarehouseId(Number(event.target.value))}>
                  <option value="">Selecciona una bodega</option>
                  {(dashboard?.warehouses ?? []).map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.name} ({warehouse.code})</option>)}
                </select>
              </div>
              <div className="field-group">
                <label className="input-label" htmlFor="stock-order-number">N. pedido</label>
                <input id="stock-order-number" placeholder="Se genera automaticamente" value={stockOrderNumber} onChange={(event) => setStockOrderNumber(event.target.value)} />
              </div>
              <div className="field-group">
                <label className="input-label" htmlFor="stock-order-supplier-code">Codigo proveedor</label>
                <input id="stock-order-supplier-code" placeholder="Opcional" value={stockOrderSupplierCode} onChange={(event) => setStockOrderSupplierCode(event.target.value)} />
              </div>
            </div>

            <div className="stock-order-lines" aria-label="Lineas del pedido">
              <div className="stock-order-line stock-order-line-header" aria-hidden="true"><span>Producto</span><span>Cantidad</span><span>Unidad</span><span>Precio</span><span /></div>
              {stockOrderLines.map((line) => (
                <div className="stock-order-line" key={line.id}>
                  <label><span>Producto</span><input aria-label="ID de producto" list="inventory-products" min="1" required type="number" value={line.product_id || ""} onChange={(event) => updateStockOrderLine(line.id, { product_id: Number(event.target.value) })} /></label>
                  <label><span>Cantidad</span><input aria-label="Cantidad" min="0.01" required step="any" type="number" value={line.quantity} onChange={(event) => updateStockOrderLine(line.id, { quantity: Number(event.target.value) })} /></label>
                  <label><span>Unidad</span><input aria-label="Unidad" required value={line.unit_code} onChange={(event) => updateStockOrderLine(line.id, { unit_code: event.target.value })} /></label>
                  <label><span>Precio</span><input aria-label="Precio unitario" min="0" required step="any" type="number" value={line.unit_price ?? 0} onChange={(event) => updateStockOrderLine(line.id, { unit_price: Number(event.target.value) })} /></label>
                  <button aria-label="Eliminar linea" className="chip-btn danger" disabled={stockOrderLines.length === 1} type="button" onClick={() => setStockOrderLines((current) => current.filter((item) => item.id !== line.id))}>Eliminar</button>
                </div>
              ))}
            </div>
            <datalist id="inventory-products">
              {(dashboard?.stock_snapshot ?? []).map((item) => <option key={item.product_id} value={item.product_id} label={item.product_name} />)}
            </datalist>
            <div className="actions-row">
              <button className="chip-btn" type="button" onClick={() => setStockOrderLines((current) => [...current, createOrderLine(Date.now() + current.length)])}>Agregar linea</button>
              <button className="primary-btn" disabled={busy || !dashboard?.warehouses.length} type="submit">Confirmar pedido y entrada</button>
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="stock-order-notes">Notas</label>
              <textarea id="stock-order-notes" placeholder="Observaciones opcionales" rows={2} value={stockOrderNotes} onChange={(event) => setStockOrderNotes(event.target.value)} />
            </div>
          </form>
        </article>

        <article className="card">
          <p className="section-label">Setup minimo</p>
          <h3>Crear bodega</h3>
          <form className="stack" onSubmit={onCreateWarehouse}>
            <div className="field-group">
              <label className="input-label" htmlFor="warehouse-code">Codigo</label>
              <input
                id="warehouse-code"
                placeholder="Ejemplo: MADRID"
                value={warehouseForm.code}
                onChange={(event) => setWarehouseForm((prev) => ({ ...prev, code: event.target.value }))}
              />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="warehouse-name">Nombre</label>
              <input
                id="warehouse-name"
                placeholder="Nombre de la bodega"
                value={warehouseForm.name}
                onChange={(event) => setWarehouseForm((prev) => ({ ...prev, name: event.target.value }))}
              />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="warehouse-description">Descripcion</label>
              <input
                id="warehouse-description"
                placeholder="Descripcion opcional"
                value={warehouseForm.description ?? ""}
                onChange={(event) => setWarehouseForm((prev) => ({ ...prev, description: event.target.value }))}
              />
            </div>
            <button className="primary-btn" disabled={busy} type="submit">Guardar bodega</button>
          </form>
        </article>

        <article className="card">
          <p className="section-label">Producto base</p>
          <h3>Configurar unidad y punto de pedido</h3>
          <form className="stack" onSubmit={onConfigureProduct}>
            <div className="field-group">
              <label className="input-label" htmlFor="product-id">ID de producto</label>
              <input
                id="product-id"
                placeholder="Ejemplo: 123"
                type="number"
                value={productConfig.product_id || ""}
                onChange={(event) => setProductConfig((prev) => ({ ...prev, product_id: Number(event.target.value) }))}
              />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="base-unit-code">Unidad base</label>
              <input
                id="base-unit-code"
                placeholder="Ejemplo: unit"
                value={productConfig.base_unit_code}
                onChange={(event) => setProductConfig((prev) => ({ ...prev, base_unit_code: event.target.value }))}
              />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="reorder-point">Punto de pedido</label>
              <input
                id="reorder-point"
                placeholder="Unidades minimas"
                type="number"
                value={productConfig.reorder_point}
                onChange={(event) => setProductConfig((prev) => ({ ...prev, reorder_point: Number(event.target.value) }))}
              />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="reorder-quantity">Cantidad sugerida</label>
              <input
                id="reorder-quantity"
                placeholder="Unidades por reposicion"
                type="number"
                value={productConfig.reorder_quantity}
                onChange={(event) => setProductConfig((prev) => ({ ...prev, reorder_quantity: Number(event.target.value) }))}
              />
            </div>
            <label className="field-label">
              <input
                checked={productConfig.allow_negative_stock}
                onChange={(event) => setProductConfig((prev) => ({ ...prev, allow_negative_stock: event.target.checked }))}
                type="checkbox"
              />
              Permitir stock negativo
            </label>
            <button className="primary-btn" disabled={busy} type="submit">Guardar configuracion</button>
          </form>
        </article>
      </section>

      <section className="grid two-columns">
        <article className="card">
          <p className="section-label">Operaciones</p>
          <h3>Acciones rapidas de prueba</h3>
          <p className="muted">
            Usan el primer producto y las primeras bodegas visibles para validar recepcion y transferencia minima.
          </p>
          <div className="quick-row">
            <button
              className="primary-btn"
              disabled={busy || !firstWarehouseId || !firstProductId}
              type="button"
              onClick={() =>
                void runOperation(
                  confirmInventoryReceipt({
                    warehouse_id: firstWarehouseId,
                    supplier_name: "Proveedor demo",
                    user_name: "frontend",
                    lines: [{ product_id: firstProductId, quantity: 5, unit_code: "unit", unit_price: 1, exchange_rate: 1 }],
                  }),
                  "Recepcion registrada."
                )
              }
            >
              Recepcion demo
            </button>
            <button
              className="chip-btn"
              disabled={busy || !firstWarehouseId || !secondWarehouseId || !firstProductId || firstWarehouseId === secondWarehouseId}
              type="button"
              onClick={() =>
                void runOperation(
                  transferInventoryStock({
                    source_warehouse_id: firstWarehouseId,
                    destination_warehouse_id: secondWarehouseId,
                    user_name: "frontend",
                    reason: "transferencia demo",
                    lines: [{ product_id: firstProductId, quantity: 1, unit_code: "unit", unit_price: 0, exchange_rate: 1 }],
                  }),
                  "Transferencia registrada."
                )
              }
            >
              Transferencia demo
            </button>
          </div>
        </article>

        <article className="card">
          <p className="section-label">Bodegas</p>
          <h3>Listado actual</h3>
          <div className="inventory-list">
            {(dashboard?.warehouses ?? []).map((warehouse) => (
              <div className="inventory-list-item" key={warehouse.id}>
                <strong>{warehouse.name}</strong>
                <span>{warehouse.code}</span>
              </div>
            ))}
            {(dashboard?.warehouses?.length ?? 0) === 0 && <p className="muted">Aun no hay bodegas creadas.</p>}
          </div>
        </article>
      </section>

      <section className="grid two-columns">
        <article className="card">
          <p className="section-label">Stock disponible</p>
          <h3>Snapshot por producto y bodega</h3>
          <div className="inventory-table">
            {(dashboard?.stock_snapshot ?? []).map((item) => (
              <div className="inventory-table-row" key={`${item.product_id}-${item.warehouse_id}`}>
                <span>{item.product_name}</span>
                <span>{item.warehouse_name}</span>
                <span>{item.available_qty} {item.base_unit_code}</span>
              </div>
            ))}
            {(dashboard?.stock_snapshot?.length ?? 0) === 0 && <p className="muted">Todavia no hay stock cargado.</p>}
          </div>
        </article>

        <article className="card">
          <p className="section-label">Movimientos</p>
          <h3>Ultimos registros</h3>
          <div className="inventory-table">
            {(dashboard?.recent_movements ?? []).map((movement) => (
              <div className="inventory-table-row" key={movement.id}>
                <span>{movement.movement_type}</span>
                <span>Producto #{movement.product_id}</span>
                <span>{movement.quantity_signed} {movement.base_unit_code}</span>
              </div>
            ))}
            {(dashboard?.recent_movements?.length ?? 0) === 0 && <p className="muted">No hay movimientos todavia.</p>}
          </div>
        </article>
      </section>
    </div>
  );
}
