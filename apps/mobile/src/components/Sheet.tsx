import { type ReactNode, useEffect } from "react";

import { Icon } from "./Icon";

interface SheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}

/** Bottom sheet with a blurred backdrop; closes on backdrop click / Escape. */
export function Sheet({
  open,
  onClose,
  title,
  description,
  children,
}: SheetProps) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="sheet-backdrop">
      <button
        type="button"
        className="sheet-backdrop-close"
        onClick={onClose}
        aria-label="Закрыть окно"
      />
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title}>
        <div className="sheet-grabber" />
        <header className="sheet-head">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button
            type="button"
            className="btn-icon"
            onClick={onClose}
            aria-label="Закрыть"
          >
            <Icon name="close" size={18} />
          </button>
        </header>
        <div className="sheet-body">{children}</div>
      </div>
    </div>
  );
}
