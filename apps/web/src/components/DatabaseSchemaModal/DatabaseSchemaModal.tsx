import { useState } from "react";
import { Modal } from "../Modal/Modal";
import styles from "./DatabaseSchemaModal.module.css";

export interface SchemaColumn {
  name: string;
  type: string;
  primaryKey?: boolean;
  /** `"table.column"` this column is a foreign key into. */
  references?: string;
}

export interface SchemaTable {
  name: string;
  columns: SchemaColumn[];
}

export interface DatabaseSchemaModalProps {
  open: boolean;
  onClose: () => void;
  /** The real Postgres database name (e.g. "front_of_house"), used in the title. */
  databaseName: string;
  tables: SchemaTable[];
}

/**
 * The system map's "click a database, see its entity relationship" view —
 * every table and column here is verified directly against the running
 * database (`schemaData.ts`), not reconstructed from ORM naming
 * conventions. Each foreign-key column is annotated inline
 * (`table.column`) rather than drawn as a routed line between boxes: with
 * up to 11 tables (front_of_house) an auto-routed diagram would need real layout
 * work to stay readable, and a plain annotation says the same thing without
 * the risk of crossing, overlapping lines. Hovering or focusing a reference
 * instead highlights its target table's border — the same "trace the
 * relationship" payoff as a drawn line, without the routing work.
 */
export function DatabaseSchemaModal({ open, onClose, databaseName, tables }: DatabaseSchemaModalProps) {
  const [highlightedTable, setHighlightedTable] = useState<string | null>(null);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`${databaseName} — entity relationships`}
      description={`${tables.length} table${tables.length === 1 ? "" : "s"} — primary keys and foreign-key references, verified against the running database.`}
      hideActions
      size="wide"
    >
      <div className={styles.grid}>
        {tables.map((table) => (
          <table
            key={table.name}
            className={styles.table}
            data-highlighted={table.name === highlightedTable || undefined}
          >
            <caption className={styles.caption}>{table.name}</caption>
            <thead>
              <tr>
                <th scope="col" className={styles.header}>
                  Column
                </th>
                <th scope="col" className={styles.header}>
                  Type
                </th>
              </tr>
            </thead>
            <tbody>
              {table.columns.map((column) => {
                const referencedTable = column.references?.split(".")[0] ?? null;
                return (
                  <tr key={column.name}>
                    <td className={styles.cell}>
                      {column.name}
                      {column.primaryKey && (
                        <span className={styles.badge} title="Primary key">
                          PK
                        </span>
                      )}
                    </td>
                    <td className={styles.cell}>
                      <span className={styles.type}>{column.type}</span>
                      {column.references && (
                        <button
                          type="button"
                          className={styles.reference}
                          onMouseEnter={() => setHighlightedTable(referencedTable)}
                          onMouseLeave={() => setHighlightedTable(null)}
                          onFocus={() => setHighlightedTable(referencedTable)}
                          onBlur={() => setHighlightedTable(null)}
                        >
                          → {column.references}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ))}
      </div>
    </Modal>
  );
}
