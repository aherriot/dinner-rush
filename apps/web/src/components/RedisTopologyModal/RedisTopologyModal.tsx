import { Modal } from "../Modal/Modal";
import styles from "./RedisTopologyModal.module.css";

export interface StreamTopology {
  stream: string;
  groups: { group: string; does: string }[];
}

export interface RedisTopologyModalProps {
  open: boolean;
  onClose: () => void;
  streams: StreamTopology[];
}

/**
 * The system map's "click Redis, see the full picture" view — which
 * consumer group reads which stream and what it does with what it reads,
 * verified live against the running stack (`docker exec redis-1 redis-cli
 * XINFO GROUPS <stream>`, `systemMapState.ts`'s own comment on
 * `REDIS_TOPOLOGY_METRIC`), not the early planning doc in DECISIONS.md
 * §0003 (which predates two of these six groups).
 */
export function RedisTopologyModal({ open, onClose, streams }: RedisTopologyModalProps) {
  const groupCount = new Set(streams.flatMap((s) => s.groups.map((g) => g.group))).size;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Redis — streams and consumer groups"
      description={`${streams.length} streams, ${groupCount} distinct consumer groups — one stream per aggregate type (DECISIONS.md §0003), not per event type.`}
      hideActions
      size="wide"
    >
      <div className={styles.stack}>
        {streams.map((entry) => (
          <section key={entry.stream} className={styles.stream}>
            <h3 className={styles["stream-name"]}>{entry.stream}</h3>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col" className={styles.header}>
                    Consumer group
                  </th>
                  <th scope="col" className={styles.header}>
                    What it does
                  </th>
                </tr>
              </thead>
              <tbody>
                {entry.groups.map((row) => (
                  <tr key={row.group}>
                    <td className={styles.cell}>{row.group}</td>
                    <td className={styles["cell-prose"]}>{row.does}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))}
      </div>
    </Modal>
  );
}
