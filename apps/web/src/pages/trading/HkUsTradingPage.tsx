import { TradingWorkspace } from "./TradingWorkspace";

export function HkUsTradingPage() {
  return (
    <TradingWorkspace
      marketGroup="hk_us_equity"
      title="港美交易"
      description="管理富途与长桥帐号，统一查看港股和美股交易状态。"
      providers={["futu", "longbridge"]}
    />
  );
}
