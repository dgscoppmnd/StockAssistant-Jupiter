import { useLayoutEffect, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";

type Props = {
  anchor: RefObject<HTMLInputElement>;
  children: ReactNode;
};

// Render outside cards and scrolling dialogs so their stacking and overflow cannot clip the list.
export default function ComboboxPopup({ anchor, children }: Props) {
  const popup = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const element = popup.current;
    const input = anchor.current;
    if (!element || !input) return;
    const update = () => {
      const rect = (input.parentElement ?? input).getBoundingClientRect();
      const margin = 8;
      const gap = 4;
      const width = Math.min(rect.width, document.documentElement.clientWidth - margin * 2);
      element.style.width = `${Math.max(0, width)}px`;
      element.style.left = `${Math.max(margin, Math.min(rect.left, document.documentElement.clientWidth - width - margin))}px`;
      const below = Math.max(0, window.innerHeight - rect.bottom - gap - margin);
      const above = Math.max(0, rect.top - gap - margin);
      const desired = Math.min(300, element.scrollHeight);
      const upwards = below < desired && above > below;
      element.style.maxHeight = `${upwards ? above : below}px`;
      element.style.top = upwards ? "auto" : `${Math.max(margin, rect.bottom + gap)}px`;
      element.style.bottom = upwards ? `${Math.max(margin, window.innerHeight - rect.top + gap)}px` : "auto";
    };
    const onScroll = (event: Event) => {
      if (event.target instanceof Node && element.contains(event.target)) return;
      update();
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(input);
    observer.observe(element);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [anchor]);

  return createPortal(
    <div ref={popup} className="inventory-picker-popup combobox-floating-popup"
      onMouseDown={(event) => event.preventDefault()}>
      {children}
    </div>,
    document.body,
  );
}
