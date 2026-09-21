import { AlertCircle, Check, X } from "lucide-react";
import { type ReactNode, useState } from "react";

import type { BinanceOverview, UsdmBalance, UsdmPosition } from "./types";

type Tab = "spot" | "usdm" | "permissions";

type Props = {
  overview: BinanceOverview;
};

const tabs: Array<{ id: Tab; label: string }> = [
  { id: "spot", label: "现货资产" },
  { id: "usdm", label: "U 本位" },
  { id: "permissions", label: "API 权限" },
];

export function BinanceAccountOverview({ overview }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("spot");

  return (
    <section className="binance-overview" aria-label="币安账户数据">
      <div className="product-tabs" role="tablist" aria-label="币安账户视图">
        {tabs.map((tab) => (
          <button
            aria-controls={`binance-${tab.id}-panel`}
            aria-selected={activeTab === tab.id}
            className={activeTab === tab.id ? "is-active" : undefined}
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            role="tab"
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        className="binance-overview__body"
        id={`binance-${activeTab}-panel`}
        role="tabpanel"
      >
        {activeTab === "spot" && <SpotSection section={overview.spot} />}
        {activeTab === "usdm" && <UsdmSection section={overview.usdm} />}
        {activeTab === "permissions" && (
          <PermissionsSection section={overview.permissions} />
        )}
      </div>
    </section>
  );
}

function SpotSection({ section }: { section: BinanceOverview["spot"] }) {
  if (section.status === "error" || !section.data) {
    return <SectionError message={section.error?.message} />;
  }
  if (section.data.balances.length === 0) {
    return <EmptyResult message="当前没有非零现货资产" />;
  }
  return (
    <DataTable
      columns={["资产", "可用", "冻结", "总额"]}
      rows={section.data.balances}
      renderRow={(balance) => (
        <tr key={balance.asset}>
          <td>
            <strong>{balance.asset}</strong>
          </td>
          <td>{balance.free}</td>
          <td>{balance.locked}</td>
          <td>{balance.total}</td>
        </tr>
      )}
    />
  );
}

function UsdmSection({ section }: { section: BinanceOverview["usdm"] }) {
  if (section.status === "error" || !section.data) {
    return <SectionError message={section.error?.message} />;
  }
  return (
    <div className="binance-usdm">
      <DataTable
        caption="余额"
        columns={["资产", "钱包余额", "可用余额", "未实现盈亏"]}
        rows={section.data.balances}
        renderRow={renderUsdmBalance}
      />
      <DataTable
        caption="持仓"
        columns={[
          "合约",
          "方向",
          "数量",
          "开仓均价",
          "标记价格",
          "未实现盈亏",
          "杠杆",
          "保证金",
        ]}
        rows={section.data.positions}
        renderRow={renderUsdmPosition}
      />
    </div>
  );
}

function PermissionsSection({
  section,
}: {
  section: BinanceOverview["permissions"];
}) {
  if (section.status === "error" || !section.data) {
    return <SectionError message={section.error?.message} />;
  }
  const permissions = [
    ["读取", section.data.canRead],
    ["现货交易", section.data.canSpotTrade],
    ["U 本位交易", section.data.canFuturesTrade],
    ["固定 IP", section.data.ipRestricted],
    ["提现", section.data.canWithdraw],
    ["内部划转", section.data.canInternalTransfer],
    ["通用划转", section.data.canUniversalTransfer],
  ] as const;

  return (
    <dl className="permission-list">
      {permissions.map(([label, enabled]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd className={enabled ? "metric-positive" : "metric-muted"}>
            {enabled ? <Check size={15} /> : <X size={15} />}
            {enabled ? "已开启" : "已关闭"}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function DataTable<T>({
  caption,
  columns,
  rows,
  renderRow,
}: {
  caption?: string;
  columns: string[];
  rows: T[];
  renderRow: (row: T) => ReactNode;
}) {
  return (
    <div className="binance-data-table">
      {caption && <h3>{caption}</h3>}
      {rows.length === 0 ? (
        <EmptyResult message={`当前没有${caption ?? "可展示"}数据`} />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>{rows.map(renderRow)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function renderUsdmBalance(balance: UsdmBalance) {
  return (
    <tr key={balance.asset}>
      <td>
        <strong>{balance.asset}</strong>
      </td>
      <td>{balance.walletBalance}</td>
      <td>{balance.availableBalance}</td>
      <td>{balance.unrealizedPnl}</td>
    </tr>
  );
}

function renderUsdmPosition(position: UsdmPosition) {
  return (
    <tr key={position.symbol}>
      <td>
        <strong>{position.symbol}</strong>
      </td>
      <td>{position.side === "long" ? "多" : "空"}</td>
      <td>{position.quantity}</td>
      <td>{position.entryPrice}</td>
      <td>{position.markPrice ?? "-"}</td>
      <td>{position.unrealizedPnl ?? "-"}</td>
      <td>{position.leverage ? `${position.leverage}x` : "-"}</td>
      <td>{position.marginMode === "isolated" ? "逐仓" : "全仓"}</td>
    </tr>
  );
}

function SectionError({ message }: { message?: string }) {
  return (
    <div className="binance-section-state binance-section-state--error">
      <AlertCircle size={18} />
      <span>{message ?? "数据暂不可用"}</span>
    </div>
  );
}

function EmptyResult({ message }: { message: string }) {
  return <div className="binance-section-state">{message}</div>;
}
