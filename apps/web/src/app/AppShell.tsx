import { LogOut, Workflow } from "lucide-react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { UserProfilePage } from "../pages/UserProfilePage";
import { BinanceTradingPage } from "../pages/trading/BinanceTradingPage";

export function AppShell() {
  const auth = useAuth();
  const userEmail = auth.claims?.email ?? "当前用户";

  return (
    <div className="app-shell">
      <header className="appbar">
        <div className="appbar-lead">
          <NavLink className="brand" to="/trading/binance">
            <span className="brand-mark" aria-hidden="true">
              <Workflow size={19} strokeWidth={2.2} />
            </span>
            <strong>Quant Desk</strong>
          </NavLink>
          <nav className="primary-nav" aria-label="主导航">
            <NavLink
              className={({ isActive }) =>
                `nav-item${isActive ? " is-active" : ""}`
              }
              to="/trading/binance"
            >
              币安
            </NavLink>
          </nav>
        </div>

        <div className="appbar-trail">
          <NavLink
            aria-label={`用户详情 ${userEmail}`}
            className="user-context"
            title={userEmail}
            to="/user"
          >
            {userEmail}
          </NavLink>
          <button
            aria-label="退出登录"
            className="icon-button"
            onClick={() => void auth.logout()}
            title="退出登录"
            type="button"
          >
            <LogOut size={17} />
          </button>
        </div>
      </header>

      <main className="main-content">
        <Routes>
          <Route path="/trading/binance" element={<BinanceTradingPage />} />
          <Route path="/user" element={<UserProfilePage />} />
          <Route
            path="*"
            element={<Navigate replace to="/trading/binance" />}
          />
        </Routes>
      </main>
    </div>
  );
}
