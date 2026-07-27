import { Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { OrderTracker } from "./pages/OrderTracker/OrderTracker";
import { Storefront } from "./pages/Storefront/Storefront";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Storefront />} />
        <Route path="/orders/:code" element={<OrderTracker />} />
      </Routes>
    </AuthProvider>
  );
}
