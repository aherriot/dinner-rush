import { Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { Board } from "./pages/Board/Board";
import { OrderTracker } from "./pages/OrderTracker/OrderTracker";
import { Storefront } from "./pages/Storefront/Storefront";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Storefront />} />
        <Route path="/orders/:code" element={<OrderTracker />} />
        <Route path="/board" element={<Board />} />
      </Routes>
    </AuthProvider>
  );
}
