import { LogOut, Settings, Workflow } from "lucide-react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { HomePage } from "../pages/HomePage";
import { StrategiesPage } from "../pages/StrategiesPage";
import { TradingPage } from "../pages/TradingPage";
import { UserProfilePage } from "../pages/UserProfilePage";

// 一级菜单：首页、策略、交易
const primaryNav = [
  { to: "/", label: "首页", end: true },
  { to: "/strategies", label: "策略", end: false },
  { to: "/trading", label: "交易", end: false },
];

export function AppShell() {
  const auth = useAuth();
  const userEmail = auth.claims?.email ?? "当前用户";

  return (
    <div className="app-shell">
      <header className="appbar">
        <div className="appbar-lead">
          <NavLink className="brand" to="/">
            <span className="brand-mark" aria-hidden="true">
              <Workflow size={19} strokeWidth={2.2} />
            </span>
            <strong>Quant Desk</strong>
          </NavLink>
          <nav className="primary-nav" aria-label="主导航">
            {primaryNav.map((item) => (
              <NavLink
                key={item.to}
                className={({ isActive }) =>
                  `nav-item${isActive ? " is-active" : ""}`
                }
                end={item.end}
                to={item.to}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="appbar-trail">
          <span className="status-pill" title="系统状态">
            <span className="status-dot" aria-hidden="true" />
            系统正常 · 128ms
          </span>
          <NavLink
            aria-label={`用户详情 ${userEmail}`}
            className="user-context"
            title={userEmail}
            to="/user"
          >
            {userEmail}
          </NavLink>
          <NavLink
            aria-label="设置"
            className="icon-button"
            title="设置"
            to="/user"
          >
            <Settings size={17} />
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
          <Route path="/" element={<HomePage />} />
          <Route path="/strategies" element={<StrategiesPage />} />
          <Route path="/trading" element={<TradingPage />} />
          <Route path="/user" element={<UserProfilePage />} />
          <Route path="*" element={<Navigate replace to="/" />} />
        </Routes>
      </main>
    </div>
  );
}
