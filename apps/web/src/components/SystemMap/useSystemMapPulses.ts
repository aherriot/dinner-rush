import { useCallback, useEffect, useRef, useState } from "react";
import {
  httpPulseForEventType,
  pulsePlanForEvent,
  type EdgeId,
} from "./systemMapState";

export interface ActivePulse {
  /** Unique per rendered instance, not domain data — a React key and
   * nothing else. */
  id: string;
  edgeId: EdgeId;
}

/**
 * Schedules the transient "a data packet just moved along this edge" pulses
 * `SystemMap` renders, from real board activity: live socket events
 * (`notifyEvent`) and the board's own outgoing HTTP calls (`notifyEdges`,
 * for the periodic snapshot poll and admin actions). Kept as a hook
 * separate from the presentational `SystemMap` component so Storybook can
 * pass a fixed `pulses` list instead of driving the real timers.
 */
export function useSystemMapPulses(pulseDurationMs: number): {
  pulses: ActivePulse[];
  notifyEvent: (event: { producer: string; event_type: string }) => void;
  notifyEdges: (edgeIds: EdgeId[]) => void;
} {
  const [pulses, setPulses] = useState<ActivePulse[]>([]);
  const nextId = useRef(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
    },
    [],
  );

  const schedule = useCallback(
    (edgeId: EdgeId, delayMs: number) => {
      const id = `pulse-${nextId.current++}`;
      const start = () => {
        setPulses((current) => [...current, { id, edgeId }]);
        timers.current.push(
          setTimeout(() => {
            setPulses((current) => current.filter((pulse) => pulse.id !== id));
          }, pulseDurationMs),
        );
      };
      // Zero delay applies immediately rather than through a macrotask —
      // otherwise every event's first stage would render a tick late.
      if (delayMs <= 0) start();
      else timers.current.push(setTimeout(start, delayMs));
    },
    [pulseDurationMs],
  );

  const notifyEvent = useCallback(
    (event: { producer: string; event_type: string }) => {
      for (const step of pulsePlanForEvent(event)) {
        schedule(step.edgeId, step.delayMs);
      }
      const httpEdge = httpPulseForEventType(event.event_type);
      if (httpEdge) schedule(httpEdge, 0);
    },
    [schedule],
  );

  const notifyEdges = useCallback(
    (edgeIds: EdgeId[]) => {
      for (const edgeId of edgeIds) schedule(edgeId, 0);
    },
    [schedule],
  );

  return { pulses, notifyEvent, notifyEdges };
}
