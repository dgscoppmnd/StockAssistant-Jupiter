import { type Dispatch, type FormEvent, type SetStateAction, useCallback, useEffect, useState } from "react";
import { deleteProductImage, fetchProductImages, setProductDefaultImage, uploadProductImage } from "../../api";
import type { ProductImage } from "../../types";

export type EditorState = {
  pk_product?: number;
  cdgo_producto_externo: string;
  name_product: string;
  description_product: string;
  disabled: boolean;
  price: string;
  unit: string;
  final_price: string;
  discount: string;
  discount_end_date: string;
  currency: string;
  user_rating: string;
  link: string;
  creation_date: string;
  fk_last_update_user: string;
  supplier: string;
};

export const emptyEditor: EditorState = {
  cdgo_producto_externo: "",
  name_product: "",
  description_product: "",
  disabled: false,
  price: "0",
  unit: "1",
  final_price: "0",
  discount: "0",
  discount_end_date: "",
  currency: "",
  user_rating: "0",
  link: "",
  creation_date: "",
  fk_last_update_user: "1",
  supplier: "",
};

type ProductEditerFormProps = {
  editor: EditorState;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (e: FormEvent<HTMLFormElement>) => void | Promise<void>;
  setEditor: Dispatch<SetStateAction<EditorState>>;
  onImagesChanged?: () => void;
};

