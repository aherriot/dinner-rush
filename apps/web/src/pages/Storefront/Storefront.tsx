import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { components } from "../../api/schema";
import { useAuth } from "../../auth/useAuth";
import { Button } from "../../components/Button/Button";
import { Panel } from "../../components/Panel/Panel";
import { ToastStack, Toast } from "../../components/Toast/Toast";
import { Wordmark } from "../../design/Wordmark/Wordmark";
import styles from "./Storefront.module.css";

type MenuItem = components["schemas"]["MenuItem"];

function LoginForm() {
  const { login, error } = useAuth();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      setSubmitting(true);
      try {
        await login(email.trim());
      } finally {
        setSubmitting(false);
      }
    },
    [email, login],
  );

  return (
    <Panel title="Sign in">
      <form className={styles["login-form"]} onSubmit={handleSubmit}>
        <label className={styles["login-label"]}>
          Email
          <input
            className={styles["login-input"]}
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="ada@example.com"
          />
        </label>
        <Button type="submit" disabled={submitting || !email}>
          Sign in
        </Button>
        {error && <p className={styles["login-error"]}>{error}</p>}
        <p className={styles.hint}>
          Use a demo customer's email — seeded by <code>make seed</code>.
        </p>
      </form>
    </Panel>
  );
}

export function Storefront() {
  const { customer, loading: authLoading, logout } = useAuth();
  const navigate = useNavigate();
  const [menu, setMenu] = useState<MenuItem[] | null>(null);
  const [menuError, setMenuError] = useState(false);
  const [cart, setCart] = useState<Record<string, number>>({});
  const [placing, setPlacing] = useState(false);
  const [placeError, setPlaceError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.GET("/api/v1/menu").then(({ data, error }) => {
      if (cancelled) return;
      if (error) {
        setMenuError(true);
        return;
      }
      setMenu(data ?? []);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const addToCart = useCallback((sku: string) => {
    setCart((prev) => ({ ...prev, [sku]: (prev[sku] ?? 0) + 1 }));
  }, []);

  const removeFromCart = useCallback((sku: string) => {
    setCart((prev) => {
      const next = { ...prev };
      if (next[sku] <= 1) {
        delete next[sku];
      } else {
        next[sku] -= 1;
      }
      return next;
    });
  }, []);

  const cartLines = useMemo(() => {
    if (!menu) return [];
    return Object.entries(cart)
      .map(([sku, qty]) => ({ item: menu.find((m) => m.sku === sku), qty }))
      .filter((line): line is { item: MenuItem; qty: number } => Boolean(line.item));
  }, [cart, menu]);

  const subtotalCents = cartLines.reduce(
    (sum, line) => sum + line.item.base_price_cents * line.qty,
    0,
  );

  const placeOrder = useCallback(async () => {
    const address = customer?.addresses[0];
    if (!address) {
      setPlaceError("No delivery address on file.");
      return;
    }
    setPlacing(true);
    setPlaceError(null);
    const { data, error, response } = await api.POST("/api/v1/orders", {
      params: { header: { "Idempotency-Key": crypto.randomUUID() } },
      body: {
        address_id: address.id,
        items: cartLines.map((line) => ({ sku: line.item.sku, qty: line.qty })),
      },
    });
    setPlacing(false);
    if (!data) {
      setPlaceError(
        typeof error === "object" && error && "detail" in error
          ? String((error as { detail: unknown }).detail)
          : `Order failed (${response.status}).`,
      );
      return;
    }
    setCart({});
    navigate(`/orders/${data.code}`);
  }, [cartLines, customer, navigate]);

  if (authLoading) {
    return <div className={styles.page}>Loading…</div>;
  }

  return (
    <div className={styles.page} data-theme="light">
      <header className={styles.header}>
        <Wordmark />
        {customer && (
          <div className={styles["header-right"]}>
            <span className={styles.greeting}>Hi, {customer.name.split(" ")[0]}</span>
            <Button variant="ghost" size="small" onClick={logout}>
              Sign out
            </Button>
          </div>
        )}
      </header>

      {!customer ? (
        <LoginForm />
      ) : (
        <>
          <Panel
            title="Menu"
            state={menuError ? "error" : menu === null ? "loading" : menu.length === 0 ? "empty" : "idle"}
            errorMessage="Couldn't load the menu."
            emptyMessage="No items on the menu right now."
          >
            <ul className={styles["menu-list"]}>
              {menu?.map((item) => (
                <li key={item.sku} className={styles["menu-row"]}>
                  <div>
                    <p className={styles["menu-name"]}>{item.name}</p>
                    <p className={styles["menu-price"]}>
                      ${(item.base_price_cents / 100).toFixed(2)}
                    </p>
                  </div>
                  <Button
                    variant="secondary"
                    size="small"
                    disabled={item.available === false}
                    onClick={() => addToCart(item.sku)}
                  >
                    {item.available === false ? "Unavailable" : "Add"}
                  </Button>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Cart" state={cartLines.length === 0 ? "empty" : "idle"} emptyMessage="Your cart is empty.">
            <ul className={styles["cart-list"]}>
              {cartLines.map((line) => (
                <li key={line.item.sku} className={styles["cart-row"]}>
                  <span>
                    {line.qty}× {line.item.name}
                  </span>
                  <div className={styles["cart-row-actions"]}>
                    <span>${((line.item.base_price_cents * line.qty) / 100).toFixed(2)}</span>
                    <Button variant="ghost" size="small" onClick={() => removeFromCart(line.item.sku)}>
                      Remove
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
            {cartLines.length > 0 && (
              <div className={styles.checkout}>
                <p className={styles.subtotal}>Subtotal: ${(subtotalCents / 100).toFixed(2)}</p>
                <Button onClick={placeOrder} loading={placing} disabled={placing}>
                  Place order
                </Button>
              </div>
            )}
          </Panel>
        </>
      )}

      {placeError && (
        <ToastStack>
          <Toast variant="error" onDismiss={() => setPlaceError(null)}>
            {placeError}
          </Toast>
        </ToastStack>
      )}
    </div>
  );
}
