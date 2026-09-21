import { MarketTile, NewsTile } from "../features/market/MarketTile";
import {
  useLiveAnnouncements,
  useLiveMarketQuotes,
} from "../features/market/useLiveData";

// 首页：聚合币安公开行情与官方资讯，两块均为卡片网格，每秒静默刷新。
export function HomePage() {
  const { quotes, state: marketState } = useLiveMarketQuotes();
  const { news, state: newsState } = useLiveAnnouncements();

  return (
    <div className="page">
      <section aria-labelledby="market-overview">
        <div className="section-heading">
          <div>
            <h2 id="market-overview">行情</h2>
            <span>币安现货 · 公开行情</span>
          </div>
        </div>
        {marketState === "error" && quotes.length === 0 ? (
          <div className="binance-section-state binance-section-state--error">
            行情数据加载失败，请稍后重试
          </div>
        ) : quotes.length === 0 ? (
          <div className="binance-section-state">正在加载行情</div>
        ) : (
          <div className="market-grid">
            {quotes.map((quote) => (
              <MarketTile key={quote.symbol} quote={quote} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="news-stream">
        <div className="section-heading">
          <div>
            <h2 id="news-stream">资讯</h2>
            <span>币安官方公告</span>
          </div>
        </div>
        {newsState === "error" && news.length === 0 ? (
          <div className="binance-section-state binance-section-state--error">
            资讯加载失败，请稍后重试
          </div>
        ) : news.length === 0 ? (
          <div className="binance-section-state">正在加载资讯</div>
        ) : (
          <div className="market-grid">
            {news.map((item) => (
              <NewsTile key={item.id} item={item} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
