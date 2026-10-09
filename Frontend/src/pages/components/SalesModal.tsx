import { useEffect, useId, useRef, type ReactNode } from "react";

export default function SalesModal({ title, saving, onClose, children }: {
  title: string; saving: boolean; onClose: () => void; children: ReactNode;
}) {
  const id = useId();
  const dialog = useRef<HTMLDivElement>(null);
  const busy = useRef(saving);
  const close = useRef(onClose);
  busy.current = saving;
  close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key === "Escape" && !busy.current) { event.preventDefault(); close.current(); }
      if (event.key === "Tab") {
        const elements = Array.from(dialog.current?.querySelectorAll<HTMLElement>("button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]") ?? []);
        const first = elements[0], last = elements[elements.length - 1];
        if (!first) { event.preventDefault(); return; }
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", keydown);
    return () => { document.removeEventListener("keydown", keydown); previous?.focus(); };
  }, []);
  return <div className="product-modal-overlay">
    <div className="product-modal sales-modal" role="dialog" aria-modal="true" aria-labelledby={id} aria-busy={saving} tabIndex={-1} ref={dialog}>
      <div className="inventory-crud-header"><h3 id={id}>{title}</h3><button type="button" className="chip-btn" disabled={saving} onClick={onClose} aria-label="Cerrar">×</button></div>
      {children}
    </div>
  </div>;
}
