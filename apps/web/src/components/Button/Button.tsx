import { Button as HeadlessButton } from "@headlessui/react";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import styles from "./Button.module.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "default" | "small";

export interface ButtonProps
  extends Omit<ComponentPropsWithoutRef<typeof HeadlessButton>, "className" | "children"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children?: ReactNode;
}

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: styles.primary,
  secondary: styles.secondary,
  ghost: styles.ghost,
  danger: styles.danger,
};

/** Token-styled wrapper around Headless UI's Button — see DESIGN.md §7. */
export function Button({ variant = "primary", size = "default", loading = false, disabled, children, ...props }: ButtonProps) {
  return (
    <HeadlessButton
      {...props}
      disabled={disabled ?? loading}
      aria-busy={loading || undefined}
      className={`${styles.button} ${VARIANT_CLASS[variant]} ${size === "small" ? styles.small : ""}`}
    >
      {loading && <span className={styles.spinner} aria-hidden="true" />}
      {children}
    </HeadlessButton>
  );
}
