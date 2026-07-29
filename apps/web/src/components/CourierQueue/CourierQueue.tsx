import { CourierDot, type CourierStatus } from "../CourierDot/CourierDot";
import { Panel, type PanelState } from "../Panel/Panel";
import styles from "./CourierQueue.module.css";

export type TripPhase = "assigned" | "picked_up" | "delivering";

export interface QueuedTrip {
  id: string;
  code: string;
  /** Dispatch's own trip FSM phase (SPEC.md §2) — which leg of the run this
   * courier is actually on, not just "has an active trip." */
  status: TripPhase;
  /** Epoch ms — compared against `now` to render "on time" / "Nm late". */
  etaAtMs: number;
}

export interface CourierRosterEntry {
  id: string;
  name: string;
  status: CourierStatus;
  /** In assignment order — dispatch's `GET /trips` already sorts this way,
   * so this component never re-sorts, only groups. */
  trips: QueuedTrip[];
}

export interface BacklogSummary {
  readyCount: number;
  /** `null` when `readyCount` is 0 — there is no "oldest" of an empty set. */
  oldestWaitingSeconds: number | null;
}

export interface CourierQueueProps {
  couriers?: CourierRosterEntry[];
  /** `undefined`/`null` means dispatch didn't answer this field at all
   * (degraded, not empty) — rendered distinctly from a confirmed-empty
   * backlog so a stale board can't be read as "all clear". */
  backlog?: BacklogSummary | null;
  now: number;
  state?: PanelState;
  errorMessage?: string;
}

/** "<1m" / "4m" / "23m" — never "0m", so a backlog that just started waiting
 * doesn't read as no time having passed at all. Not exported: it's an
 * internal formatting detail, not part of this component's public shape
 * (react-refresh's rule against non-component value exports from a
 * component file — same reason `DispatchPanel`'s `toPercent` stays
 * private). Covered indirectly by this component's own rendering tests. */
function formatMinutes(totalSeconds: number): string {
  const minutes = Math.round(totalSeconds / 60);
  return minutes <= 0 ? "<1m" : `${minutes}m`;
}

/** What a courier is actually doing right now, in the same words a human
 * dispatcher would use — the trip phase alone ("assigned") doesn't say
 * whether that means "driving to the restaurant" or "driving to the
 * customer." */
const TRIP_PHASE_LABEL: Record<TripPhase, string> = {
  assigned: "Heading to pickup",
  picked_up: "Picked up",
  delivering: "Delivering",
};

/** A courier with no active trips is either off shift or waiting at the
 * restaurant for the next one — distinct enough states that "No active
 * trips" alone left the question the roster exists to answer unanswered. */
const IDLE_COURIER_LABEL: Record<CourierStatus, string> = {
  offline: "Offline",
  idle: "Idle at base",
  active: "No active trips",
};

interface TripEtaStatus {
  late: boolean;
  label: string;
}

/** A trip is "late" the instant `now` passes its `eta_at` — no grace window,
 * since dispatch's own ETA already bakes in travel time (SPEC.md's `eta_at`
 * is a real courier-speed estimate, not padded). */
function tripEtaStatus(etaAtMs: number, nowMs: number): TripEtaStatus {
  const overdueMs = nowMs - etaAtMs;
  if (overdueMs <= 0) return { late: false, label: "on time" };
  return { late: true, label: `${formatMinutes(overdueMs / 1000)} late` };
}

/**
 * The board's courier roster (PIZZA.md's "where did dispatch's own backlog
 * go" gap) — every courier, their trips in assignment order with an
 * elapsed-vs-ETA readout, and a backlog callout for orders `ready` with no
 * trip at all. `DispatchPanel`'s map answers "where is everyone"; this
 * answers "is anyone actually behind, and is anything stuck waiting for a
 * courier that was never assigned."
 */
export function CourierQueue({
  couriers = [],
  backlog,
  now,
  state = "idle",
  errorMessage,
}: CourierQueueProps) {
  const backlogKnown = backlog !== undefined && backlog !== null;
  const hasBacklog = backlogKnown && backlog.readyCount > 0;

  return (
    <Panel
      title="Courier queue"
      state={couriers.length === 0 && state === "idle" ? "empty" : state}
      errorMessage={errorMessage}
      emptyMessage="No couriers online."
    >
      <div className={styles.body}>
        <div
          className={styles.backlog}
          data-alert={hasBacklog || undefined}
          data-ok={(backlogKnown && !hasBacklog) || undefined}
          role="status"
        >
          <span className={styles["backlog-glyph"]} aria-hidden="true">
            {!backlogKnown ? "?" : hasBacklog ? "!" : "✓"}
          </span>
          <span>
            {!backlogKnown
              ? "Backlog unknown"
              : hasBacklog
                ? `${backlog.readyCount} ready, oldest waiting ${formatMinutes(backlog.oldestWaitingSeconds ?? 0)}`
                : "No backlog"}
          </span>
        </div>
        <ul className={styles.roster}>
          {couriers.map((courier) => (
            <li key={courier.id} className={styles.courier}>
              <div className={styles["courier-header"]}>
                <CourierDot status={courier.status} name={courier.name} />
                <span className={styles["courier-name"]}>{courier.name}</span>
              </div>
              {courier.trips.length === 0 ? (
                <p className={styles["no-trips"]}>{IDLE_COURIER_LABEL[courier.status]}</p>
              ) : (
                <ol className={styles.trips}>
                  {courier.trips.map((trip) => {
                    const eta = tripEtaStatus(trip.etaAtMs, now);
                    return (
                      <li key={trip.id} className={styles.trip}>
                        <div className={styles["trip-row"]}>
                          <span className={styles["trip-code"]}>{trip.code}</span>
                          <span className={styles["trip-eta"]} data-late={eta.late || undefined}>
                            {eta.label}
                          </span>
                        </div>
                        <span className={styles["trip-phase"]}>
                          {TRIP_PHASE_LABEL[trip.status]}
                        </span>
                      </li>
                    );
                  })}
                </ol>
              )}
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}
