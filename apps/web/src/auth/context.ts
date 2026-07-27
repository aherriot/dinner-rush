import { createContext } from "react";
import type { components } from "../api/schema";

type Customer = components["schemas"]["Customer"];

export interface AuthState {
  customer: Customer | null;
  loading: boolean;
  error: string | null;
  login: (email: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthState | null>(null);
