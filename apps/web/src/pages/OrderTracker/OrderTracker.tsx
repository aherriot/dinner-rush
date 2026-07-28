import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, getAccessToken } from "../../api/client";
import type { components } from "../../api/schema";
import { OrderTimeline, type TimelineEvent } from "../../components/OrderTimeline/OrderTimeline";
import { Panel } from "../../components/Panel/Panel";
import { StatusPill } from "../../components/StatusPill/StatusPill";
import { rejectionReasonLabel } from "../../design/rejectionReasons";
import { Wordmark } from "../../design/Wordmark/Wordmark";
import type { OrderStatus } from "../../design/tokens";
import styles from "./OrderTracker.module.css";

type Order = components["schemas"]["Order"];

const GATEWAY_WS_URL = (import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8000").replace(
  /^http/,
  "ws",
);
const RECONNECT_DELAY_MS = 2000;

/**
 * Live over `/ws/orders/{code}` (DECISIONS.md §0003) — a reconnect resumes
 * from the last event id it saw, so a mid-order refresh misses nothing. Each
 * pushed event just triggers a refetch rather than reconstructing state
 * client-side: the envelope carries the domain payload, but the order/
 * timeline REST shapes remain the single source of truth for what renders.
 */
export function OrderTracker() {
  const { code } = useParams<{ code: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[] | null>(null);
  const [notFound, setNotFound] = useState(false);
  const lastEventIdRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!code) return;
    let cancelled = false;
    let terminal = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    async function refetch(): Promise<Order | undefined> {
      const [orderResult, timelineResult] = await Promise.all([
        api.GET("/api/v1/orders/{code}", { params: { path: { code } } }),
        api.GET("/api/v1/orders/{code}/timeline", { params: { path: { code } } }),
      ]);
      if (cancelled) return undefined;

      if (!orderResult.data) {
        setNotFound(true);
        return undefined;
      }
      setOrder(orderResult.data);
      setTimeline((timelineResult.data as TimelineEvent[] | undefined) ?? null);
      terminal = isTerminal(orderResult.data.status);
      return orderResult.data;
    }

    function connect() {
      const token = getAccessToken();
      if (cancelled || terminal || !token) return;

      const params = new URLSearchParams({ token });
      if (lastEventIdRef.current) params.set("last_event_id", lastEventIdRef.current);
      socket = new WebSocket(`${GATEWAY_WS_URL}/ws/orders/${code}/?${params.toString()}`);

      socket.onmessage = (message: MessageEvent<string>) => {
        // `stream_id` is the Redis stream position (`<ms>-<seq>`) — the only
        // thing valid in `?last_event_id=` on reconnect. The envelope's own
        // `event_id` is a business UUID for a different purpose and isn't a
        // stream position at all; sending it back here is what used to
        // crash the connection on every reconnect (server-side `XRANGE`
        // rejects it outright).
        const payload = JSON.parse(message.data) as { stream_id: string };
        lastEventIdRef.current = payload.stream_id;
        void refetch().then(() => {
          // A terminal order produces no further events — close rather than
          // leave the socket idle waiting for pushes that will never come.
          if (terminal) socket?.close();
        });
      };
      socket.onclose = () => {
        if (!cancelled && !terminal) reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
    }

    void refetch().then((current) => {
      if (current && !terminal) connect();
    });

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [code]);

  return (
    <div className={styles.page} data-theme="light">
      <header className={styles.header}>
        <Link to="/" className={styles["wordmark-link"]}>
          <Wordmark />
        </Link>
      </header>

      <Panel
        title={code ? `Order ${code}` : "Order"}
        state={notFound ? "error" : order === null ? "loading" : "idle"}
        errorMessage="We couldn't find that order."
      >
        {order && (
          <div className={styles.summary}>
            <StatusPill status={order.status as OrderStatus} late={order.late} />
            <p className={styles.total}>${(order.total_cents / 100).toFixed(2)}</p>
            {order.rejection_reason && (
              <p className={styles.reason}>Reason: {rejectionReasonLabel(order.rejection_reason)}</p>
            )}
          </div>
        )}
      </Panel>

      <Panel title="Timeline">
        <OrderTimeline
          events={timeline ?? undefined}
          state={timeline === null ? "loading" : timeline.length === 0 ? "empty" : "idle"}
        />
      </Panel>
    </div>
  );
}

function isTerminal(status: string): boolean {
  return status === "delivered" || status === "rejected" || status === "failed";
}
