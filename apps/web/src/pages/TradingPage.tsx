import { Info } from "lucide-react";

import { BinanceAssetsPanel } from "../features/trading/BinanceAssetsPanel";

export function TradingPage() {
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">币安</p>
          <h1>交易</h1>
          <p className="page-description">查看账户总资产与当前订单。</p>
        </div>
      </div>

      <BinanceAssetsPanel />

      <section className="panel list-panel" aria-labelledby="open-orders">
        <div className="panel-heading">
          <div>
            <h2 id="open-orders">当前订单</h2>
            <span>只读预览</span>
          </div>
        </div>
        <div className="binance-section-state">
          <Info size={18} />
          <span>下单与撤单能力将于阶段二开放后接入。</span>
        </div>
      </section>
    </div>
  );
}
