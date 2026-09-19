import { TradingWorkspace } from "./TradingWorkspace";

const products = [
  { id: "spot", label: "现货" },
  { id: "cross_margin", label: "全仓杠杆" },
  { id: "isolated_margin", label: "逐仓杠杆" },
  { id: "usdm_futures", label: "U 本位永续" },
];

export function BinanceTradingPage() {
  return (
    <TradingWorkspace
      marketGroup="binance"
      title="币安交易"
      description="生产帐号默认只读，交易权限按产品 Scope 独立启用。"
      providers={["binance"]}
      products={products}
    />
  );
}
