import ComboboxPopup from "./ComboboxPopup";
import { useEffect, useRef, useState } from "react";
import type { MasterRecord } from "../../types";

type Props = {
  suppliers: MasterRecord[];
  selectedId: number | null;
  creating: boolean;
  disabled: boolean;
  loading: boolean;
  onSelect: (supplier: MasterRecord) => void;
  onCreate: (name: string) => void;
};

const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const supplierLabel = (supplier: MasterRecord) => [supplier.supplier_code, supplier.name].filter(Boolean).join(" · ");

export default function SupplierCombobox({ suppliers, selectedId, creating, disabled, loading, onSelect, onCreate }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const selected = suppliers.find((supplier) => supplier.id === selectedId);
  const matches = suppliers.filter((supplier) => normalize(supplierLabel(supplier)).includes(normalize(query.trim())));
  const options = [
    ...matches.map((supplier) => ({ supplier, label: supplierLabel(supplier) })),
    { supplier: null, label: query.trim() ? `Crear nuevo proveedor: «${query.trim()}»…` : "Crear nuevo proveedor…" },
  ];
  const activeIndex = Math.min(active, options.length - 1);
  const expanded = open && !disabled;

  useEffect(() => {
    if (expanded) list.current?.children[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, expanded]);

  const choose = (supplier: MasterRecord | null) => {
    if (supplier) onSelect(supplier);
    else onCreate(query.trim());
    setOpen(false);
    setQuery("");
  };

  return <div className="inventory-picker-combobox stock-order-supplier-combobox" onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) { setOpen(false); setQuery(""); }
  }}>
    <label className="input-label" htmlFor="stock-order-supplier">Proveedor (código o nombre)</label>
    <div className="inventory-picker-input">
      <input ref={input} id="stock-order-supplier" role="combobox" aria-autocomplete="list"
        aria-expanded={expanded} aria-controls="stock-order-supplier-options"
        aria-activedescendant={expanded ? `stock-order-supplier-option-${activeIndex}` : undefined}
        autoComplete="off" disabled={disabled} placeholder="Buscar por código o nombre…"
        value={expanded ? query : selected ? supplierLabel(selected) : creating ? "Nuevo proveedor" : ""}
        onFocus={() => { setOpen(true); setQuery(""); setActive(0); }}
        onClick={() => { if (!open) { setOpen(true); setQuery(""); setActive(0); } }}
        onChange={(event) => { setQuery(event.target.value); setOpen(true); setActive(0); }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setOpen(true);
            setActive(!expanded ? 0 : (activeIndex + (event.key === "ArrowDown" ? 1 : options.length - 1)) % options.length);
          } else if (event.key === "Enter" && expanded) {
            event.preventDefault();
            choose(options[activeIndex].supplier);
          } else if (event.key === "Escape" && expanded) {
            event.preventDefault(); event.stopPropagation(); setOpen(false); setQuery("");
          }
        }} />
      <button type="button" tabIndex={-1} className="chip-btn" disabled={disabled} aria-label="Mostrar proveedores"
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => { input.current?.focus(); setOpen(true); setQuery(""); setActive(0); }}>▾</button>
    </div>
    {expanded && <ComboboxPopup anchor={input}>
      <ul ref={list} id="stock-order-supplier-options" role="listbox" aria-label="Proveedores" aria-busy={loading}>
        {options.map((option, index) => <li key={option.supplier?.id ?? "create"}
          id={`stock-order-supplier-option-${index}`} role="option"
          aria-selected={option.supplier ? option.supplier.id === selectedId : creating}
          className={index === activeIndex ? "is-active" : ""}
          onMouseDown={(event) => event.preventDefault()} onClick={() => choose(option.supplier)}>
          {option.label}{option.supplier?.id === selectedId ? " ✓" : ""}
        </li>)}
      </ul>
      <p className="muted" role="status">{loading ? "Cargando proveedores…" : matches.length ? `${matches.length} proveedores disponibles` : "No hay proveedores que coincidan."}</p>
    </ComboboxPopup>}
  </div>;
}
