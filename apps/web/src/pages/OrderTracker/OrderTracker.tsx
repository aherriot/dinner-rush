import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { OrderTimeline, type TimelineEvent } from "../../components/OrderTimeline/OrderTimeline";
import { Panel } from "../../components/Panel/Panel";
import { StatusPill } from "../../components/StatusPill/StatusPill";
import { Wordmark } from "../../design/Wordmark/Wordmark";
import type { OrderStatus } from "../../design/tokens";
import styles from "./OrderTracker.module.css";

type Order = components["schemas"]["Order"];

const POLL_INTERVAL_MS = 1500;

/**
 * Polls for updates — an explicit placeholder for Phase 3's websocket
 * fanout with last-event-id resume. Gets replaced, not extended.
 */
export function OrderTracker() {
  const { code } = useParams<{ code: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[] | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!code) return;
    let cancelled = false;

    async function poll() {
      const [orderResult, timelineResult] = await Promise.all([
        api.GET("/api/v1/orders/{code}", { params: { path: { code } } }),
        api.GET("/api/v1/orders/{code}/timeline", { params: { path: { code } } }),
      ]);
      if (cancelled) return;

      if (!orderResult.data) {
        setNotFound(true);
        return;
      }
      setOrder(orderResult.data);
      setTimeline((timelineResult.data as TimelineEvent[] | undefined) ?? null);
    }

    void poll();
    const interval = order && isTerminal(order.status) ? null : setInterval(() => void poll(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (interval) clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-armed once `order` settles into a terminal status
  }, [code, order?.status]);

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
              <p className={styles.reason}>Reason: {order.rejection_reason}</p>
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
