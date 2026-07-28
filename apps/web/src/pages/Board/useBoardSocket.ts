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

const GATEWAY_WS_URL = (import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8000").replace(
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
export function useBoardSocket(onEvent: (event: BoardEnvelope) => void): { connected: boolean } {
  const onEventRef = useRef(onEvent);
  useLayoutEffect(() => {
    onEventRef.current = onEvent;
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

      socket = new WebSocket(`${GATEWAY_WS_URL}/ws/board/?${params.toString()}`);

      socket.onopen = () => {
        if (!cancelled) setConnected(true);
      };
      socket.onmessage = (message: MessageEvent<string>) => {
        const event = JSON.parse(message.data) as BoardEnvelope;
        lastEventIds[event.stream] = event.stream_id;
        onEventRef.current(event);
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
