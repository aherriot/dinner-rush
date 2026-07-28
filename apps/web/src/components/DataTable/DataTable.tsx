import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import styles from "./DataTable.module.css";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  sortable?: boolean;
  render: (row: T) => ReactNode;
}

export type SortDirection = "asc" | "desc";
export type DataTableState = "idle" | "loading" | "empty";
export type DataTableDensity = "dense" | "default";

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  density?: DataTableDensity;
  sortKey?: string;
  sortDirection?: SortDirection;
  onSort?: (key: string) => void;
  state?: DataTableState;
  emptyMessage?: string;
  virtualize?: boolean;
  rowHeightPx?: number;
  viewportHeightPx?: number;
  overscan?: number;
  onRowClick?: (row: T) => void;
}

const SKELETON_ROWS = 6;

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  density = "dense",
  sortKey,
  sortDirection,
  onSort,
  state = "idle",
  emptyMessage = "Nothing here yet.",
  virtualize = false,
  rowHeightPx = 28,
  viewportHeightPx = 320,
  overscan = 6,
  onRowClick,
}: DataTableProps<T>) {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  function rowClickProps(row: T) {
    if (!onRowClick) return {};
    return {
      "data-clickable": "" as const,
      tabIndex: 0,
      onClick: () => onRowClick(row),
      onKeyDown: (event: KeyboardEvent<HTMLTableRowElement>) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        onRowClick(row);
      },
    };
  }

  const header = (
    <thead className={styles.head}>
      <tr>
        {columns.map((column) => (
          <th key={column.key} className={styles["header-cell"]}>
            {column.sortable ? (
              <button type="button" className={styles["sort-button"]} onClick={() => onSort?.(column.key)}>
                {column.header}
                {sortKey === column.key && (
                  <span className={styles["sort-glyph"]} aria-hidden="true">
                    {sortDirection === "desc" ? "▾" : "▴"}
                  </span>
                )}
              </button>
            ) : (
              column.header
            )}
          </th>
        ))}
      </tr>
    </thead>
  );

  if (state === "loading") {
    return (
      <div className={styles.wrapper}>
        <table className={styles.table}>
          {header}
          <tbody>
            {Array.from({ length: SKELETON_ROWS }, (_, index) => (
              <tr key={index} className={styles["skeleton-row"]} aria-hidden="true">
                <td colSpan={columns.length}>
                  <div className={styles["skeleton-fill"]} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <span className={styles["sr-only"]} role="status">
          Loading
        </span>
      </div>
    );
  }

  if (state === "empty" || rows.length === 0) {
    return (
      <div className={styles.wrapper}>
        <table className={styles.table}>{header}</table>
        <div className={styles.state} role="status">
          {emptyMessage}
        </div>
      </div>
    );
  }

  if (!virtualize) {
    return (
      <div className={styles.wrapper}>
        <table className={styles.table}>
          {header}
          <tbody>
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                className={styles.row}
                data-density={density}
                {...rowClickProps(row)}
              >
                {columns.map((column) => (
                  <td key={column.key} className={styles.cell}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const totalHeight = rows.length * rowHeightPx;
  const firstVisible = Math.max(0, Math.floor(scrollTop / rowHeightPx) - overscan);
  const visibleCount = Math.ceil(viewportHeightPx / rowHeightPx) + overscan * 2;
  const lastVisible = Math.min(rows.length, firstVisible + visibleCount);
  const visibleRows = rows.slice(firstVisible, lastVisible);

  return (
    <div
      ref={containerRef}
      className={styles.wrapper}
      style={{ maxHeight: viewportHeightPx }}
      onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
    >
      <table className={styles.table}>
        {header}
        <tbody>
          <tr aria-hidden="true">
            <td colSpan={columns.length} style={{ padding: 0, height: firstVisible * rowHeightPx }} />
          </tr>
          {visibleRows.map((row) => (
            <tr
              key={rowKey(row)}
              className={styles.row}
              data-density={density}
              {...rowClickProps(row)}
            >
              {columns.map((column) => (
                <td key={column.key} className={styles.cell}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
          <tr aria-hidden="true">
            <td colSpan={columns.length} style={{ padding: 0, height: totalHeight - lastVisible * rowHeightPx }} />
          </tr>
        </tbody>
      </table>
    </div>
  );
}
