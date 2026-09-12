import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  configureInventoryProduct,
  confirmInventoryReceipt,
  createWarehouse,
  fetchInventoryDashboard,
  fetchMasterRecords,
  fetchProducts,
  transferInventoryStock,
} from "../api";
import type {
  InventoryDashboard,
  InventoryLinePayload,
  InventoryMovement,
  InventoryOperationResponse,
  InventoryProductConfigPayload,
  InventoryStockItem,
  InventoryWarehouse,
  InventoryWarehousePayload,
  MasterRecord,
  Product,
} from "../types";
import InventoryCrudCard from "./components/InventoryCrudCard";
import ProductConfigModal from "./components/ProductConfigModal";
import SectionIcon from "./components/SectionIcon";
import SupplierCombobox from "./components/SupplierCombobox";
import ProductCombobox from "./components/ProductCombobox";
import WarehouseCreateModal from "./components/WarehouseCreateModal";

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

type StockOrderListRow = {
  id: string;
  document_number: string;
  warehouse_name: string;
  lines_count: number;
  total_qty: number;
  created_at: string;
  operation_key: string;
};

type ProductConfigRow = {
  id: number;
  product_id: number;
  product_name: string;
  base_unit_code: string;
  reorder_point: number;
  reorder_quantity: number;
  available_qty: number;
  warehouses: string;
};

type MovementTableRow = InventoryMovement & {
  product_label: string;
  warehouse_name: string;
  destination_warehouse_name: string;
  document_number: string;
};

type SnapshotTableRow = InventoryStockItem & { id: string };

const createOrderLine = (id: number, productId = 0, unitCode = "unit"): StockOrderLine => ({
  id,
  product_id: productId,
  quantity: 1,
  unit_code: unitCode,
  unit_price: 0,
  currency_code: "EUR",
  exchange_rate: 1,
});

function formatDateTime(raw?: string | null): string {
  if (!raw) return "-";
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return parsed.toLocaleString("es-ES");
}

function formatQuantity(value: number, maximumFractionDigits = 2): string {
  return Number(value).toLocaleString("es-ES", { maximumFractionDigits });
}

