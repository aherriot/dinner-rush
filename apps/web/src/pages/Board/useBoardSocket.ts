import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getAccessToken } from "../../api/client";

export type BoardStream = "events:order" | "events:oven" | "events:courier";

const STREAM_QUERY_PARAM: Record<BoardStream, string> = {
  "events:order": "last_event_id_order",
  "events:oven": "last_event_id_oven",
  "events:courier": "last_event_id_courier",
};

export interface BoardEnvelope {
  event_id: string;
  event_type: string;
  event_version: number;
  occurred_at: string;
  aggregate_type: string;
  aggregate_id: string;
  sequence: number;
  correlation_id: string;
  causation_id: string | null;
  producer: string;
  payload: Record<string, unknown>;
  stream_id: string;
  stream: BoardStream;
}

/** Pushed every ~5s from Prometheus by front-of-house's `push_board_metrics`
 * Celery beat task (Phase 9) over the same socket as domain events, the one
 * message shape here that isn't a `BoardEnvelope` — discriminated by its own
 * `type` field, which domain events never carry on the wire. Either field
 * is `null` when Prometheus didn't answer in time; that's "no data yet", not
 * "zero". */
export interface BoardMetricsMessage {
  type: "board.metrics";
  stream_pending: number | null;
  promise_error_p95_seconds: number | null;
}

type BoardSocketMessage = BoardEnvelope | BoardMetricsMessage;

function isBoardMetricsMessage(message: BoardSocketMessage): message is BoardMetricsMessage {
  return (message as BoardMetricsMessage).type === "board.metrics";
}

const FRONT_OF_HOUSE_WS_URL = (import.meta.env.VITE_FRONT_OF_HOUSE_URL ?? "http://localhost:8000").replace(
  /^http/,
  "ws",
);
const RECONNECT_DELAY_MS = 2000;

/**
 * Live over `/ws/board` (SPEC.md §3.1) — three streams (`events:order`,
 * `events:oven`, `events:courier`, DECISIONS.md §0003) multiplexed onto one
 * socket, each tracking its own `last_event_id` for resumption
 * independently. Unlike `OrderTracker`'s socket (which triggers a REST
 * refetch per push, since a single order's REST shape is small and cheap to
 * re-fetch), every board event is applied directly to caller-held state —
 * refetching the whole board on every one of potentially dozens of
 * events/second would defeat the point of a push feed.
 */
export function useBoardSocket(
  onEvent: (event: BoardEnvelope) => void,
  onMetrics?: (message: BoardMetricsMessage) => void,
): { connected: boolean } {
  const onEventRef = useRef(onEvent);
  useLayoutEffect(() => {
    onEventRef.current = onEvent;
  });
  const onMetricsRef = useRef(onMetrics);
  useLayoutEffect(() => {
    onMetricsRef.current = onMetrics;
  });
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    const lastEventIds: Partial<Record<BoardStream, string>> = {};

    function connect() {
      const token = getAccessToken();
      if (cancelled || !token) return;

      const params = new URLSearchParams({ token });
      for (const [stream, queryParam] of Object.entries(STREAM_QUERY_PARAM) as [
        BoardStream,
        string,
      ][]) {
        const lastEventId = lastEventIds[stream];
        if (lastEventId) params.set(queryParam, lastEventId);
      }

      socket = new WebSocket(`${FRONT_OF_HOUSE_WS_URL}/ws/board/?${params.toString()}`);

      socket.onopen = () => {
        if (!cancelled) setConnected(true);
      };
      socket.onmessage = (message: MessageEvent<string>) => {
        const parsed = JSON.parse(message.data) as BoardSocketMessage;
        if (isBoardMetricsMessage(parsed)) {
          onMetricsRef.current?.(parsed);
          return;
        }
        lastEventIds[parsed.stream] = parsed.stream_id;
        onEventRef.current(parsed);
      };
      socket.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return { connected };
}
