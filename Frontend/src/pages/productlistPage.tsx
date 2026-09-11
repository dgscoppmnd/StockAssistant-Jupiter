import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import BootstrapTable from "react-bootstrap-table-next";
import paginationFactory from "react-bootstrap-table2-paginator";
import { createProduct, deleteProduct, fetchProductsPage, importProductsCsv, updateProduct } from "../api";
import type { Product, ProductCreatePayload, ProductUpdatePayload } from "../types";
import ProductEditerForm, { type EditorState, emptyEditor } from "./components/productEditerForm";
import type { ProductImportProgress } from "../utils/productCsvUpload";

function toInputDate(raw?: string | null): string {
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
}

function formatDisplayDate(raw?: string | null): string {
  if (!raw) return "-";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("es-ES");
}

function toInputNumber(raw?: number | null): string {
  if (raw === null || raw === undefined || Number.isNaN(raw)) return "";
  return String(raw);
}

function toNullableNumber(raw: string): number | null {
  const clean = raw.trim();
  if (!clean) return null;
  const value = Number(clean);
  return Number.isFinite(value) ? value : null;
}

function toInteger(raw: string, fallback: number): number {
  const value = Number(raw);
  if (!Number.isFinite(value)) return fallback;
  return Math.trunc(value);
}

function normalizeText(raw: string): string | null {
  const clean = raw.trim();
  return clean ? clean : null;
}

function buildPayload(editor: EditorState): ProductCreatePayload {
  return {
    cdgo_producto_externo: normalizeText(editor.cdgo_producto_externo),
    name_product: editor.name_product.trim(),
    description_product: normalizeText(editor.description_product),
    disabled: editor.disabled,
    price: toNullableNumber(editor.price),
    unit: toInteger(editor.unit, 1),
    final_price: toNullableNumber(editor.final_price),
    discount: toNullableNumber(editor.discount),
    discount_end_date: editor.discount_end_date || null,
    fk_currency: 1,
    currency: normalizeText(editor.currency),
    user_rating: toNullableNumber(editor.user_rating) ?? 0,
    link: normalizeText(editor.link),
    creation_date: editor.creation_date || null,
    fk_last_update_user: toInteger(editor.fk_last_update_user, 1),
    supplier: normalizeText(editor.supplier)
  };
}

