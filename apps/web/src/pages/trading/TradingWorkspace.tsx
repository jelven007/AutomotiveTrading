import {
  AlertOctagon,
  Plus,
  RefreshCw,
  ShieldAlert,
  WalletCards,
} from "lucide-react";
import { useState } from "react";
import { NavLink } from "react-router-dom";

import { AccountBindingDialog } from "../../features/trading/AccountBindingDialog";
import type {
  MarketGroup,
  TradingAccount,
  TradingAccountDraft,
  TradingProvider,
} from "../../features/trading/types";

type ProductTab = {
  id: string;
  label: string;
};

type Props = {
  marketGroup: MarketGroup;
  title: string;
  description: string;
  providers: TradingProvider[];
  products?: ProductTab[];
};

const providerLabels: Record<TradingProvider, string> = {
  tonghuashun: "同花顺",
  caixin: "财信证券",
  futu: "富途",
  longbridge: "长桥",
  binance: "币安",
};

const marketLinks = [
  { label: "沪深", to: "/trading/cn" },
  { label: "港美", to: "/trading/hk-us" },
  { label: "币安", to: "/trading/binance" },
];

export function TradingWorkspace({
  marketGroup,
  title,
  description,
  providers,
  products,
}: Props) {
  const providerNames = providers.map((provider) => providerLabels[provider]);
  const isBinance = marketGroup === "binance";
  const [showBinding, setShowBinding] = useState(false);
  const [accounts, setAccounts] = useState<TradingAccount[]>([]);
  const [activeProduct, setActiveProduct] = useState(products?.[0]?.id);

  function saveAccount(draft: TradingAccountDraft) {
    const fingerprint = draft.apiKey
      ? `key-${draft.apiKey.slice(-4)}`
      : undefined;
    setAccounts((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        alias: draft.alias,
        provider: draft.provider,
        environment: "production",
        fingerprint,
        scopes: draft.enabledScopes,
        connectionStatus: "disconnected",
        tradingEnabled: false,
      },
    ]);
    setShowBinding(false);
  }

  return (
    <div className="page trading-workspace">
      <nav className="trading-market-tabs" aria-label="交易市场">
        {marketLinks.map(({ label, to }) => (
          <NavLink
            className={({ isActive }) =>
              `trading-market-tab${isActive ? " is-active" : ""}`
            }
            key={to}
            to={to}
          >
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="page-heading">
        <div>
          <p className="eyebrow">帐号与订单</p>
          <h1>{title}</h1>
          <p className="page-description">{description}</p>
        </div>
        <div className="page-actions">
          <button
            className="button button--primary"
            onClick={() => setShowBinding(true)}
          >
            <Plus size={16} />
            添加帐号
          </button>
          <button className="icon-button" aria-label="对账" title="对账">
            <RefreshCw size={17} />
          </button>
          <button
            className="icon-button icon-button--danger"
            aria-label="急停"
            title="急停"
          >
            <AlertOctagon size={17} />
          </button>
        </div>
      </div>

      {isBinance && (
        <div className="production-guard" role="status">
          <ShieldAlert size={18} />
          <span>
            <strong>生产交易未启用</strong>
            <small>帐号通过权限检查、近期 MFA 和风控审批后方可启用。</small>
          </span>
          <span className="state state--warning">只读模式</span>
        </div>
      )}

      <div className="trading-summary">
        <div>
          <span>已绑定帐号</span>
          <strong>{accounts.length}</strong>
        </div>
        <div>
          <span>已连接</span>
          <strong>0</strong>
        </div>
        <div>
          <span>交易权限</span>
          <strong>关闭</strong>
        </div>
        <div>
          <span>最近同步</span>
          <strong>--</strong>
        </div>
      </div>

      {products && (
        <div className="product-tabs" role="tablist" aria-label="币安产品">
          {products.map((product) => (
            <button
              aria-controls="product-workspace"
              aria-selected={activeProduct === product.id}
              className={activeProduct === product.id ? "is-active" : ""}
              key={product.id}
              onClick={() => setActiveProduct(product.id)}
              role="tab"
              type="button"
            >
              {product.label}
            </button>
          ))}
        </div>
      )}

      <section className="panel account-list" aria-labelledby="account-list">
        <div className="panel-heading">
          <div>
            <h2 id="account-list">交易帐号</h2>
            <span>可用通道：{providerNames.join("、")}</span>
          </div>
        </div>
        {accounts.length === 0 ? (
          <div className="trading-empty">
            <span className="trading-empty__icon" aria-hidden="true">
              <WalletCards size={22} />
            </span>
            <h2>尚未添加帐号</h2>
            <p>添加帐号后，这里将显示连接、权限和数据同步状态。</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>帐号</th>
                  <th>通道</th>
                  <th>环境</th>
                  <th>凭据</th>
                  <th>Scope</th>
                  <th>连接</th>
                  <th>交易权限</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account) => (
                  <tr key={account.id}>
                    <td>{account.alias}</td>
                    <td>{providerLabels[account.provider]}</td>
                    <td>生产</td>
                    <td>{account.fingerprint ?? "待授权"}</td>
                    <td>
                      {account.scopes.length > 0
                        ? account.scopes.join(" / ")
                        : "未配置"}
                    </td>
                    <td>待检查</td>
                    <td className="metric-negative">关闭</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {products && (
        <section
          className="panel product-workspace"
          id="product-workspace"
          role="tabpanel"
        >
          <div className="panel-heading">
            <div>
              <h2>
                {
                  products.find((product) => product.id === activeProduct)
                    ?.label
                }
                帐号状态
              </h2>
              <span>选择已通过权限检查的帐号后加载生产数据</span>
            </div>
          </div>
          <div className="trading-empty trading-empty--compact">
            <ShieldAlert size={20} />
            <p>当前没有可用帐号，生产写操作保持关闭。</p>
          </div>
        </section>
      )}

      {showBinding && (
        <AccountBindingDialog
          marketGroup={marketGroup}
          providers={providers}
          onCancel={() => setShowBinding(false)}
          onSave={saveAccount}
        />
      )}
    </div>
  );
}
