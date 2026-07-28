import { useContext } from "react";
import { BoardAuthContext, type BoardAuthState } from "./boardContext";

export function useBoardAuth(): BoardAuthState {
  const context = useContext(BoardAuthContext);
  if (!context) {
    throw new Error("useBoardAuth must be used within a BoardAuthProvider");
  }
  return context;
}
