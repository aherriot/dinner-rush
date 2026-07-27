import { Menu, MenuButton, MenuItem, MenuItems, Radio, RadioGroup, Switch } from "@headlessui/react";
import type { ReactNode } from "react";
import styles from "./Toolbar.module.css";

export function Toolbar({ children }: { children: ReactNode }) {
  return <div className={styles.toolbar}>{children}</div>;
}

export interface SegmentedControlOption<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedControlProps<T extends string> {
  label: string;
  options: SegmentedControlOption<T>[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
}

export function SegmentedControl<T extends string>({ label, options, value, onChange, disabled }: SegmentedControlProps<T>) {
  return (
    <RadioGroup value={value} onChange={onChange} disabled={disabled} aria-label={label} className={styles.segmented}>
      {options.map((option) => (
        <Radio key={option.value} value={option.value} className={styles.segment}>
          {option.label}
        </Radio>
      ))}
    </RadioGroup>
  );
}

export interface ToggleGroupOption<T extends string> {
  value: T;
  label: string;
}

export interface ToggleGroupProps<T extends string> {
  options: ToggleGroupOption<T>[];
  selected: T[];
  onChange: (selected: T[]) => void;
  disabled?: boolean;
}

export function ToggleGroup<T extends string>({ options, selected, onChange, disabled }: ToggleGroupProps<T>) {
  return (
    <div className={styles["toggle-group"]}>
      {options.map((option) => (
        <Switch
          key={option.value}
          checked={selected.includes(option.value)}
          disabled={disabled}
          onChange={(checked) =>
            onChange(checked ? [...selected, option.value] : selected.filter((value) => value !== option.value))
          }
          className={styles.toggle}
        >
          {option.label}
        </Switch>
      ))}
    </div>
  );
}

export interface ActionMenuItem {
  key: string;
  label: string;
  onSelect: () => void;
}

export function ActionMenu({ label, items }: { label: string; items: ActionMenuItem[] }) {
  return (
    <Menu as="div" className={styles["menu-root"]}>
      <MenuButton className={styles["menu-button"]}>
        {label}
        <span aria-hidden="true">▾</span>
      </MenuButton>
      <MenuItems className={styles["menu-items"]}>
        {items.map((item) => (
          <MenuItem key={item.key}>
            <button type="button" className={styles["menu-item"]} onClick={item.onSelect}>
              {item.label}
            </button>
          </MenuItem>
        ))}
      </MenuItems>
    </Menu>
  );
}
