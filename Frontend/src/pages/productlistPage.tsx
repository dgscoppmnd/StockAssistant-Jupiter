import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import BootstrapTable from "react-bootstrap-table-next";
import paginationFactory from "react-bootstrap-table2-paginator";
import { createProduct, deleteProduct, fetchProducts, updateProduct } from "../api";
import type { Product, ProductCreatePayload, ProductUpdatePayload } from "../types";
import ProductEditerForm, { type EditorState, emptyEditor } from "./components/productEditerForm";

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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editor, setEditor] = useState<EditorState>(emptyEditor);

  const loadProducts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchProducts();
      setProducts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar los productos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  const openCreate = () => {
    setEditor(emptyEditor);
    setError("");
    setShowModal(true);
  };

  const openEdit = (product: Product) => {
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
  };

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

  const onDelete = async (pkProduct: number, name: string) => {
    if (!window.confirm(`¿Borrar el producto ${name}?`)) return;
    try {
      await deleteProduct(pkProduct);
      await loadProducts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo borrar el producto");
    }
  };

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
            <button className="chip-btn" onClick={() => openEdit(product)} title="Editar" type="button">
              ✏️
            </button>
            <button
              className="chip-btn danger"
              onClick={() => void onDelete(product.pk_product, product.name_product)}
              title="Borrar"
              type="button"
            >
              🗑️
            </button>
          </div>
        )
      }
    ],
    []
  );

  return (
    <div className="users-page">
      <div className="users-toolbar">
        <p className="section-label">Lista de productos</p>
        <button className="primary-btn" onClick={openCreate} type="button">
          + Nuevo producto
        </button>
        {error && <p className="error-line" style={{ margin: 0 }}>{error}</p>}
      </div>

      {loading ? (
        <p className="muted">Cargando productos...</p>
      ) : (
        <div className="users-table-wrapper">
          {products.length === 0 ? (
            <p className="muted" style={{ padding: "18px 14px" }}>
              No hay productos. Crea uno con "+ Nuevo producto".
            </p>
          ) : (
            <div style={{ minWidth: 1700 }}>
              <BootstrapTable
                keyField="pk_product"
                data={products}
                columns={columns}
                classes="users-table"
                headerClasses="users-table"
                bordered={false}
                pagination={paginationFactory({
                  page: 1,
                  pageStartIndex: 1,
                  sizePerPage: 10,
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
          )}
        </div>
      )}

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
