import { Disclosure, DisclosureButton, DisclosurePanel } from "@headlessui/react";
import type { ReactNode } from "react";
import styles from "./Panel.module.css";

export type PanelState = "idle" | "loading" | "empty" | "error";

export interface PanelProps {
  title?: string;
  toolbar?: ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
  state?: PanelState;
  errorMessage?: string;
  emptyMessage?: string;
  children?: ReactNode;
}

function PanelBody({ state, errorMessage, emptyMessage, children }: Pick<PanelProps, "state" | "errorMessage" | "emptyMessage" | "children">) {
  if (state === "loading") {
    return (
      <div className={styles.body} aria-busy="true">
        <div className={styles.skeleton} data-testid="panel-skeleton">
          <div className={styles["skeleton-row"]} />
          <div className={styles["skeleton-row"]} />
          <div className={styles["skeleton-row"]} />
        </div>
      </div>
    );
  }
  if (state === "empty") {
    return (
      <div className={styles.state} role="status">
        {emptyMessage ?? "Nothing here yet."}
      </div>
    );
  }
  if (state === "error") {
    return (
      <div className={`${styles.state} ${styles.error}`} role="alert">
        {errorMessage ?? "Something went wrong."}
      </div>
    );
  }
  return <div className={styles.body}>{children}</div>;
}

export function Panel({ title, toolbar, collapsible = false, defaultOpen = true, state = "idle", errorMessage, emptyMessage, children }: PanelProps) {
  const header = title && (
    <div className={styles.header}>
      {collapsible ? (
        <DisclosureButton className={styles["disclosure-button"]}>
          <h3 className={styles.title}>{title}</h3>
          <span className={styles.chevron} aria-hidden="true">
            ▸
          </span>
        </DisclosureButton>
      ) : (
        <h3 className={styles.title}>{title}</h3>
      )}
      {toolbar}
    </div>
  );

  const body = <PanelBody state={state} errorMessage={errorMessage} emptyMessage={emptyMessage}>{children}</PanelBody>;

  if (collapsible) {
    return (
      <Disclosure as="section" className={styles.panel} defaultOpen={defaultOpen}>
        {header}
        <DisclosurePanel>{body}</DisclosurePanel>
      </Disclosure>
    );
  }

  return (
    <section className={styles.panel}>
      {header}
      {body}
    </section>
  );
}
