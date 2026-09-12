import type { FormEvent } from "react";

import type { InventoryProductConfigPayload } from "../../types";

type ProductConfigModalProps = {
  config: InventoryProductConfigPayload;
  saving: boolean;
  error: string;
  onChange: (changes: Partial<InventoryProductConfigPayload>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  onClose: () => void;
};

export default function ProductConfigModal({ config, saving, error, onChange, onSubmit, onClose }: ProductConfigModalProps) {
  return (
    <div
      className="product-modal-overlay"
      onClick={onClose}
      onKeyDown={(event) => event.key === "Escape" && onClose()}
      role="presentation"
    >
      <div className="product-modal master-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="Configurar unidad y punto de pedido">
        <div className="product-modal-header">
          <h3>Configurar unidad y punto de pedido</h3>
          <button aria-label="Cerrar popup de configuracion" className="product-modal-close" disabled={saving} onClick={onClose} type="button">×</button>
        </div>

        <p className="muted">Define la unidad base y los minimos de reposicion por producto.</p>
        {error ? <p className="error-line">{error}</p> : null}

        <form className="stack" onSubmit={onSubmit}>
          <div className="inventory-crud-grid">
            <div className="field-group">
              <label className="input-label" htmlFor="product-id">ID de producto</label>
              <input
                id="product-id"
                min="1"
                placeholder="Ejemplo: 123"
                required
                type="number"
                value={config.product_id || ""}
                onChange={(event) => onChange({ product_id: Number(event.target.value) })}
              />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="base-unit-code">Unidad base</label>
              <input
                id="base-unit-code"
                placeholder="Ejemplo: unit"
                required
                value={config.base_unit_code}
                onChange={(event) => onChange({ base_unit_code: event.target.value })}
              />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="reorder-point">Punto de pedido</label>
              <input
                id="reorder-point"
                min="0"
                placeholder="Unidades minimas"
                required
                type="number"
                value={config.reorder_point}
                onChange={(event) => onChange({ reorder_point: Number(event.target.value) })}
              />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="reorder-quantity">Cantidad sugerida</label>
              <input
                id="reorder-quantity"
                min="0"
                placeholder="Unidades por reposicion"
                required
                type="number"
                value={config.reorder_quantity}
                onChange={(event) => onChange({ reorder_quantity: Number(event.target.value) })}
              />
            </div>
            <label className="field-label inventory-crud-checkbox inventory-crud-grid-full">
              <input
                checked={config.allow_negative_stock}
                onChange={(event) => onChange({ allow_negative_stock: event.target.checked })}
                type="checkbox"
              />
              Permitir stock negativo
            </label>
          </div>
          <div className="actions-row">
            <button className="primary-btn" disabled={saving} type="submit">{saving ? "Guardando..." : "Guardar configuracion"}</button>
            <button className="chip-btn" disabled={saving} onClick={onClose} type="button">Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  );
}
