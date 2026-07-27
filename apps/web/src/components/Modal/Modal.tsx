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
}: ModalProps) {
  return (
    <Dialog open={open} onClose={onClose} transition>
      <DialogBackdrop transition className={styles.backdrop} />
      <div className={styles.viewport}>
        <DialogPanel transition className={styles.panel}>
          <DialogTitle className={styles.title}>{title}</DialogTitle>
          {description && <Description className={styles.description}>{description}</Description>}
          {children}
          <div className={styles.actions}>
            <Button variant="ghost" onClick={onClose}>
              {cancelLabel}
            </Button>
            <Button variant={destructive ? "danger" : "primary"} onClick={onConfirm ?? onClose}>
              {confirmLabel}
            </Button>
          </div>
        </DialogPanel>
      </div>
    </Dialog>
  );
}
