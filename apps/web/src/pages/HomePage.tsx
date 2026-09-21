import {
  ArrowDownRight,
  ArrowUpRight,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  fetchAnnouncements,
  fetchMarketQuotes,
  type MarketQuote,
  type NewsItem,
} from "../features/market/binancePublic";

// 首页数据加载态：行情与资讯共用
type LoadState = "loading" | "ready" | "error";

function MiniChart({ points, trend }: { points: string; trend: string }) {
  return (
    <svg
      className={`mini-chart mini-chart--${trend}`}
      viewBox="0 0 150 42"
      aria-hidden="true"
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
    </svg>
  );
}

export function HomePage() {
  const [quotes, setQuotes] = useState<MarketQuote[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [marketState, setMarketState] = useState<LoadState>("loading");
  const [newsState, setNewsState] = useState<LoadState>("loading");

  // 行情与资讯各自独立加载，互不阻塞。
  // silent=true 用于自动刷新：不重置为 loading，失败时保留已有数据避免界面闪烁。
  const loadMarket = useCallback(async (silent = false) => {
    if (!silent) {
      setMarketState("loading");
    }
    try {
      setQuotes(await fetchMarketQuotes());
      setMarketState("ready");
    } catch {
      setMarketState((prev) => (silent && prev === "ready" ? prev : "error"));
    }
  }, []);

  const loadNews = useCallback(async (silent = false) => {
    if (!silent) {
      setNewsState("loading");
    }
    try {
      setNews(await fetchAnnouncements());
      setNewsState("ready");
    } catch {
      setNewsState((prev) => (silent && prev === "ready" ? prev : "error"));
    }
  }, []);

  useEffect(() => {
    // 首次进入展示加载态，之后每 1 秒静默刷新一次行情与资讯
    void loadMarket();
    void loadNews();
    const timer = setInterval(() => {
      void loadMarket(true);
      void loadNews(true);
    }, 1000);
    return () => clearInterval(timer);
  }, [loadMarket, loadNews]);

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">概览</p>
          <h1>首页</h1>
          <p className="page-description">聚合币安公开行情与官方资讯。</p>
        </div>
      </div>

      <section aria-labelledby="market-overview">
        <div className="section-heading">
          <div>
            <h2 id="market-overview">行情</h2>
            <span>币安现货 · 公开行情</span>
          </div>
          <button
            className="text-button"
            disabled={marketState === "loading"}
            onClick={() => void loadMarket()}
            type="button"
          >
            <RefreshCw
              className={marketState === "loading" ? "is-spinning" : undefined}
              size={14}
            />
            刷新
          </button>
        </div>
        {marketState === "error" ? (
          <div className="binance-section-state binance-section-state--error">
            行情数据加载失败，请稍后重试
          </div>
        ) : marketState === "loading" ? (
          <div className="binance-section-state">正在加载行情</div>
        ) : (
          <div className="market-grid">
            {quotes.map((quote) => (
              <article className="market-tile" key={quote.symbol}>
                <div className="tile-topline">
                  <div>
                    <strong>{quote.displayName}</strong>
                    <small>{quote.symbol}</small>
                  </div>
                  <span className="market-status market-status--open">
                    交易中
                  </span>
                </div>
                <div className="market-value-row">
                  <div>
                    <span className="market-value">{quote.price}</span>
                    <span className={`change change--${quote.trend}`}>
                      {quote.trend === "up" ? (
                        <ArrowUpRight size={14} />
                      ) : (
                        <ArrowDownRight size={14} />
                      )}
                      {quote.changePercent}
                    </span>
                  </div>
                  <MiniChart points={quote.points} trend={quote.trend} />
                </div>
                <small className="market-time">24h 涨跌</small>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="panel list-panel" aria-labelledby="news-stream">
        <div className="panel-heading">
          <div>
            <h2 id="news-stream">资讯</h2>
            <span>币安官方公告</span>
          </div>
          <button
            className="text-button"
            disabled={newsState === "loading"}
            onClick={() => void loadNews()}
            type="button"
          >
            <RefreshCw
              className={newsState === "loading" ? "is-spinning" : undefined}
              size={14}
            />
            刷新
          </button>
        </div>
        {newsState === "error" ? (
          <div className="binance-section-state binance-section-state--error">
            资讯加载失败，请稍后重试
          </div>
        ) : newsState === "loading" ? (
          <div className="binance-section-state">正在加载资讯</div>
        ) : (
          <div className="news-list">
            {news.map((item) => (
              <article className="news-row" key={item.id}>
                <time>{item.time}</time>
                <div>
                  <div className="tag-row">
                    <span className="tag">公告</span>
                  </div>
                  <h3>{item.title}</h3>
                  <p>Binance Announcement</p>
                </div>
                <a
                  className="icon-button"
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`查看公告 ${item.title}`}
                  title="查看原文"
                >
                  <ExternalLink size={16} />
                </a>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
