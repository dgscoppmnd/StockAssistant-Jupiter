import ComboboxPopup from "./ComboboxPopup";
import { useEffect, useId, useRef, useState } from "react";
import type { Product } from "../../types";

type Props = {
  label?: string;
  products: Product[];
  selectedId: number;
  disabled: boolean;
  loading: boolean;
  onSelect: (product: Product) => void;
};

const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const productLabel = (product: Product) => `${product.cdgo_producto_externo || "Sin código"} · ${product.name_product}`;

export default function ProductCombobox({ products, selectedId, disabled, loading, onSelect, label = "Producto (código o nombre)" }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const selected = products.find((product) => product.pk_product === selectedId);
  const matches = products.filter((product) => normalize(`${product.cdgo_producto_externo ?? ""} ${product.name_product}`).includes(normalize(query.trim())));
  const activeIndex = Math.min(active, matches.length - 1);
  const expanded = open && !disabled;

  useEffect(() => {
    if (expanded && activeIndex >= 0) list.current?.children[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, expanded]);

  const choose = (product: Product) => {
    onSelect(product);
    setOpen(false);
    setQuery("");
  };

  return <div className="inventory-picker-combobox stock-order-product-combobox" onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) { setOpen(false); setQuery(""); }
  }}>
    <label className="input-label" htmlFor={id}>{label}</label>
    <div className="inventory-picker-input">
      <input ref={input} id={id} role="combobox" aria-autocomplete="list"
        aria-expanded={expanded} aria-controls={`${id}-options`}
        aria-activedescendant={expanded && activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
        autoComplete="off" disabled={disabled || loading}
        placeholder={loading ? "Cargando productos…" : "Buscar por código o nombre…"}
        value={expanded ? query : selected ? productLabel(selected) : ""}
        onFocus={() => { setOpen(true); setQuery(""); setActive(0); }}
        onClick={() => { if (!open) { setOpen(true); setQuery(""); setActive(0); } }}
        onChange={(event) => { setQuery(event.target.value); setOpen(true); setActive(0); }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setOpen(true);
            if (matches.length) setActive(!expanded ? 0 : (activeIndex + (event.key === "ArrowDown" ? 1 : matches.length - 1)) % matches.length);
          } else if (event.key === "Enter" && expanded) {
            event.preventDefault();
            if (matches[activeIndex]) choose(matches[activeIndex]);
          } else if (event.key === "Escape" && expanded) {
            event.preventDefault(); event.stopPropagation(); setOpen(false); setQuery("");
          }
        }} />
      <button type="button" tabIndex={-1} className="chip-btn" disabled={disabled || loading} aria-label="Mostrar productos"
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => { input.current?.focus(); setOpen(true); setQuery(""); setActive(0); }}>▾</button>
    </div>
    {expanded && <ComboboxPopup anchor={input}>
      <ul ref={list} id={`${id}-options`} role="listbox" aria-label="Productos" aria-busy={loading}>
        {matches.map((product, index) => <li key={product.pk_product} id={`${id}-option-${index}`} role="option"
          aria-selected={product.pk_product === selectedId} className={index === activeIndex ? "is-active" : ""}
          onMouseDown={(event) => event.preventDefault()} onClick={() => choose(product)}>
          {productLabel(product)}{product.pk_product === selectedId ? " ✓" : ""}
        </li>)}
      </ul>
      <p className="muted" role="status">{matches.length ? `${matches.length} productos disponibles` : "No hay productos que coincidan."}</p>
    </ComboboxPopup>}
  </div>;
}
