import ComboboxPopup from "./ComboboxPopup";
import { useEffect, useId, useRef, useState } from "react";
import { fetchProductOption, searchProductOptions } from "../../api";
import type { ProductOption, ProductOptions } from "../../types";

type Props = {
  label?: string;
  selectedId: number;
  selectedProduct?: ProductOption | null;
  disabled: boolean;
  onSelect: (product: ProductOption) => void;
  loadOptions?: typeof searchProductOptions;
};
const productLabel = (product: ProductOption) => `${product.cdgo_producto_externo || "Sin código"} · ${product.name_product}`;
const emptyResults: ProductOptions = { items: [], next_cursor: null };

export default function ProductCombobox({ selectedId, selectedProduct, disabled, onSelect, loadOptions = searchProductOptions, label = "Producto (código o nombre)" }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [cursors, setCursors] = useState([0]);
  const [result, setResult] = useState<ProductOptions>(emptyResults);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [remembered, setRemembered] = useState<ProductOption | null>(null);
  const [selectedError, setSelectedError] = useState("");
  const request = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const selected = selectedProduct?.pk_product === selectedId ? selectedProduct : remembered?.pk_product === selectedId ? remembered : null;
  const activeIndex = Math.min(active, result.items.length - 1);
  const expanded = open && !disabled;
  const cursor = cursors[cursors.length - 1];
  const shortQuery = query.trim().length > 0 && query.trim().length < 3;

  useEffect(() => {
    setSelectedError("");
    if (!selectedId || selected) return;
    const controller = new AbortController();
    void fetchProductOption(selectedId, controller.signal).then(product => {
      if (!controller.signal.aborted) setRemembered(product);
    }).catch(() => {
      if (!controller.signal.aborted) setSelectedError("No se pudo cargar el producto seleccionado. Puedes buscarlo de nuevo.");
    });
    return () => controller.abort();
  }, [selectedId, selected]);

  useEffect(() => {
    if (!expanded || shortQuery) { setLoading(false); return; }
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError("");
    setResult(emptyResults);
    const timer = window.setTimeout(() => {
      void loadOptions(query.trim(), cursor, controller.signal).then(data => {
        if (!controller.signal.aborted) { setResult(data); setActive(0); }
      }).catch(err => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "No se pudieron buscar los productos.");
      }).finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    }, query.trim() ? 300 : 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [expanded, query, shortQuery, cursor, retry, loadOptions]);

  useEffect(() => {
    if (expanded && activeIndex >= 0) list.current?.children[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, expanded]);

  const resetSearch = () => { request.current?.abort(); setQuery(""); setCursors([0]); setResult(emptyResults); setActive(0); setError(""); };
  const choose = (product: ProductOption) => {
    setRemembered(product); onSelect(product); setOpen(false); resetSearch();
  };
  const nextPage = () => {
    if (!loading && result.next_cursor !== null) { setLoading(true); setResult(emptyResults); setCursors([...cursors, result.next_cursor]); }
  };
  const previousPage = () => {
    if (!loading && cursors.length > 1) { setLoading(true); setResult(emptyResults); setCursors(cursors.slice(0, -1)); }
  };
  const showOptions = () => { if (!open) { resetSearch(); setOpen(true); } };

  return <div className="inventory-picker-combobox stock-order-product-combobox" onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) { setOpen(false); resetSearch(); }
  }}>
    <label className="input-label" htmlFor={id}>{label}</label>
    <div className="inventory-picker-input">
      <input ref={input} id={id} role="combobox" aria-autocomplete="list"
        aria-expanded={expanded} aria-controls={`${id}-options`} aria-describedby={expanded ? `${id}-status` : undefined}
        aria-activedescendant={expanded && !loading && activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
        autoComplete="off" disabled={disabled} maxLength={200}
        placeholder="Buscar por código o nombre…"
        value={expanded ? query : selected ? productLabel(selected) : selectedId ? `Producto #${selectedId}` : ""}
        onFocus={showOptions} onClick={showOptions}
        onChange={(event) => { request.current?.abort(); setQuery(event.target.value); setCursors([0]); setResult(emptyResults); setError(""); setLoading(true); setOpen(true); setActive(0); }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault(); setOpen(true);
            if (!loading && result.items.length) setActive(!expanded ? 0 : (activeIndex + (event.key === "ArrowDown" ? 1 : result.items.length - 1)) % result.items.length);
          } else if (event.key === "Enter" && expanded) {
            event.preventDefault(); if (!loading && result.items[activeIndex]) choose(result.items[activeIndex]);
          } else if (event.key === "PageDown" && expanded) {
            event.preventDefault(); nextPage();
          } else if (event.key === "PageUp" && expanded) {
            event.preventDefault(); previousPage();
          } else if (event.key === "Escape" && expanded) {
            event.preventDefault(); event.stopPropagation(); setOpen(false); resetSearch();
          }
        }} />
      <button type="button" tabIndex={-1} className="chip-btn" disabled={disabled} aria-label="Mostrar productos"
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => { input.current?.focus(); showOptions(); }}>▾</button>
    </div>
    {selectedError && <p className="error-line" role="alert">{selectedError}</p>}
    {expanded && <ComboboxPopup anchor={input}>
      <ul ref={list} id={`${id}-options`} role="listbox" aria-label="Productos" aria-busy={loading}>
        {result.items.map((product, index) => <li key={product.pk_product} id={`${id}-option-${index}`} role="option"
          aria-selected={product.pk_product === selectedId} className={index === activeIndex ? "is-active" : ""}
          onMouseDown={(event) => event.preventDefault()} onClick={() => choose(product)}>
          {productLabel(product)}{product.pk_product === selectedId ? " ✓" : ""}
        </li>)}
      </ul>
      <p className="muted" id={`${id}-status`} role="status">{shortQuery ? "Escribe al menos 3 caracteres para buscar." : loading ? "Buscando productos…" : error ? "No se pudo completar la búsqueda." : result.items.length ? `${query.trim() ? "Coincidencias" : "Productos más recientes"} · Página ${cursors.length}. AvPág/RePág para navegar.` : "No hay productos que coincidan."}</p>
      {error && <button className="chip-btn" type="button" onClick={() => setRetry(retry + 1)}>Reintentar búsqueda</button>}
      {(cursors.length > 1 || result.next_cursor !== null) && <div className="actions-cell">
        <button type="button" className="chip-btn" disabled={loading || cursors.length === 1} onClick={previousPage}>Anterior</button>
        <button type="button" className="chip-btn" disabled={loading || result.next_cursor === null} onClick={nextPage}>Siguiente</button>
      </div>}
    </ComboboxPopup>}
  </div>;
}
