import { Button, Transition } from "@headlessui/react";
import type { ReactNode } from "react";
import styles from "./Toast.module.css";

export type ToastVariant = "info" | "success" | "warning" | "error";

const GLYPH: Record<ToastVariant, string> = {
  info: "ⓘ",
  success: "✓",
  warning: "▲",
  error: "✕",
};

export interface ToastProps {
  variant: ToastVariant;
  children: ReactNode;
  open?: boolean;
  onDismiss?: () => void;
}

/** A single toast. Headless UI's Transition drives enter/exit only — see
 * DESIGN.md §7; there is no Headless UI toast primitive. */
export function Toast({ variant, children, open = true, onDismiss }: ToastProps) {
  return (
    <Transition show={open} appear as="div" className={styles.toast} data-variant={variant} role="status">
      <span className={styles.glyph} aria-hidden="true">
        {GLYPH[variant]}
      </span>
      <div className={styles.body}>{children}</div>
      {onDismiss && (
        <Button className={styles.dismiss} onClick={onDismiss} aria-label="Dismiss">
          ✕
        </Button>
      )}
    </Transition>
  );
}

export function ToastStack({ children }: { children: ReactNode }) {
  return (
    <div className={styles.stack} aria-live="polite">
      {children}
    </div>
  );
}
