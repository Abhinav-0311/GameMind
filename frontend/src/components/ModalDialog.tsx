"use client";

import { useEffect, useRef, type ReactNode } from "react";

// Native modal dialogs provide top-layer rendering and background inertness.
export default function ModalDialog({ children, onClose, labelledBy, label, className = "", dismissible = true, returnFocusId }: {
  children: ReactNode;
  onClose: () => void;
  labelledBy?: string;
  label?: string;
  className?: string;
  dismissible?: boolean;
  returnFocusId?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const previousFocus = returnFocusId ? document.getElementById(returnFocusId) : document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.showModal();
    dialog.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [returnFocusId]);

  return (
    <dialog ref={ref} aria-labelledby={labelledBy} aria-label={label} tabIndex={-1}
      className={`app-dialog ${className}`}
      onCancel={(event) => { event.preventDefault(); if (dismissible) onClose(); }}
      onClick={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        if (event.target === event.currentTarget && dismissible
          && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
          'button:enabled, a[href], input:enabled, select:enabled, textarea:enabled, summary, [tabindex]:not([tabindex="-1"])'
        )).filter((item) => item.tabIndex >= 0 && item.getClientRects().length > 0);
        const first = items[0];
        const last = items[items.length - 1];
        if (!first) { event.preventDefault(); event.currentTarget.focus(); }
        else if (event.shiftKey && (document.activeElement === first || document.activeElement === event.currentTarget)) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === event.currentTarget)) {
          event.preventDefault(); first.focus();
        }
      }}>
      {children}
    </dialog>
  );
}
