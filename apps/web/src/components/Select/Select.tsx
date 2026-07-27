import { Listbox, ListboxButton, ListboxOption, ListboxOptions } from "@headlessui/react";
import styles from "./Select.module.css";

export interface SelectOption<T extends string> {
  value: T;
  label: string;
}

export interface SelectProps<T extends string> {
  label?: string;
  options: SelectOption<T>[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
  error?: string;
}

/** Token-styled wrapper around Headless UI's Listbox — see DESIGN.md §7. */
export function Select<T extends string>({ label, options, value, onChange, disabled, error }: SelectProps<T>) {
  const selected = options.find((option) => option.value === value);
  return (
    <Listbox value={value} onChange={onChange} disabled={disabled}>
      <div className={styles.wrapper} data-error={error ? "" : undefined}>
        {label && <span className={styles.label}>{label}</span>}
        <ListboxButton className={styles.button}>
          <span>{selected?.label ?? "Select…"}</span>
          <span className={styles.chevron} aria-hidden="true">
            ▾
          </span>
        </ListboxButton>
        {error && <span className={styles["error-message"]}>{error}</span>}
        <ListboxOptions className={styles.options}>
          {options.map((option) => (
            <ListboxOption key={option.value} value={option.value} className={styles.option}>
              {option.label}
            </ListboxOption>
          ))}
        </ListboxOptions>
      </div>
    </Listbox>
  );
}
