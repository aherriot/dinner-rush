import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setAccessToken } from "../api/client";
import type { components } from "../api/schema";
import { AuthContext } from "./context";

type Customer = components["schemas"]["Customer"];

const STORAGE_KEY = "dinner-rush:access-token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(() => Boolean(sessionStorage.getItem(STORAGE_KEY)));
  const [error, setError] = useState<string | null>(null);

  const loadMe = useCallback(async () => {
    const { data } = await api.GET("/api/v1/me");
    setCustomer(data ?? null);
  }, []);

  useEffect(() => {
    const token = sessionStorage.getItem(STORAGE_KEY);
    if (!token) {
      return;
    }
    setAccessToken(token);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- resolving the stored token into a profile is exactly this effect's job
    void loadMe().finally(() => setLoading(false));
  }, [loadMe]);

  const login = useCallback(
    async (email: string) => {
      setError(null);
      const { data } = await api.POST("/api/v1/auth/token", { body: { email } });
      if (!data) {
        setError("Unknown email — try one seeded by `make seed` (e.g. ada@example.com).");
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
    setCustomer(null);
  }, []);

  const value = useMemo(
    () => ({ customer, loading, error, login, logout }),
    [customer, loading, error, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
