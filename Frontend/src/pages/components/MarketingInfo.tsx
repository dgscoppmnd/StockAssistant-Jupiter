import { useEffect, useId, useRef, useState } from "react";
import "./MarketingInfo.css";

export default function MarketingInfo() {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const pinned = useRef(false);
  const suppressFocus = useRef(false);
  const id = useId();
  const close = (restoreFocus = false) => {
    pinned.current = false;
    setOpen(false);
    if (restoreFocus) {
      suppressFocus.current = true;
      button.current?.focus();
      suppressFocus.current = false;
    }
  };
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) close();
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close(Boolean(root.current?.contains(document.activeElement)));
      }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  return <div className="marketing-info" ref={root}
    onMouseEnter={() => setOpen(true)}
    onMouseLeave={() => { if (!pinned.current && !root.current?.contains(document.activeElement)) setOpen(false); }}
    onFocusCapture={() => { if (!suppressFocus.current) setOpen(true); }}
    onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) close(); }}>
    <button ref={button} className="routing-info-button" type="button"
      aria-label="Información sobre el análisis de Marketing" aria-expanded={open} aria-controls={id} aria-haspopup="dialog"
      onClick={() => { if (pinned.current) close(); else { pinned.current = true; setOpen(true); } }}>
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9" /><path d="M12 11v6" /><circle className="routing-info-dot" cx="12" cy="7" r="1" /></svg>
    </button>
    {open && <div id={id} className="marketing-info-panel" role="dialog" aria-label="Cómo funciona el análisis de Marketing">
      <button className="marketing-info-close" type="button" aria-label="Cerrar información de Marketing" onClick={() => close(true)}>×</button>
      <p>Compara dos periodos de 30 días completos. Selecciona hasta tres productos con crecimiento, stock disponible, al menos 10 unidades recientes, 5 anteriores y despachos en 3 días recientes distintos.</p>
      <p>Prioriza el mayor aumento en unidades. Consulta Google Trends usando el nombre del producto y prepara una propuesta de campaña. Si faltan datos externos, lo indica; no necesita una fecha comercial concreta.</p>
      <p>Las propuestas son borradores: revisa el público, el stock y el margen antes de lanzarlas. No publica campañas ni aplica descuentos.</p>
    </div>}
  </div>;
}
