import {
  Bell,
  CandlestickChart,
  Database,
  Home,
  Newspaper,
  Search,
  Settings,
  Waypoints,
  Workflow,
} from "lucide-react";
import { NavLink, Route, Routes } from "react-router-dom";

import { DataPage } from "../pages/DataPage";
import { HomePage } from "../pages/HomePage";
import { NewsPage } from "../pages/NewsPage";
import { StrategiesPage } from "../pages/StrategiesPage";
import { TradingPage } from "../pages/TradingPage";

const navigation = [
  { label: "首页", to: "/", icon: Home, end: true },
  { label: "资讯", to: "/news", icon: Newspaper },
  { label: "策略", to: "/strategies", icon: Waypoints },
  { label: "交易", to: "/trading", icon: CandlestickChart },
  { label: "数据", to: "/data", icon: Database },
];

export function AppShell() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
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
              <Icon size={19} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="system-state">
          <span className="status-dot status-dot--ok" />
          <span>
            <strong>系统运行正常</strong>
            <small>数据延迟 128ms</small>
          </span>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="mobile-brand">
            <span className="brand-mark" aria-hidden="true">
              <Workflow size={18} />
            </span>
            <strong>Quant Desk</strong>
          </div>

          <div className="context-controls">
            <label className="select-control">
              <span>租户</span>
              <select aria-label="当前租户" defaultValue="星河资本">
                <option>星河资本</option>
                <option>个人研究空间</option>
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
            <button className="icon-button" aria-label="设置" title="设置">
              <Settings size={18} />
            </button>
            <button
              className="user-button"
              aria-label="账户菜单"
              title="账户菜单"
            >
              ZL
            </button>
          </div>
        </header>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/news" element={<NewsPage />} />
            <Route path="/strategies" element={<StrategiesPage />} />
            <Route path="/trading" element={<TradingPage />} />
            <Route path="/data" element={<DataPage />} />
            <Route path="*" element={<HomePage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
