import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../../api/client";
import { BoardAuthProvider } from "../../auth/BoardAuthContext";
import { useBoardAuth } from "../../auth/useBoardAuth";
import { Button } from "../../components/Button/Button";
import { DispatchPanel } from "../../components/DispatchPanel/DispatchPanel";
import { KitchenPanel } from "../../components/KitchenPanel/KitchenPanel";
import { OrderFeed } from "../../components/OrderFeed/OrderFeed";
import { Panel } from "../../components/Panel/Panel";
import {
  StatusBar,
  type ChaosScenarioOption,
  type SpeedValue,
} from "../../components/StatusBar/StatusBar";
import { Wordmark } from "../../design/Wordmark/Wordmark";
import type { OrderStatus } from "../../design/tokens";
import styles from "./Board.module.css";
import {
  applyOrderEvent,
  lateRatioPercent,
  mapCouriers,
  mapOvens,
  mapTripLines,
  ordersPerMinute,
  toOrderFeedRows,
  type BoardOrder,
  type DispatchCourierRaw,
  type DispatchTripRaw,
  type KitchenOvenRaw,
  type KitchenTicketRaw,
} from "./boardState";
import { useBoardSocket, type BoardEnvelope } from "./useBoardSocket";

const CHAOS_SCENARIOS: ChaosScenarioOption[] = [
  { name: "friday_rush", label: "Friday rush" },
  { name: "oven_down", label: "Oven down" },
  { name: "courier_offline", label: "Courier offline" },
  { name: "ingredient_shortage", label: "Ingredient shortage" },
];

const TICK_INTERVAL_MS = 3000;
const RESYNC_DEBOUNCE_MS = 300;
// Courier position updates (`POST /couriers/{id}/position`) are Redis-only —
// no outbox event, per SPEC.md §1.3 ("nothing durable lives here") — so the
// board's *only* way to see a courier move is this periodic re-fetch. Match
// it to config.example.yaml's `position_report_interval_seconds: 5` (how
// often dispatch's autopilot reports a new position) so the dispatch map
// reads as continuous movement rather than 30-second jumps.
const PERIODIC_RESYNC_MS = 5_000;

export function Board() {
  return (
    <BoardAuthProvider>
      <BoardGate />
    </BoardAuthProvider>
  );
}

function BoardGate() {
  const { actor, loading } = useBoardAuth();

  if (loading) {
    return (
      <div className={styles.page} data-theme="dark">
        <Panel title="Dinner Rush board" state="loading" />
      </div>
    );
  }
  if (!actor) return <BoardLogin />;
  return <BoardDashboard />;
}

function BoardLogin() {
  const { login, error } = useBoardAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      setSubmitting(true);
      try {
        await login(username.trim(), password);
      } finally {
        setSubmitting(false);
      }
    },
    [username, password, login],
  );

  return (
    <div className={styles.page} data-theme="dark">
      <div className={styles["login-screen"]}>
        <Wordmark />
        <Panel title="Sign in — kitchen / manager">
          <form className={styles["login-form"]} onSubmit={(event) => void handleSubmit(event)}>
            <label className={styles["login-label"]}>
              Username
              <input
                className={styles["login-input"]}
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="manager"
              />
            </label>
            <label className={styles["login-label"]}>
              Password
              <input
                className={styles["login-input"]}
                type="password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="manager"
              />
            </label>
            <Button type="submit" disabled={submitting || !username || !password}>
              Sign in
            </Button>
            {error && <p className={styles["login-error"]}>{error}</p>}
            <p className={styles.hint}>
              Seeded demo staff — <code>manager/manager</code> or <code>kitchen/kitchen</code>.
            </p>
          </form>
        </Panel>
      </div>
    </div>
  );
}

interface BoardData {
  orders: BoardOrder[];
  ovens: KitchenOvenRaw[] | null;
  queue: KitchenTicketRaw[] | null;
  trips: DispatchTripRaw[] | null;
  couriers: DispatchCourierRaw[] | null;
}

