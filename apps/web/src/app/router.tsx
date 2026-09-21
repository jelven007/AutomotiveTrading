import { BrowserRouter } from "react-router-dom";

import { AuthPage } from "../pages/AuthPage";
import { AuthProvider } from "../features/auth/AuthProvider";
import { useAuth } from "../features/auth/AuthContext";
import { AppShell } from "./AppShell";

export function AppRouter() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AuthenticatedApp />
      </AuthProvider>
    </BrowserRouter>
  );
}

function AuthenticatedApp() {
  const auth = useAuth();
  if (auth.status === "loading") {
    return <main className="auth-loading">正在加载...</main>;
  }
  return auth.status === "authenticated" ? <AppShell /> : <AuthPage />;
}
