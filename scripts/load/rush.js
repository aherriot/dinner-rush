// `make load` (PHASES.md Phase 9) — a genuine dinner rush through the public
// API, the same one a browser or the simulator hits. Ramps orders/minute
// well past the kitchen's configured capacity (config.example.yaml's
// `kitchen.capacity`) so the artifact this writes proves both throughput
// *and* backpressure in one run, rather than needing two.
//
// Run via `make load` (wraps `docker compose --profile load run k6`), which
// mounts this file read-only and writes `docs/load/latest.json` — see the
// Makefile for the exact command, printed next to the number when it's
// quoted anywhere (CLAUDE.md: "claims need artifacts").
import exec from "k6/execution";
import http from "k6/http";
import { Counter } from "k6/metrics";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://front-of-house:8000";

const ordersAccepted = new Counter("orders_accepted");
const ordersRejected = new Counter("orders_rejected");
const ordersFailed = new Counter("orders_failed");

// Fixed seed customers from `make seed` (orders/management/commands/seed.py)
// — email-only auth, no password, so there's no credential to manage here.
const CUSTOMER_EMAILS = ["ada@example.com", "grace@example.com", "alan@example.com"];

export const options = {
  scenarios: {
    rush: {
      executor: "ramping-arrival-rate",
      // Rates are orders/minute directly — the same number the board's
      // status bar and the README's throughput claim both use.
      startRate: 5,
      timeUnit: "1m",
      preAllocatedVUs: 150,
      maxVUs: 500,
      stages: [
        { target: 20, duration: "15s" }, // baseline: calm, orders flowing
        { target: 400, duration: "15s" }, // the rush: past configured capacity
        { target: 400, duration: "40s" }, // hold — this is where rejections happen
        { target: 0, duration: "10s" }, // drain
      ],
    },
  },
  thresholds: {
    // A load test that can't reach the API at all is a setup failure, not
    // a capacity finding — distinct from `orders_rejected`, which is the
    // point of this run, not a failure of it.
    http_req_failed: ["rate<0.05"],
  },
};

function authHeaders(token) {
  return { headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } };
}

/** Runs once before the load starts (not once per VU): authenticates the
 * fixed customer pool, resolves each one's seeded address, sets SPEED=60
 * via the same admin endpoint the board's speed control uses (so a 7-minute
 * bake takes 7 real seconds — otherwise this run would need to last longer
 * than a demo ever does to see a single order finish), and fetches the live
 * menu rather than hand-duplicating config.example.yaml's SKUs here. */
export function setup() {
  const managerToken = authenticate({ username: "manager", password: "manager" });
  const speedRes = http.post(
    `${BASE_URL}/api/v1/admin/speed`,
    JSON.stringify({ speed: 60 }),
    authHeaders(managerToken),
  );
  check(speedRes, { "SPEED set to 60": (r) => r.status === 200 });

  const pool = CUSTOMER_EMAILS.map((email) => {
    const token = authenticate({ email });
    const me = http.get(`${BASE_URL}/api/v1/me`, authHeaders(token));
    if (me.status !== 200) {
      throw new Error(`GET /api/v1/me failed for ${email}: ${me.status} ${me.body}`);
    }
    const customer = JSON.parse(me.body);
    if (!customer.addresses || customer.addresses.length === 0) {
      throw new Error(`${email} has no seeded address — has \`make seed\` run?`);
    }
    return { token, addressId: customer.addresses[0].id };
  });

  const menuRes = http.get(`${BASE_URL}/api/v1/menu`);
  if (menuRes.status !== 200) {
    throw new Error(`GET /api/v1/menu failed: ${menuRes.status} ${menuRes.body}`);
  }
  const skus = JSON.parse(menuRes.body)
    .filter((item) => item.available !== false)
    .map((item) => item.sku);
  if (skus.length === 0) {
    throw new Error("menu returned zero available items — has `make seed` run?");
  }

  return { pool, skus };
}

function authenticate(credentials) {
  const res = http.post(`${BASE_URL}/api/v1/auth/token`, JSON.stringify(credentials), {
    headers: { "Content-Type": "application/json" },
  });
  if (res.status !== 200) {
    throw new Error(
      `POST /api/v1/auth/token failed for ${JSON.stringify(credentials)}: ${res.status}`,
    );
  }
  return JSON.parse(res.body).access;
}

function randomCart(skus) {
  const itemCount = 1 + Math.floor(Math.random() * 3); // 1-3 line items
  const items = [];
  for (let i = 0; i < itemCount; i++) {
    items.push({
      sku: skus[Math.floor(Math.random() * skus.length)],
      qty: 1 + Math.floor(Math.random() * 2),
    });
  }
  return items;
}

export default function (data) {
  const customer = data.pool[exec.vu.idInTest % data.pool.length];
  const idempotencyKey = `k6-${exec.vu.idInTest}-${exec.scenario.iterationInTest}-${Date.now()}`;

  const res = http.post(
    `${BASE_URL}/api/v1/orders`,
    JSON.stringify({ address_id: customer.addressId, items: randomCart(data.skus) }),
    {
      headers: {
        Authorization: `Bearer ${customer.token}`,
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
    },
  );

  const ok = check(res, {
    "order request succeeded (201 accepted or 202 rejected)": (r) =>
      r.status === 201 || r.status === 202,
  });

  if (!ok) {
    ordersFailed.add(1);
  } else if (res.status === 201) {
    ordersAccepted.add(1);
  } else {
    ordersRejected.add(1);
  }

  sleep(0.1);
}

function round1(n) {
  return typeof n === "number" ? Math.round(n * 10) / 10 : null;
}

/** Writes `docs/load/latest.json` — a small, hand-picked summary rather
 * than k6's full metrics dump, so the number quoted in a README is the
 * same one a human reads here, not one they had to go dig for. */
export function handleSummary(data) {
  const accepted = data.metrics.orders_accepted?.values.count ?? 0;
  const rejected = data.metrics.orders_rejected?.values.count ?? 0;
  const failed = data.metrics.orders_failed?.values.count ?? 0;
  const total = accepted + rejected + failed;
  const durationSeconds = data.state.testRunDurationMs / 1000;

  const summary = {
    generated_at: new Date().toISOString(),
    command: "make load",
    duration_seconds: Math.round(durationSeconds),
    speed: 60,
    orders: {
      total,
      accepted,
      rejected,
      failed,
      accepted_per_minute: Math.round((accepted / durationSeconds) * 60),
      rejection_rate_percent: total > 0 ? Math.round((rejected / total) * 1000) / 10 : 0,
    },
    http_req_duration_ms: {
      // k6's default trend stats are avg/min/med/max/p(90)/p(95) — "med" is
      // the p50, not "p(50)" (which isn't collected unless added to
      // summaryTrendStats).
      p50: round1(data.metrics.http_req_duration?.values["med"]),
      p95: round1(data.metrics.http_req_duration?.values["p(95)"]),
    },
    http_req_failed_rate_percent:
      Math.round((data.metrics.http_req_failed?.values.rate ?? 0) * 1000) / 10,
  };

  return {
    "/out/latest.json": JSON.stringify(summary, null, 2) + "\n",
    stdout: JSON.stringify(summary, null, 2) + "\n",
  };
}
