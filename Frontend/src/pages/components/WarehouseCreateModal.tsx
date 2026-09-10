import type { FormEvent } from "react";

import type { InventoryWarehousePayload } from "../../types";

type WarehouseCreateModalProps = {
  warehouse: InventoryWarehousePayload;
  saving: boolean;
  error: string;
  onChange: (changes: Partial<InventoryWarehousePayload>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  onClose: () => void;
};

export default function WarehouseCreateModal({ warehouse, saving, error, onChange, onSubmit, onClose }: WarehouseCreateModalProps) {
  return (
    <div
      className="product-modal-overlay"
      onClick={onClose}
      onKeyDown={(event) => event.key === "Escape" && onClose()}
      role="presentation"
    >
      <div className="product-modal master-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="Crear bodega">
        <div className="product-modal-header">
          <h3>Crear bodega</h3>
          <button aria-label="Cerrar popup de crear bodega" className="product-modal-close" disabled={saving} onClick={onClose} type="button">×</button>
        </div>

        <p className="muted">Alta rapida de ubicaciones fisicas para recepcion, almacenamiento y transferencia.</p>
        {error ? <p className="error-line">{error}</p> : null}

        <form className="stack" onSubmit={onSubmit}>
          <div className="inventory-crud-grid">
            <div className="field-group">
              <label className="input-label" htmlFor="warehouse-code">Codigo</label>
              <input
                id="warehouse-code"
                placeholder="Ejemplo: MADRID"
                required
                value={warehouse.code}
                onChange={(event) => onChange({ code: event.target.value })}
              />
            </div>
            <div className="field-group">
              <label className="input-label" htmlFor="warehouse-name">Nombre</label>
              <input
                id="warehouse-name"
                placeholder="Nombre de la bodega"
                required
                value={warehouse.name}
                onChange={(event) => onChange({ name: event.target.value })}
              />
            </div>
            <div className="field-group inventory-crud-grid-full">
              <label className="input-label" htmlFor="warehouse-description">Descripcion</label>
              <input
                id="warehouse-description"
                placeholder="Descripcion opcional"
                value={warehouse.description ?? ""}
                onChange={(event) => onChange({ description: event.target.value })}
              />
            </div>
          </div>
          <div className="actions-row">
            <button className="primary-btn" disabled={saving} type="submit">{saving ? "Guardando..." : "Guardar bodega"}</button>
            <button className="chip-btn" disabled={saving} onClick={onClose} type="button">Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  );
}