export default function ProductlistPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, pageSize: 10, total: 0 });
  const requestedPage = useRef({ page: 1, pageSize: 10 });
  const activeRequest = useRef<AbortController | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editor, setEditor] = useState<EditorState>(emptyEditor);
  const [showImport, setShowImport] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const [importResult, setImportResult] = useState("");
  const [importProgress, setImportProgress] = useState<ProductImportProgress | null>(null);
  const progressLabels = {
    uploading: "Subiendo archivo (1/3)",
    validating: "Validando CSV (2/3)",
    importing: "Importando productos (3/3)",
    committing: "Confirmando el guardado",
    complete: "Importación completada",
  };

  const loadProducts = useCallback(async (page = requestedPage.current.page, pageSize = requestedPage.current.pageSize) => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    requestedPage.current = { page, pageSize };
    setLoading(true);
    setError("");
    try {
      const data = await fetchProductsPage(page, pageSize, controller.signal);
      if (controller.signal.aborted) return;
      setProducts(data.items);
      requestedPage.current = { page: data.page, pageSize: data.page_size };
      setPagination({ page: data.page, pageSize: data.page_size, total: data.total });
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "No se pudieron cargar los productos");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProducts();
    return () => activeRequest.current?.abort();
  }, [loadProducts]);

  const onImport = async (event: FormEvent) => {
    event.preventDefault();
    if (!csvFile || importing) return;
    setImportError("");
    setImportResult("");
    setImportProgress(null);
    if (!csvFile.name.toLowerCase().endsWith(".csv") || csvFile.size > 200 * 1024 * 1024) {
      setImportError("Selecciona un archivo .csv de hasta 200 MB.");
      return;
    }
    setImporting(true);
    try {
      const result = await importProductsCsv(csvFile, setImportProgress);
      setImportResult(`Importación completada: ${result.imported} productos importados y ${result.skipped} omitidos por código existente, de ${result.total} productos.`);
      setCsvFile(null);
      setShowImport(false);
      await loadProducts();
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo importar el CSV.";
      try {
        const parsed = JSON.parse(message) as { detail?: unknown };
        setImportError(typeof parsed.detail === "string" ? parsed.detail : message);
      } catch {
        setImportError(message);
      }
    } finally {
      setImporting(false);
    }
  };

  const openCreate = () => {
    setEditor(emptyEditor);
    setError("");
    setShowModal(true);
  };

  const openEdit = useCallback((product: Product) => {
    setEditor({
      pk_product: product.pk_product,
      cdgo_producto_externo: product.cdgo_producto_externo ?? "",
      name_product: product.name_product,
      description_product: product.description_product ?? "",
      disabled: product.disabled,
      price: toInputNumber(product.price),
      unit: toInputNumber(product.unit),
      final_price: toInputNumber(product.final_price),
      discount: toInputNumber(product.discount),
      discount_end_date: toInputDate(product.discount_end_date),
      currency: product.currency ?? "",
      user_rating: toInputNumber(product.user_rating),
      link: product.link ?? "",
      creation_date: toInputDate(product.creation_date),
      fk_last_update_user: toInputNumber(product.fk_last_update_user),
      supplier: product.supplier ?? ""
    });
    setError("");
    setShowModal(true);
  }, []);

  const closeModal = () => {
    setShowModal(false);
    setEditor(emptyEditor);
    setError("");
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!editor.name_product.trim()) {
      setError("El nombre del producto es obligatorio.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const payload = buildPayload(editor);

      if (editor.pk_product) {
        await updateProduct(editor.pk_product, payload as ProductUpdatePayload);
      } else {
        await createProduct(payload);
      }

      await loadProducts();
      closeModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el producto");
    } finally {
      setSaving(false);
    }
  };

  const onDelete = useCallback(async (pkProduct: number, name: string) => {
    if (!window.confirm(`¿Borrar el producto ${name}?`)) return;
    try {
      await deleteProduct(pkProduct);
      await loadProducts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo borrar el producto");
    }
  }, [loadProducts]);

  const columns = useMemo<any[]>(
    () => [
      {
        dataField: "default_image_url",
        text: "Imagen",
        headerStyle: () => ({ width: "94px", minWidth: "94px" }),
        style: { width: "94px", minWidth: "94px" },
        formatter: (cell: string | null): ReactNode =>
          cell ? (
            <img alt="Producto" className="product-default-thumb" src={cell} loading="lazy" />
          ) : (
            <span className="muted">-</span>
          )
      },
      { dataField: "cdgo_producto_externo", text: "Codigo externo", formatter: (cell: string | null) => cell || "-" },
      { dataField: "name_product", text: "Nombre" },
      { dataField: "description_product", text: "Descripcion", formatter: (cell: string | null) => cell || "-" },
      {
        dataField: "disabled",
        text: "Deshabilitado",
        formatter: (cell: boolean) => (cell ? "Si" : "No")
      },
      { dataField: "price", text: "Precio", formatter: (cell: number | null) => cell != null ? `$${Number(cell).toFixed(2)}` : "-" },
      { dataField: "unit", text: "Unidad" },
      { dataField: "final_price", text: "Precio final", formatter: (cell: number | null) => cell != null ? `$${Number(cell).toFixed(2)}` : "-" },
      { dataField: "discount", text: "Descuento", formatter: (cell: number | null) => cell != null ? `${cell*100}%` : "-" },
      {
        dataField: "discount_end_date",
        text: "Fin descuento",
        formatter: (cell: string | null) => formatDisplayDate(cell)
      },
      { dataField: "currency", text: "Moneda", formatter: (cell: string | null) => cell || "-" },
      { dataField: "user_rating", text: "Rating" },
      { dataField: "link", text: "Link",
        style: { wordBreak: "break-all", whiteSpace: "normal", minWidth: "160px" }, 
        formatter: (cell: string | null): ReactNode => cell ? <a href={cell} target="_blank" rel="noreferrer noopener">{cell}</a> : "-" },
      {
        dataField: "creation_date",
        text: "Creacion",
        formatter: (cell: string | null) => formatDisplayDate(cell)
      },
      { dataField: "fk_last_update_user", text: "Usuario actualizacion" },
      {
        dataField: "last_update",
        text: "Ultima actualizacion",
        formatter: (cell: string | null) => formatDisplayDate(cell)
      },
      { dataField: "supplier", text: "Proveedor", formatter: (cell: string | null) => cell || "-" },
      {
        dataField: "actions",
        text: "Acciones",
        isDummyField: true,
        headerStyle: () => ({ width: "132px", minWidth: "132px" }),
        style: { minWidth: "132px" },
        formatter: (_: unknown, product: Product): ReactNode => (
          <div className="actions-cell">
            <button className="chip-btn" onClick={() => openEdit(product)} title="Editar" type="button" disabled={loading}>
              ✏️
            </button>
            <button
              className="chip-btn danger"
              onClick={() => void onDelete(product.pk_product, product.name_product)}
              title="Borrar"
              disabled={loading}
              type="button"
            >
              🗑️
            </button>
          </div>
        )
      }
    ],
    [openEdit, onDelete, loading]
  );

  return (
    <div className="users-page">
      <div className="users-toolbar">
        <p className="section-label">Lista de productos</p>
        <button className="primary-btn" onClick={openCreate} type="button">
          + Nuevo producto
        </button>
        <button className="primary-btn" onClick={() => { setShowImport(!showImport); setCsvFile(null); setImportError(""); setImportProgress(null); }} type="button" disabled={importing} aria-expanded={showImport} aria-controls="product-csv-import">
          Importar CSV
        </button>
        {error && <p className="error-line" role="alert" style={{ margin: 0 }}>{error} <button type="button" className="chip-btn" disabled={loading} onClick={() => void loadProducts()}>Recargar lista</button></p>}
      </div>

      {importResult && <p role="status">{importResult}</p>}
      {importProgress && !importError && (
        <div style={{ margin: "16px 0" }}>
          <p id="product-import-progress-label" role="status" style={{ marginBottom: 6 }}>
            {progressLabels[importProgress.stage]}
            {importProgress.stage !== "committing" && `: ${importProgress.percent}%`}
            {importProgress.stage === "importing" && ` · ${importProgress.processed?.toLocaleString("es-ES")} de ${importProgress.total?.toLocaleString("es-ES")} productos procesados`}
          </p>
          <progress aria-labelledby="product-import-progress-label" max={100} value={importProgress.stage === "committing" ? undefined : importProgress.percent} style={{ width: "100%", height: 22, accentColor: "#2563eb" }} />
        </div>
      )}
      {showImport && (
        <form id="product-csv-import" onSubmit={onImport} className="users-table-wrapper" style={{ padding: 20, marginBottom: 20 }} aria-busy={importing}>
          <h2 style={{ fontSize: "1.2rem" }}>Importar productos desde CSV</h2>
          <p>Usa el formato de formatoEjemploProductos.csv: UTF-8, separado por comas, hasta 200 MB. Los archivos grandes pueden tardar varios minutos en importarse.</p>
          <p style={{ overflowWrap: "anywhere" }}><strong>Cabecera:</strong> product_id,product_name,description,product_category,brand,sku,product_cost_usd,selling_price_usd,created_at</p>
          <p>El coste se guarda como precio base y el precio de venta como precio final en USD. Categoría, marca y SKU se añaden a la descripción. Fecha: AAAA-MM-DD HH:MM:SS (UTC).</p>
          <p>Se omiten los códigos externos existentes. Los identificadores repetidos dentro del CSV o las filas inválidas impiden importar el archivo completo.</p>
          <label htmlFor="product-csv-file">Archivo CSV</label>{" "}
          <input id="product-csv-file" type="file" accept=".csv,text/csv" disabled={importing} required onChange={(event) => { setCsvFile(event.target.files?.[0] ?? null); setImportError(""); }} />
          <div className="actions-cell" style={{ marginTop: 16 }}>
            <button className="primary-btn" type="submit" disabled={!csvFile || importing}>{importing ? "Importando..." : "Importar productos"}</button>
            <button className="chip-btn" type="button" disabled={importing} onClick={() => { setShowImport(false); setCsvFile(null); setImportError(""); }}>Cancelar</button>
          </div>
          {importError && <p className="error-line" role="alert">{importError}</p>}
        </form>
      )}

      {loading && <p className="muted" role="status">Cargando productos...</p>}
        <div className="users-table-wrapper" aria-busy={loading}>
          {products.length === 0 && !loading && !error ? (
            <p className="muted" style={{ padding: "18px 14px" }}>
              No hay productos. Crea uno con "+ Nuevo producto" o usa "Importar CSV".
            </p>
          ) : products.length > 0 ? (
            <div style={{ minWidth: 1700, opacity: loading ? 0.6 : 1, pointerEvents: loading ? "none" : "auto" }}>
              <BootstrapTable
                keyField="pk_product"
                data={products}
                columns={columns}
                classes="users-table"
                headerClasses="users-table"
                bordered={false}
                remote={{ pagination: true }}
                onTableChange={(type: string, state: { page: number; sizePerPage: number }) => {
                  if (type !== "pagination" || loading) return;
                  const nextPage = state.sizePerPage !== pagination.pageSize ? 1 : state.page;
                  void loadProducts(nextPage, state.sizePerPage);
                }}
                pagination={paginationFactory({
                  page: pagination.page,
                  pageStartIndex: 1,
                  sizePerPage: pagination.pageSize,
                  totalSize: pagination.total,
                  sizePerPageList: [
                    { text: "10", value: 10 },
                    { text: "25", value: 25 },
                    { text: "50", value: 50 }
                  ],
                  showTotal: true,
                  paginationTotalRenderer: (from: number, to: number, size: number) => `${from} - ${to} de ${size} productos`
                })}
              />
            </div>
          ) : null}
        </div>

      {showModal && (
        <div
          className="product-modal-overlay"
          onClick={closeModal}
          onKeyDown={(e) => {
            if (e.key === "Escape") closeModal();
          }}
          role="presentation"
        >
          <ProductEditerForm
            editor={editor}
            error={error}
            onClose={closeModal}
            onSubmit={onSubmit}
            saving={saving}
            setEditor={setEditor}
            onImagesChanged={() => {
              void loadProducts();
            }}
          />
        </div>
      )}
    </div>
  );
}
