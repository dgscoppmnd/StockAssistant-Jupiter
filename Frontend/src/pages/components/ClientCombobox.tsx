import { useEffect, useId, useRef, useState } from "react";
import { searchSalesClients } from "../../api";
import type { SalesClient } from "../../types";
import ComboboxPopup from "./ComboboxPopup";

export default function ClientCombobox({ selected, disabled = false, onSelect }: {
  selected: SalesClient | null; disabled?: boolean; onSelect: (client: SalesClient) => void;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<SalesClient[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [active, setActive] = useState(0);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setLoading(true); setError(""); setItems([]);
    const timer = window.setTimeout(() => {
      void searchSalesClients(query, page, controller.signal).then(rows => {
        if (!controller.signal.aborted) { setItems(rows); setActive(0); }
      }).catch(err => { if (!controller.signal.aborted) setError(String(err)); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 200);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [open, query, page]);
  const choose = (client: SalesClient) => { onSelect(client); setOpen(false); setQuery(""); setPage(1); };
  return <div className="inventory-picker-combobox" onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
  }}>
    <label className="input-label" htmlFor={id}>Cliente (código o nombre)</label>
    <input id={id} ref={input} role="combobox" aria-expanded={open} aria-controls={`${id}-list`} aria-autocomplete="list"
      aria-activedescendant={open && items[active] ? `${id}-${active}` : undefined}
      disabled={disabled} autoComplete="off" value={open ? query : selected ? [selected.client_code, selected.name].filter(Boolean).join(" · ") : ""}
      placeholder="Seleccionar cliente" onFocus={() => setOpen(true)}
      onChange={event => { setQuery(event.target.value); setPage(1); setOpen(true); }}
      onKeyDown={event => {
        if ((event.key === "ArrowDown" || event.key === "ArrowUp") && items.length) {
          event.preventDefault(); setOpen(true); setActive((active + (event.key === "ArrowDown" ? 1 : items.length - 1)) % items.length);
        } else if (event.key === "Enter" && open) { event.preventDefault(); if (items[active] && !loading) choose(items[active]); }
        else if (event.key === "Escape" && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); }
      }} />
    {open && <ComboboxPopup anchor={input}>
      <ul id={`${id}-list`} role="listbox" aria-label="Clientes" aria-busy={loading}>
        {items.map((client, index) => <li key={client.id} id={`${id}-${index}`} role="option" aria-selected={selected?.id === client.id}
          className={index === active ? "active" : ""} onMouseDown={event => event.preventDefault()} onClick={() => choose(client)}>
          {[client.client_code, client.name].filter(Boolean).join(" · ")}
        </li>)}
      </ul>
      <p role="status">{loading ? "Cargando…" : error || (!items.length ? "Sin clientes" : "")}</p>
      <div className="actions-row"><button type="button" disabled={loading || page === 1} onMouseDown={e => e.preventDefault()} onClick={() => setPage(page - 1)}>Anterior</button>
        <button type="button" disabled={loading || items.length < 20} onMouseDown={e => e.preventDefault()} onClick={() => setPage(page + 1)}>Siguiente</button></div>
    </ComboboxPopup>}
  </div>;
}
