import {
  Bell,
  CandlestickChart,
  Database,
  Home,
  LogOut,
  Newspaper,
  Search,
  Settings,
  UserRound,
  Waypoints,
  Workflow,
} from "lucide-react";
import { useState } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";

import { DataPage } from "../pages/DataPage";
import { HomePage } from "../pages/HomePage";
import { NewsPage } from "../pages/NewsPage";
import { ModelServicesPage } from "../pages/settings/ModelServicesPage";
import { StrategiesPage } from "../pages/StrategiesPage";
import { BinanceTradingPage } from "../pages/trading/BinanceTradingPage";
import { CnTradingPage } from "../pages/trading/CnTradingPage";
import { HkUsTradingPage } from "../pages/trading/HkUsTradingPage";

const navigation = [
  { label: "首页", to: "/", icon: Home, end: true },
  { label: "资讯", to: "/news", icon: Newspaper },
  { label: "策略", to: "/strategies", icon: Waypoints },
  { label: "交易", to: "/trading", icon: CandlestickChart },
  { label: "数据", to: "/data", icon: Database },
];

type Props = {
  tenantId?: string;
  onLogout?: () => void;
};

export function AppShell({ tenantId, onLogout }: Props = {}) {
  const [showAccountMenu, setShowAccountMenu] = useState(false);
  const tenantLabel = tenantId ? tenantId.slice(0, 12) : "星河资本";

  return (
    <div className="app-shell">
      <header className="appbar">
        <div className="appbar-lead">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              <Workflow size={20} strokeWidth={2.2} />
            </span>
            <span>
              <strong>Quant Desk</strong>
              <small>交易决策中枢</small>
            </span>
          </div>

          <nav className="primary-nav" aria-label="主导航">
            {navigation.map(({ label, to, icon: Icon, end }) => (
              <NavLink
                className={({ isActive }) =>
                  `nav-item${isActive ? " is-active" : ""}`
                }
                end={end}
                key={to}
                to={to}
              >
                <Icon size={18} strokeWidth={1.8} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="appbar-trail">
          <span className="status-pill" title="系统运行正常，数据延迟 128ms">
            <span className="status-dot status-dot--ok" />
            系统正常 · 128ms
          </span>

          <div className="context-controls">
            <label className="select-control">
              <span>租户</span>
              <select aria-label="当前租户" defaultValue={tenantLabel}>
                <option>{tenantLabel}</option>
              </select>
            </label>
            <label className="select-control">
              <span>市场</span>
              <select aria-label="当前市场" defaultValue="全部市场">
                <option>全部市场</option>
                <option>A 股</option>
                <option>港股</option>
                <option>美股</option>
              </select>
            </label>
          </div>

          <div className="topbar-actions">
            <button
              className="icon-button search-button"
              aria-label="搜索"
              title="搜索"
            >
              <Search size={18} />
            </button>
            <button
              className="icon-button has-indicator"
              aria-label="通知"
              title="通知"
            >
              <Bell size={18} />
            </button>
            <NavLink
              className="icon-button"
              aria-label="租户设置"
              title="租户设置"
              to="/settings/model-services"
            >
              <Settings size={18} />
            </NavLink>
            <div className="account-menu">
              <button
                aria-expanded={showAccountMenu}
                aria-haspopup="menu"
                aria-label="账户菜单"
                className="user-button"
                onClick={() => setShowAccountMenu((current) => !current)}
                title="账户菜单"
                type="button"
              >
                <UserRound size={16} />
              </button>
              {showAccountMenu && onLogout && (
                <div className="account-menu__popover" role="menu">
                  <button onClick={onLogout} role="menuitem" type="button">
                    <LogOut size={15} />
                    退出登录
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/news" element={<NewsPage />} />
          <Route path="/strategies" element={<StrategiesPage />} />
          <Route
            path="/trading"
            element={<Navigate replace to="/trading/cn" />}
          />
          <Route path="/trading/cn" element={<CnTradingPage />} />
          <Route path="/trading/hk-us" element={<HkUsTradingPage />} />
          <Route path="/trading/binance" element={<BinanceTradingPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route
            path="/settings/model-services"
            element={<ModelServicesPage />}
          />
          <Route path="*" element={<HomePage />} />
        </Routes>
      </main>
    </div>
  );
}