function buildStockOrderRows(
  movements: InventoryMovement[],
  warehouses: InventoryWarehouse[],
): StockOrderListRow[] {
  const warehouseNames = new Map(warehouses.map((warehouse) => [warehouse.id, warehouse.name]));
  const grouped = new Map<string, StockOrderListRow>();

  movements
    .filter((movement) => movement.document_type === "goods_receipt")
    .forEach((movement) => {
      const key = movement.document_id ? String(movement.document_id) : movement.operation_key;
      const current = grouped.get(key);
      const warehouseName = movement.warehouse_id ? warehouseNames.get(movement.warehouse_id) ?? `Bodega #${movement.warehouse_id}` : "-";

      if (!current) {
        grouped.set(key, {
          id: key,
          document_number: movement.document_id ? `GR-${movement.document_id}` : movement.operation_key,
          warehouse_name: warehouseName,
          lines_count: 1,
          total_qty: Number(movement.quantity_signed) || 0,
          created_at: movement.created_at,
          operation_key: movement.operation_key,
        });
        return;
      }

      current.lines_count += 1;
      current.total_qty += Number(movement.quantity_signed) || 0;
      if (new Date(movement.created_at).getTime() > new Date(current.created_at).getTime()) {
        current.created_at = movement.created_at;
      }
    });

  return Array.from(grouped.values()).sort(
    (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
  );
}

function buildProductConfigRows(snapshot: InventoryStockItem[]): ProductConfigRow[] {
  const grouped = new Map<number, ProductConfigRow>();

  snapshot.forEach((item) => {
    const current = grouped.get(item.product_id);
    if (!current) {
      grouped.set(item.product_id, {
        id: item.product_id,
        product_id: item.product_id,
        product_name: item.product_name,
        base_unit_code: item.base_unit_code,
        reorder_point: Number(item.reorder_point) || 0,
        reorder_quantity: Number(item.reorder_quantity) || 0,
        available_qty: Number(item.available_qty) || 0,
        warehouses: item.warehouse_name,
      });
      return;
    }

    current.available_qty += Number(item.available_qty) || 0;
    current.warehouses = `${current.warehouses}, ${item.warehouse_name}`;
  });

  return Array.from(grouped.values()).sort((left, right) => left.product_name.localeCompare(right.product_name, "es"));
}

export default function InventoryPage() {
  const [dashboard, setDashboard] = useState<InventoryDashboard | null>(null);
  const [warehouseForm, setWarehouseForm] = useState<InventoryWarehousePayload>(emptyWarehouse);
  const [showWarehouseModal, setShowWarehouseModal] = useState(false);
  const [productConfig, setProductConfig] = useState<InventoryProductConfigPayload>(emptyProductConfig);
  const [showProductConfigModal, setShowProductConfigModal] = useState(false);
  const [stockOrderSupplier, setStockOrderSupplier] = useState("");
  const [stockOrderSupplierCode, setStockOrderSupplierCode] = useState("");
  const [suppliers, setSuppliers] = useState<MasterRecord[]>([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(null);
  const [creatingSupplier, setCreatingSupplier] = useState(false);
  const [suppliersLoading, setSuppliersLoading] = useState(true);
  const [suppliersError, setSuppliersError] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(true);
  const [productsError, setProductsError] = useState("");
  const [stockOrderNumber, setStockOrderNumber] = useState("");
  const [stockOrderWarehouseId, setStockOrderWarehouseId] = useState(0);
  const [stockOrderNotes, setStockOrderNotes] = useState("");
  const [stockOrderLines, setStockOrderLines] = useState<StockOrderLine[]>([createOrderLine(1)]);
  const [status, setStatus] = useState("Cargando inventario...");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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

  const loadProducts = useCallback(async () => {
    setProductsLoading(true);
    setProductsError("");
    try {
      setProducts(await fetchProducts());
    } catch (err) {
      setProductsError(err instanceof Error ? err.message : "No se pudieron cargar los productos.");
    } finally {
      setProductsLoading(false);
    }
  }, []);

  useEffect(() => { void loadProducts(); }, [loadProducts]);

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
    setStockOrderLines((current) =>
      current.map((line) =>
        line.product_id || !firstStockItem
          ? line
          : { ...line, product_id: firstStockItem.product_id, unit_code: firstStockItem.base_unit_code },
      ),
    );
  }, [dashboard]);

  const firstWarehouseId = dashboard?.warehouses?.[0]?.id ?? 0;
  const secondWarehouseId = dashboard?.warehouses?.[1]?.id ?? firstWarehouseId;
  const firstProductId = dashboard?.stock_snapshot?.[0]?.product_id ?? 0;

  const warehouseRows = useMemo(
    () => (dashboard?.warehouses ?? []).map((warehouse) => ({ ...warehouse, description: warehouse.description || "-" })),
    [dashboard],
  );
  const stockOrderRows = useMemo(
    () => buildStockOrderRows(dashboard?.recent_movements ?? [], dashboard?.warehouses ?? []),
    [dashboard],
  );
  const productConfigRows = useMemo(
    () => buildProductConfigRows(dashboard?.stock_snapshot ?? []),
    [dashboard],
  );
  const movementRows = useMemo<MovementTableRow[]>(() => {
    const warehouseNames = new Map((dashboard?.warehouses ?? []).map((warehouse) => [warehouse.id, warehouse.name]));
    const productNames = new Map((dashboard?.stock_snapshot ?? []).map((item) => [item.product_id, item.product_name]));

    return (dashboard?.recent_movements ?? []).map((movement) => ({
      ...movement,
      product_label: productNames.get(movement.product_id) ?? `Producto #${movement.product_id}`,
      warehouse_name: movement.warehouse_id ? warehouseNames.get(movement.warehouse_id) ?? `Bodega #${movement.warehouse_id}` : "-",
      destination_warehouse_name: movement.warehouse_destination_id
        ? warehouseNames.get(movement.warehouse_destination_id) ?? `Bodega #${movement.warehouse_destination_id}`
        : "-",
      document_number: movement.document_id
        ? `${movement.document_type ?? "Documento"} #${movement.document_id}`
        : movement.operation_key,
    }));
  }, [dashboard]);
  const snapshotRows = useMemo<SnapshotTableRow[]>(
    () => (dashboard?.stock_snapshot ?? []).map((item) => ({ ...item, id: `${item.product_id}-${item.warehouse_id}` })),
    [dashboard],
  );

  const warehouseColumns = useMemo<any[]>(
    () => [
      { dataField: "id", text: "ID", sort: true, headerStyle: { width: "76px" } },
      { dataField: "code", text: "Codigo", sort: true },
      { dataField: "name", text: "Nombre", sort: true },
      { dataField: "description", text: "Descripcion", formatter: (value: string) => value || "-" },
      { dataField: "is_active", text: "Estado", sort: true, formatter: (value: boolean) => (value ? "Activa" : "Inactiva") },
      { dataField: "updated_at", text: "Actualizada", sort: true, formatter: (value: string) => formatDateTime(value) },
    ],
    [],
  );

  const stockOrderColumns = useMemo<any[]>(
    () => [
      { dataField: "document_number", text: "Documento", sort: true },
      { dataField: "warehouse_name", text: "Bodega", sort: true },
      { dataField: "lines_count", text: "Lineas", sort: true, headerStyle: { width: "90px" } },
      { dataField: "total_qty", text: "Cantidad", sort: true, formatter: (value: number) => formatQuantity(value) },
      { dataField: "created_at", text: "Fecha", sort: true, formatter: (value: string) => formatDateTime(value) },
      { dataField: "operation_key", text: "Operacion", formatter: (value: string) => value },
    ],
    [],
  );

  const productConfigColumns = useMemo<any[]>(
    () => [
      { dataField: "product_id", text: "Producto ID", sort: true, headerStyle: { width: "110px" } },
      { dataField: "product_name", text: "Producto", sort: true },
      { dataField: "base_unit_code", text: "Unidad base", sort: true },
      { dataField: "reorder_point", text: "Punto pedido", sort: true, formatter: (value: number) => formatQuantity(value) },
      { dataField: "reorder_quantity", text: "Cantidad sugerida", sort: true, formatter: (value: number) => formatQuantity(value) },
      { dataField: "available_qty", text: "Disponible", sort: true, formatter: (value: number) => formatQuantity(value) },
      { dataField: "warehouses", text: "Bodegas" },
    ],
    [],
  );

  const movementColumns = useMemo<any[]>(
    () => [
      { dataField: "created_at", text: "Fecha", sort: true, formatter: (value: string) => formatDateTime(value) },
      { dataField: "movement_type", text: "Tipo", sort: true },
      { dataField: "product_label", text: "Producto", sort: true },
      { dataField: "warehouse_name", text: "Bodega origen", sort: true },
      { dataField: "destination_warehouse_name", text: "Bodega destino", sort: true },
      { dataField: "quantity_signed", text: "Cantidad", sort: true, formatter: (value: number, row: MovementTableRow) => `${formatQuantity(value)} ${row.base_unit_code}` },
      { dataField: "document_number", text: "Documento", sort: true },
    ],
    [],
  );

  const snapshotColumns = useMemo<any[]>(
    () => [
      { dataField: "product_id", text: "Producto ID", sort: true, headerStyle: { width: "110px" } },
      { dataField: "product_name", text: "Producto", sort: true },
      { dataField: "warehouse_name", text: "Bodega", sort: true },
      { dataField: "physical_qty", text: "Fisico", sort: true, formatter: (value: number, row: SnapshotTableRow) => `${formatQuantity(value)} ${row.base_unit_code}` },
      { dataField: "reserved_qty", text: "Reservado", sort: true, formatter: (value: number, row: SnapshotTableRow) => `${formatQuantity(value)} ${row.base_unit_code}` },
      { dataField: "available_qty", text: "Disponible", sort: true, formatter: (value: number, row: SnapshotTableRow) => `${formatQuantity(value)} ${row.base_unit_code}` },
      { dataField: "reorder_point", text: "Punto pedido", sort: true, formatter: (value: number) => formatQuantity(value) },
    ],
    [],
  );

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

  const onCreateWarehouse = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await createWarehouse(warehouseForm);
      setWarehouseForm(emptyWarehouse);
      setShowWarehouseModal(false);
      setStatus("Bodega creada correctamente.");
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear la bodega");
    } finally {
      setBusy(false);
    }
  };

  const onConfigureProduct = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await configureInventoryProduct(productConfig);
      setProductConfig(emptyProductConfig);
      setShowProductConfigModal(false);
      setStatus("Configuracion de inventario guardada.");
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la configuracion");
    } finally {
      setBusy(false);
    }
  };

  const onSubmitStockOrder = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy || suppliersLoading || suppliersError || productsLoading || productsError) return;
    const invalidLine = stockOrderLines.some(
      (line) => !products.some((product) => product.pk_product === line.product_id) || line.quantity <= 0 || !line.unit_code || line.unit_price === undefined || line.unit_price < 0,
    );

    if (!stockOrderWarehouseId || !stockOrderSupplier.trim() || (!selectedSupplierId && !creatingSupplier) || invalidLine) {
      setError("Indica una bodega, un proveedor y lineas con producto, cantidad y precio validos.");
      return;
    }

    setBusy(true);
    setError("");
    try {
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
        confirmInventoryReceipt({
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo comprobar el proveedor.");
    } finally {
      setBusy(false);
    }
  };

  const updateStockOrderLine = (id: number, changes: Partial<StockOrderLine>) => {
    setStockOrderLines((current) => current.map((line) => (line.id === id ? { ...line, ...changes } : line)));
  };

  const openWarehouseModal = () => {
    setWarehouseForm(emptyWarehouse);
    setError("");
    setShowWarehouseModal(true);
  };

  const closeWarehouseModal = () => {
    if (busy) return;
    setShowWarehouseModal(false);
    setError("");
  };

  const openProductConfigModal = () => {
    setProductConfig(emptyProductConfig);
    setError("");
    setShowProductConfigModal(true);
  };

  const closeProductConfigModal = () => {
    if (busy) return;
    setShowProductConfigModal(false);
    setError("");
  };

  return (
    <div className="grid">
      <section className="card">
        <p className="section-label">Inventario · Dashboard operativo</p>
        <h3><SectionIcon kind="warehouse" />Visibilidad de stock por bodega</h3>
        <div className="quick-row">
          <div className="inventory-stat-card">
            <span>Productos</span>
            <strong>{formatQuantity(dashboard?.total_products ?? 0, 0)}</strong>
          </div>
          <div className="inventory-stat-card">
            <span>Bodegas</span>
            <strong>{formatQuantity(dashboard?.total_warehouses ?? 0, 0)}</strong>
          </div>
          <div className="inventory-stat-card">
            <span>Stock fisico</span>
            <strong>{formatQuantity(dashboard?.total_stock_units ?? 0, 0)}</strong>
          </div>
          <div className="inventory-stat-card">
            <span>Disponible</span>
            <strong>{formatQuantity(dashboard?.total_available_units ?? 0, 0)}</strong>
          </div>
          <div className="inventory-stat-card">
            <span>Bajo minimo</span>
            <strong>{formatQuantity(dashboard?.low_stock_items ?? 0, 0)}</strong>
          </div>
        </div>
        <p className="status-line">{status}</p>
        {error && <p className="error-line">{error}</p>}
      </section>

      <section className="grid two-columns">
        <InventoryCrudCard
          className="stock-order-card"
          sectionLabel="Reposicion de inventario"
          title="Crear pedido de stock"
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
                <button className="primary-btn" disabled={busy || suppliersLoading || Boolean(suppliersError) || productsLoading || Boolean(productsError) || !dashboard?.warehouses.length} type="submit">
                  Confirmar pedido y entrada
                </button>
              </div>
              <div className="field-group">
                <label className="input-label" htmlFor="stock-order-notes">Notas</label>
                <textarea
                  id="stock-order-notes"
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
              <label className="input-label" htmlFor="stock-order-warehouse">Bodega de destino</label>
              <select
                id="stock-order-warehouse"
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
              <label className="input-label" htmlFor="stock-order-number">N. pedido</label>
              <input
                id="stock-order-number"
                placeholder="Se genera automaticamente"
                value={stockOrderNumber}
                onChange={(event) => setStockOrderNumber(event.target.value)}
              />
            </div>
          </div>
          {suppliersError && <p className="error-line" role="alert">{suppliersError} <button className="chip-btn" type="button" onClick={() => void loadSuppliers()}>Reintentar</button></p>}
          {creatingSupplier && <div className="stock-order-meta">
            <div className="field-group">
              <label className="input-label" htmlFor="stock-order-new-supplier">Nombre del nuevo proveedor</label>
              <input id="stock-order-new-supplier" required maxLength={200} disabled={busy}
                value={stockOrderSupplier} onChange={(event) => setStockOrderSupplier(event.target.value)} />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="stock-order-supplier-code">Codigo proveedor</label>
              <input
                id="stock-order-supplier-code"
                placeholder="Opcional"
                maxLength={80}
                disabled={busy}
                value={stockOrderSupplierCode}
                onChange={(event) => setStockOrderSupplierCode(event.target.value)}
              />
            </div>
          </div>}

          {productsError && <p className="error-line" role="alert">{productsError} <button className="chip-btn" type="button" onClick={() => void loadProducts()}>Reintentar</button></p>}
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
                <ProductCombobox products={products} selectedId={line.product_id}
                  disabled={busy || Boolean(productsError)} loading={productsLoading}
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

        <InventoryCrudCard<StockOrderListRow>
          className="stock-order-card"
          sectionLabel="Reposicion de inventario"
          title="Listado de pedidos de stock"
          titleIcon={<SectionIcon kind="movement" />}
          description="Resumen de recepciones procesadas recientemente desde el dashboard de inventario."
          table={{
            keyField: "id",
            data: stockOrderRows,
            columns: stockOrderColumns,
            noDataIndication: "Aun no hay pedidos de stock registrados.",
            totalLabel: "pedidos",
            minWidth: 920,
          }}
        />
      </section>

      <section className="grid">
        <InventoryCrudCard<InventoryWarehouse & { description: string }>
          sectionLabel="Setup minimo"
          title="Listado de bodegas"
          titleIcon={<SectionIcon kind="warehouse" />}
          description="Bodegas activas e historico reciente."
          headerAction={
            <button
              className="primary-btn"
              onClick={openWarehouseModal}
              title="Alta rapida de ubicaciones fisicas para recepcion, almacenamiento y transferencia."
              type="button"
            >
              Agregar bodega
            </button>
          }
          table={{
            keyField: "id",
            data: warehouseRows,
            columns: warehouseColumns,
            noDataIndication: "Aun no hay bodegas creadas.",
            totalLabel: "bodegas",
            minWidth: 860,
          }}
        />
      </section>

      <section className="grid">
        <InventoryCrudCard<ProductConfigRow>
          sectionLabel="Producto base"
          title="Listado de configuraciones"
          titleIcon={<SectionIcon kind="operations" />}
          description="Vista consolidada de unidad base, punto de pedido y stock disponible por producto."
          headerAction={
            <button
              className="primary-btn"
              onClick={openProductConfigModal}
              title="Define la unidad base y los minimos de reposicion por producto."
              type="button"
            >
              Configurar unidad y punto de pedido
            </button>
          }
          table={{
            keyField: "id",
            data: productConfigRows,
            columns: productConfigColumns,
            noDataIndication: "Aun no hay configuraciones de inventario visibles.",
            totalLabel: "configuraciones",
            minWidth: 980,
          }}
        />
      </section>

      <section className="grid">
        <InventoryCrudCard<MovementTableRow>
          sectionLabel="Movimientos"
          title="Ultimos registros"
          titleIcon={<SectionIcon kind="movement" />}
          table={{
            keyField: "id",
            data: movementRows,
            columns: movementColumns,
            noDataIndication: "No hay movimientos todavia.",
            totalLabel: "movimientos",
            minWidth: 980,
          }}
        >
          <div>
            <p className="section-label">Operaciones</p>
            <h3><SectionIcon kind="operations" />Acciones rapidas de prueba</h3>
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
                    "Recepcion registrada.",
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
                    "Transferencia registrada.",
                  )
                }
              >
                Transferencia demo
              </button>
            </div>
          </div>
        </InventoryCrudCard>
      </section>

      <section className="grid">
        <InventoryCrudCard<SnapshotTableRow>
          sectionLabel="Stock disponible"
          title="Snapshot por producto y bodega"
          titleIcon={<SectionIcon kind="stock" />}
          table={{
            keyField: "id",
            data: snapshotRows,
            columns: snapshotColumns,
            noDataIndication: "Todavia no hay stock cargado.",
            totalLabel: "registros",
            minWidth: 980,
          }}
        />
      </section>

      {showWarehouseModal ? (
        <WarehouseCreateModal
          error={error}
          onChange={(changes) => setWarehouseForm((current) => ({ ...current, ...changes }))}
          onClose={closeWarehouseModal}
          onSubmit={onCreateWarehouse}
          saving={busy}
          warehouse={warehouseForm}
        />
      ) : null}

      {showProductConfigModal ? (
        <ProductConfigModal
          config={productConfig}
          error={error}
          onChange={(changes) => setProductConfig((current) => ({ ...current, ...changes }))}
          onClose={closeProductConfigModal}
          onSubmit={onConfigureProduct}
          saving={busy}
        />
      ) : null}
    </div>
  );
}
