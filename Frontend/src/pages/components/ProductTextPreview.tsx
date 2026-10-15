import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

export default function ProductTextPreview({ text, link = false }: { text: string | null; link?: boolean }) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout>>();
  const [position, setPosition] = useState<{ left: number; top: number; maxHeight: number } | null>(null);
  let href: string | undefined;
  if (link && text) {
    try {
      const url = new URL(text);
      if (url.protocol === "https:" || url.protocol === "http:") href = url.href;
    } catch { /* Keep malformed links readable as plain text. */ }
  }

  const keepOpen = () => clearTimeout(closeTimer.current);
  const closeSoon = () => {
    keepOpen();
    closeTimer.current = setTimeout(() => {
      if (!trigger.current?.contains(document.activeElement) && !popup.current?.contains(document.activeElement)) {
        setPosition(null);
      }
    }, 180);
  };
  const open = () => {
    keepOpen();
    const rect = trigger.current?.getBoundingClientRect();
    if (!rect) return;
    const width = Math.min(440, window.innerWidth - 24);
    const below = window.innerHeight - rect.bottom - 20;
    const above = rect.top - 20;
    const maxHeight = Math.min(320, Math.max(below, above));
    setPosition({
      left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
      top: below >= Math.min(320, above) ? rect.bottom + 6 : Math.max(12, rect.top - maxHeight - 6),
      maxHeight,
    });
  };

  useEffect(() => {
    if (!position) return;
    const dismiss = () => setPosition(null);
    const onScroll = (event: Event) => {
      if (event.target instanceof Node && popup.current?.contains(event.target)) return;
      dismiss();
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (popup.current?.contains(document.activeElement)) trigger.current?.focus();
        dismiss();
      }
    };
    const onPointer = (event: PointerEvent) => {
      if (event.target instanceof Node && !trigger.current?.contains(event.target) && !popup.current?.contains(event.target)) dismiss();
    };
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", dismiss);
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", dismiss);
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [position]);

  useEffect(() => () => clearTimeout(closeTimer.current), []);

  if (!text) return <span className="muted">-</span>;

  return <>
    <button
      ref={trigger}
      type="button"
      className={`product-text-preview${link ? " product-text-preview-link" : ""}`}
      aria-expanded={Boolean(position)}
      aria-controls={position ? id : undefined}
      onMouseEnter={open}
      onMouseLeave={closeSoon}
      onFocus={open}
      onBlur={closeSoon}
      onClick={open}
      onKeyDown={(event) => {
        if (event.key === "Tab" && !event.shiftKey && position && href) {
          event.preventDefault();
          popup.current?.querySelector("a")?.focus();
        }
      }}
    >
      <span>{text}</span>
    </button>
    {position && createPortal(
      <div
        ref={popup}
        id={id}
        role="region"
        aria-label={link ? "Enlace completo del producto" : "Descripción completa del producto"}
        className="product-text-popup"
        style={position}
        onMouseEnter={keepOpen}
        onMouseLeave={closeSoon}
        onFocus={keepOpen}
        onBlur={closeSoon}
        onKeyDown={(event) => {
          if (event.key !== "Tab") return;
          event.preventDefault();
          if (event.shiftKey) {
            trigger.current?.focus();
          } else {
            const controls = Array.from(document.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]'));
            const next = controls[controls.indexOf(trigger.current!) + 1];
            next?.focus();
            setPosition(null);
          }
        }}
      >
        {href ? <a href={href} target="_blank" rel="noopener noreferrer">{text}<span className="product-text-popup-hint">Abrir en una pestaña nueva ↗</span></a> : text}
      </div>, document.body,
    )}
  </>;
}