function BoardDashboard() {
  const [data, setData] = useState<BoardData | null>(null);
  const [snapshotFailed, setSnapshotFailed] = useState(false);
  const [speed, setSpeed] = useState<SpeedValue>(1);
  const [activeScenarios, setActiveScenarios] = useState<string[]>([]);
  const [now, setNow] = useState(() => Date.now());

  const fetchSnapshot = useCallback(async () => {
    const { data: snapshot } = await api.GET("/api/v1/board/snapshot");
    if (!snapshot) {
      setSnapshotFailed(true);
      return;
    }
    setSnapshotFailed(false);
    setData({
      orders: snapshot.orders.map((order) => ({
        code: order.code,
        status: (order.status ?? "placed") as OrderStatus,
        late: order.late,
        placedAt: new Date(order.placed_at).getTime(),
      })),
      ovens: (snapshot.kitchen.ovens as KitchenOvenRaw[] | null) ?? null,
      queue: (snapshot.kitchen.queue as KitchenTicketRaw[] | null) ?? null,
      trips: (snapshot.dispatch.trips as DispatchTripRaw[] | null) ?? null,
      couriers: (snapshot.dispatch.couriers as DispatchCourierRaw[] | null) ?? null,
    });
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the initial cold-load fetch is exactly this effect's job
    void fetchSnapshot();
  }, [fetchSnapshot]);

  useEffect(() => {
    void api.GET("/api/v1/speed").then(({ data: speedData }) => {
      if (speedData) setSpeed(speedData.speed as SpeedValue);
    });
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), TICK_INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => void fetchSnapshot(), PERIODIC_RESYNC_MS);
    return () => clearInterval(timer);
  }, [fetchSnapshot]);

  const resyncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (resyncTimerRef.current) clearTimeout(resyncTimerRef.current);
  }, []);

  const debouncedResync = useCallback(() => {
    if (resyncTimerRef.current) clearTimeout(resyncTimerRef.current);
    resyncTimerRef.current = setTimeout(() => void fetchSnapshot(), RESYNC_DEBOUNCE_MS);
  }, [fetchSnapshot]);

  const handleBoardEvent = useCallback(
    (event: BoardEnvelope) => {
      setData((current) =>
        current ? { ...current, orders: applyOrderEvent(current.orders, event) } : current,
      );
      // Order events carry enough payload to update the feed directly
      // (above); oven/courier events don't carry enough to hand-patch slot
      // occupancy or courier position/status, so those instead trigger a
      // debounced re-fetch of the whole snapshot.
      if (event.stream === "events:oven" || event.stream === "events:courier") {
        debouncedResync();
      }
    },
    [debouncedResync],
  );

  const { connected } = useBoardSocket(handleBoardEvent);

  const handleSpeedChange = useCallback((nextSpeed: SpeedValue) => {
    setSpeed(nextSpeed);
    void api.POST("/api/v1/admin/speed", { body: { speed: nextSpeed } });
  }, []);

  const handleStartScenario = useCallback((name: string) => {
    setActiveScenarios((current) => (current.includes(name) ? current : [...current, name]));
    void api.POST("/api/v1/admin/scenarios/{name}/start", { params: { path: { name } } });
  }, []);

  const handleStopScenario = useCallback((name: string) => {
    setActiveScenarios((current) => current.filter((scenario) => scenario !== name));
    void api.POST("/api/v1/admin/scenarios/{name}/stop", { params: { path: { name } } });
  }, []);

  if (data === null && snapshotFailed) {
    return (
      <div className={styles.page} data-theme="dark">
        <div className={styles["error-screen"]}>
          <Panel title="Dinner Rush board" state="error" errorMessage="Gateway is unreachable." />
        </div>
      </div>
    );
  }

  const orders = data?.orders ?? [];

  return (
    <div className={styles.page} data-theme="dark">
      <div className={styles.grid}>
        <div className={styles["order-feed"]}>
          <OrderFeed orders={toOrderFeedRows(orders)} state={data === null ? "loading" : "idle"} />
        </div>
        <div className={styles.kitchen}>
          <KitchenPanel
            ovens={mapOvens(data?.ovens ?? null, now)}
            queueDepth={data?.queue?.length}
            state={data === null ? "loading" : data.ovens === null ? "error" : "idle"}
            errorMessage="Kitchen is unreachable."
          />
        </div>
        <div className={styles.dispatch}>
          <DispatchPanel
            couriers={mapCouriers(data?.couriers ?? null)}
            trips={mapTripLines(data?.trips ?? null)}
            activeTripCount={data?.trips?.length}
            state={data === null ? "loading" : data.couriers === null ? "error" : "idle"}
            errorMessage="Dispatch is unreachable."
          />
        </div>
        <div className={styles["status-bar"]}>
          <StatusBar
            speed={speed}
            onSpeedChange={handleSpeedChange}
            ordersPerMinute={ordersPerMinute(orders, now)}
            p95LatePercent={lateRatioPercent(orders)}
            scenarios={CHAOS_SCENARIOS}
            activeScenarios={activeScenarios}
            onStartScenario={handleStartScenario}
            onStopScenario={handleStopScenario}
            connected={connected}
          />
        </div>
      </div>
    </div>
  );
}
