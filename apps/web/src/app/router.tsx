import { BrowserRouter } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { AuthProvider } from "../features/auth/AuthProvider";
import { AuthPage } from "../pages/AuthPage";
import { AppShell } from "./AppShell";

export function AppRouter() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AuthBoundary />
      </AuthProvider>
    </BrowserRouter>
  );
}

function AuthBoundary() {
  const auth = useAuth();

  if (auth.status === "loading") {
    return (
      <main className="auth-loading" role="status">
        正在恢复登录会话
      </main>
    );
  }
  if (auth.status === "anonymous") {
    return <AuthPage />;
  }
  return (
    <AppShell
      onLogout={() => void auth.logout()}
      tenantId={auth.claims?.tenant_id}
    />
  );
}
