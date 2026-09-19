import { TradingWorkspace } from "./TradingWorkspace";

export function CnTradingPage() {
  return (
    <TradingWorkspace
      marketGroup="cn_equity"
      title="沪深交易"
      description="管理同花顺与财信证券帐号，生产权限按通道独立审批。"
      providers={["tonghuashun", "caixin"]}
    />
  );
}
