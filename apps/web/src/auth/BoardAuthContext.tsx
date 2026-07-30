import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setAccessToken } from "../api/client";
import { BoardAuthContext, type StaffActor, type StaffRole } from "./boardContext";

const STORAGE_KEY = "dinner-rush:board-access-token";
const BOARD_ROLES: StaffRole[] = ["kitchen", "manager"];

function isStaffRole(role: unknown): role is StaffRole {
  return typeof role === "string" && (BOARD_ROLES as string[]).includes(role);
}

/**
 * Separate from the customer-facing `AuthContext` — the board is a
 * different actor type (kitchen/manager staff, username+password) rather
 * than a variant of customer auth, so it gets its own token
 * (`dinner-rush:board-access-token`) and its own login shape rather than a
 * union bolted onto `AuthContext.customer`.
 */
export function BoardAuthProvider({ children }: { children: ReactNode }) {
  const [actor, setActor] = useState<StaffActor | null>(null);
  const [loading, setLoading] = useState(() => Boolean(sessionStorage.getItem(STORAGE_KEY)));
  const [error, setError] = useState<string | null>(null);

  const loadMe = useCallback(async () => {
    const { data } = await api.GET("/api/v1/me");
    // `GET /me`'s declared schema is customer-shaped; the live endpoint
    // returns `{role, id, name}` for staff (front_of_house/accounts/views.py's
    // `MeView`) — not modelled precisely in the generated types, so this is
    // a deliberate runtime cast at the one boundary where that mismatch
    // matters.
    const body = data as unknown as { role?: string; id?: string; name?: string } | undefined;
    if (body && isStaffRole(body.role) && body.id && body.name) {
      setActor({ role: body.role, id: body.id, name: body.name });
    } else {
      setActor(null);
    }
  }, []);

  useEffect(() => {
    const token = sessionStorage.getItem(STORAGE_KEY);
    if (!token) {
      return;
    }
    setAccessToken(token);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- resolving the stored token into an actor is exactly this effect's job
    void loadMe().finally(() => setLoading(false));
  }, [loadMe]);

  const login = useCallback(
    async (username: string, password: string) => {
      setError(null);
      const { data } = await api.POST("/api/v1/auth/token", { body: { username, password } });
      if (!data) {
        setError("Invalid username or password — try manager/manager or kitchen/kitchen.");
        return;
      }
      setAccessToken(data.access);
      sessionStorage.setItem(STORAGE_KEY, data.access);
      await loadMe();
    },
    [loadMe],
  );

  const logout = useCallback(() => {
    setAccessToken(null);
    sessionStorage.removeItem(STORAGE_KEY);
    setActor(null);
  }, []);

  const value = useMemo(
    () => ({ actor, loading, error, login, logout }),
    [actor, loading, error, login, logout],
  );

  return <BoardAuthContext.Provider value={value}>{children}</BoardAuthContext.Provider>;
}
