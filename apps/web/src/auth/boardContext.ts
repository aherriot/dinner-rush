import { createContext } from "react";

export type StaffRole = "kitchen" | "manager";

export interface StaffActor {
  role: StaffRole;
  id: string;
  name: string;
}

export interface BoardAuthState {
  actor: StaffActor | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

export const BoardAuthContext = createContext<BoardAuthState | null>(null);
