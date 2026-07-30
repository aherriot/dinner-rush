import { Dialog, DialogBackdrop, DialogPanel, DialogTitle, Description } from "@headlessui/react";
import type { ReactNode } from "react";
import { Button } from "../Button/Button";
import styles from "./Modal.module.css";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm?: () => void;
  destructive?: boolean;
  /** Omits the confirm/cancel row entirely, for a read-only modal (e.g. the
   * board's order drill-in) that has nothing to confirm — Headless UI's
   * `Dialog` already closes on `Escape`/backdrop click via `onClose`. */
  hideActions?: boolean;
  /** `"default"` (400px) fits a confirm dialog; `"wide"` (960px) is for
   * content-heavy read-only views (e.g. the system map's database/Redis
   * detail views) that would otherwise wrap into an unreadable column. */
  size?: "default" | "wide";
}

/** Token-styled wrapper around Headless UI's Dialog — see DESIGN.md §7. */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  destructive = false,
  hideActions = false,
  size = "default",
}: ModalProps) {
  return (
    <Dialog open={open} onClose={onClose} transition>
      <DialogBackdrop transition className={styles.backdrop} />
      <div className={styles.viewport}>
        <DialogPanel transition className={styles.panel} data-size={size}>
          <DialogTitle className={styles.title}>{title}</DialogTitle>
          {description && <Description className={styles.description}>{description}</Description>}
          {children}
          {!hideActions && (
            <div className={styles.actions}>
              <Button variant="ghost" onClick={onClose}>
                {cancelLabel}
              </Button>
              <Button variant={destructive ? "danger" : "primary"} onClick={onConfirm ?? onClose}>
                {confirmLabel}
              </Button>
            </div>
          )}
        </DialogPanel>
      </div>
    </Dialog>
  );
}