export default function ProductEditerForm({
  editor,
  saving,
  error,
  onClose,
  onSubmit,
  setEditor,
  onImagesChanged,
}: ProductEditerFormProps) {
  const [images, setImages] = useState<ProductImage[]>([]);
  const [loadingImages, setLoadingImages] = useState(false);
  const [imageSaving, setImageSaving] = useState(false);
  const [imageError, setImageError] = useState("");

  const productId = editor.pk_product;

  const loadImages = useCallback(async () => {
    if (!productId) {
      setImages([]);
      return;
    }

    setLoadingImages(true);
    setImageError("");
    try {
      const rows = await fetchProductImages(productId);
      setImages(rows);
    } catch (err) {
      setImageError(err instanceof Error ? err.message : "No se pudieron cargar las imagenes del producto");
    } finally {
      setLoadingImages(false);
    }
  }, [productId]);

  useEffect(() => {
    void loadImages();
  }, [loadImages]);

  const onUploadImage = async (file: File) => {
    if (!productId) {
      setImageError("Primero crea el producto para poder adjuntar imagenes.");
      return;
    }

    setImageSaving(true);
    setImageError("");
    try {
      await uploadProductImage(productId, file, images.length === 0);
      await loadImages();
      onImagesChanged?.();
    } catch (err) {
      setImageError(err instanceof Error ? err.message : "No se pudo subir la imagen");
    } finally {
      setImageSaving(false);
    }
  };

  const onSetDefault = async (imageId: number) => {
    if (!productId) return;
    setImageSaving(true);
    setImageError("");
    try {
      await setProductDefaultImage(productId, imageId);
      await loadImages();
      onImagesChanged?.();
    } catch (err) {
      setImageError(err instanceof Error ? err.message : "No se pudo cambiar la imagen por defecto");
    } finally {
      setImageSaving(false);
    }
  };

  const onDeleteImage = async (imageId: number) => {
    if (!productId) return;
    if (!window.confirm("¿Borrar esta imagen del producto?")) return;

    setImageSaving(true);
    setImageError("");
    try {
      await deleteProductImage(productId, imageId);
      await loadImages();
      onImagesChanged?.();
    } catch (err) {
      setImageError(err instanceof Error ? err.message : "No se pudo borrar la imagen");
    } finally {
      setImageSaving(false);
    }
  };

  return (
    <div className="product-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
      <div className="product-modal-header">
        <h3>{editor.pk_product ? `Editar producto #${editor.pk_product}` : "Nuevo producto"}</h3>
        <button className="product-modal-close" onClick={onClose} type="button">
          ✕
        </button>
      </div>

      {error && <p className="error-line">{error}</p>}
      {imageError && <p className="error-line">{imageError}</p>}

      <form className="stack" onSubmit={(e) => void onSubmit(e)}>
        <label className="field-label" htmlFor="cdgo_producto_externo">
          Codigo externo
        </label>
        <input
          id="cdgo_producto_externo"
          maxLength={200}
          onChange={(e) => setEditor((p) => ({ ...p, cdgo_producto_externo: e.target.value }))}
          placeholder="Ej. SKU-001"
          value={editor.cdgo_producto_externo}
        />

        <label className="field-label" htmlFor="name_product">
          Nombre
        </label>
        <input
          id="name_product"
          maxLength={200}
          onChange={(e) => setEditor((p) => ({ ...p, name_product: e.target.value }))}
          placeholder="Ej. Producto demo"
          required
          value={editor.name_product}
        />

        <label className="field-label" htmlFor="description_product">
          Descripcion
        </label>
        <textarea
          id="description_product"
          maxLength={1000}
          onChange={(e) => setEditor((p) => ({ ...p, description_product: e.target.value }))}
          placeholder="Descripcion del producto"
          rows={2}
          value={editor.description_product}
        />

        <label className="field-label" htmlFor="disabled">
          Estado
        </label>
        <select
          id="disabled"
          onChange={(e) => setEditor((p) => ({ ...p, disabled: e.target.value === "1" }))}
          value={editor.disabled ? "1" : "0"}
        >
          <option value="0">Activo</option>
          <option value="1">Deshabilitado</option>
        </select>

        <label className="field-label" htmlFor="price">
          Precio
        </label>
        <input
          id="price"
          onChange={(e) => setEditor((p) => ({ ...p, price: e.target.value }))}
          step="0.01"
          type="number"
          value={editor.price}
        />

        <label className="field-label" htmlFor="unit">
          Unidad
        </label>
        <input
          id="unit"
          min={1}
          onChange={(e) => setEditor((p) => ({ ...p, unit: e.target.value }))}
          step="1"
          type="number"
          value={editor.unit}
        />

        <label className="field-label" htmlFor="final_price">
          Precio final
        </label>
        <input
          id="final_price"
          onChange={(e) => setEditor((p) => ({ ...p, final_price: e.target.value }))}
          step="0.01"
          type="number"
          value={editor.final_price}
        />

        <label className="field-label" htmlFor="discount">
          Descuento
        </label>
        <input
          id="discount"
          onChange={(e) => setEditor((p) => ({ ...p, discount: e.target.value }))}
          step="0.01"
          type="number"
          value={editor.discount}
        />

        <label className="field-label" htmlFor="discount_end_date">
          Fin descuento
        </label>
        <input
          id="discount_end_date"
          onChange={(e) => setEditor((p) => ({ ...p, discount_end_date: e.target.value }))}
          type="date"
          value={editor.discount_end_date}
        />

        <label className="field-label" htmlFor="currency">
          Moneda
        </label>
        <input
          id="currency"
          maxLength={50}
          onChange={(e) => setEditor((p) => ({ ...p, currency: e.target.value }))}
          placeholder="Ej. USD"
          value={editor.currency}
        />

        <label className="field-label" htmlFor="user_rating">
          Calificacion
        </label>
        <input
          id="user_rating"
          max={5}
          min={0}
          onChange={(e) => setEditor((p) => ({ ...p, user_rating: e.target.value }))}
          step="0.1"
          type="number"
          value={editor.user_rating}
        />

        <label className="field-label" htmlFor="link">
          Link
        </label>
        <input
          id="link"
          maxLength={255}
          onChange={(e) => setEditor((p) => ({ ...p, link: e.target.value }))}
          placeholder="https://..."
          value={editor.link}
        />

        <label className="field-label" htmlFor="creation_date">
          Fecha de creacion
        </label>
        <input
          id="creation_date"
          onChange={(e) => setEditor((p) => ({ ...p, creation_date: e.target.value }))}
          type="date"
          value={editor.creation_date}
        />

        <label className="field-label" htmlFor="fk_last_update_user">
          Usuario de actualizacion
        </label>
        <input
          id="fk_last_update_user"
          min={1}
          onChange={(e) => setEditor((p) => ({ ...p, fk_last_update_user: e.target.value }))}
          step="1"
          type="number"
          value={editor.fk_last_update_user}
        />

        <label className="field-label" htmlFor="supplier">
          Proveedor
        </label>
        <input
          id="supplier"
          maxLength={200}
          onChange={(e) => setEditor((p) => ({ ...p, supplier: e.target.value }))}
          placeholder="Proveedor"
          value={editor.supplier}
        />

        <div className="product-images-panel">
          <div className="product-images-panel-header">
            <h4>Imagenes del producto</h4>
            <label className="chip-btn" aria-disabled={!productId || imageSaving}>
              Subir imagen
              <input
                className="sr-only-input"
                disabled={!productId || imageSaving}
                onChange={(e) => {
                  const selected = e.target.files?.[0];
                  if (!selected) return;
                  void onUploadImage(selected);
                  e.currentTarget.value = "";
                }}
                type="file"
                accept="image/*"
              />
            </label>
          </div>

          {!productId && (
            <p className="muted" style={{ margin: 0 }}>
              Guarda el producto primero para asociar imagenes.
            </p>
          )}

          {loadingImages ? (
            <p className="muted" style={{ margin: 0 }}>Cargando imagenes...</p>
          ) : (
            <div className="product-images-grid">
              {images.length === 0 ? (
                <p className="muted" style={{ margin: 0 }}>Este producto aun no tiene imagenes.</p>
              ) : (
                images.map((image) => (
                  <div className="product-image-card" key={image.id}>
                    <img alt={image.original_filename ?? `Imagen ${image.id}`} src={image.url} />
                    <div className="product-image-card-meta">
                      <span className={image.is_default ? "pill-default" : "pill-default off"}>
                        {image.is_default ? "Por defecto" : "Secundaria"}
                      </span>
                      <div className="product-image-card-actions">
                        {!image.is_default && (
                          <button
                            className="chip-btn"
                            disabled={imageSaving}
                            onClick={() => void onSetDefault(image.id)}
                            type="button"
                          >
                            Marcar por defecto
                          </button>
                        )}
                        <button
                          className="chip-btn danger"
                          disabled={imageSaving}
                          onClick={() => void onDeleteImage(image.id)}
                          type="button"
                        >
                          Borrar
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <div className="actions-row">
          <button className="primary-btn" disabled={saving || imageSaving} type="submit">
            {saving ? "Guardando..." : editor.pk_product ? "Actualizar" : "Crear producto"}
          </button>
          <button className="chip-btn" onClick={onClose} type="button">
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
}
