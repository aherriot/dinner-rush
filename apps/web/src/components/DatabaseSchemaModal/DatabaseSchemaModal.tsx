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
 * the risk of crossing, overlapping lines.
 */
export function DatabaseSchemaModal({ open, onClose, databaseName, tables }: DatabaseSchemaModalProps) {
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
          <table key={table.name} className={styles.table}>
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
              {table.columns.map((column) => (
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
                      <span className={styles.reference}>→ {column.references}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
      </div>
    </Modal>
  );
}
