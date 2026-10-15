import { useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

export default function InfoPopup({ title, label, children }: { title: string; label: string; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  return <>
    <button className="routing-info-button" type="button" aria-label={label} aria-haspopup="dialog" title={title} onClick={() => dialog.current?.showModal()}>
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6" />
        <circle className="routing-info-dot" cx="12" cy="7" r="1" />
      </svg>
    </button>
    {createPortal(<dialog ref={dialog} className="product-modal routing-info-dialog" aria-labelledby={titleId} onClick={(event) => {
      if (event.target !== event.currentTarget) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.current?.close();
    }}>
      <div className="product-modal-header">
        <h3 id={titleId}>{title}</h3>
        <button className="product-modal-close" type="button" aria-label="Cerrar información" onClick={() => dialog.current?.close()}>×</button>
      </div>
      {children}
    </dialog>, document.body)}
  </>;
}
