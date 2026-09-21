import { MarketTile } from "./MarketTile";
import { useLiveMarketQuotes } from "./useLiveData";

// 交易页右侧实时价：信息源同首页行情，每秒静默刷新，复用统一行情卡片
const BTC_SYMBOLS = ["BTCUSDT"];

export function BtcSpotPriceCard() {
  const { quotes, state } = useLiveMarketQuotes(BTC_SYMBOLS);
  const quote = quotes[0];

  return (
    <section className="btc-price" aria-label="BTC/USDT 实时价格">
      <div className="section-heading">
        <div>
          <h2>实时价格</h2>
          <span>币安现货 · BTC/USDT</span>
        </div>
      </div>
      {state === "error" && !quote ? (
        <div className="binance-section-state binance-section-state--error">
          行情数据加载失败，请稍后重试
        </div>
      ) : !quote ? (
        <div className="binance-section-state">正在加载行情</div>
      ) : (
        <MarketTile quote={quote} />
      )}
    </section>
  );
}
