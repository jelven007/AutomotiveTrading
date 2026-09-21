import { ArrowDownRight, ArrowUpRight, ExternalLink } from "lucide-react";

import type { MarketQuote, NewsItem } from "./binancePublic";

// 迷你走势图：收盘价序列已在取数层归一化为 150x42 的 polyline 点位
export function MiniChart({
  points,
  trend,
}: {
  points: string;
  trend: string;
}) {
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

// 统一行情卡片：全站行情类展示（首页行情、交易页 BTC 实时价）复用同一视觉，
// 卡片仅呈现现价、24h 涨跌与迷你走势，不再显示“交易中”状态标签。
export function MarketTile({ quote }: { quote: MarketQuote }) {
  return (
    <article className="market-tile">
      <div className="tile-topline">
        <div>
          <strong>{quote.displayName}</strong>
          <small>{quote.symbol}</small>
        </div>
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
  );
}

// 资讯卡片：与行情卡片共用 market-tile 外框，保证首页两个区块视觉一致
export function NewsTile({ item }: { item: NewsItem }) {
  return (
    <article className="market-tile news-tile">
      <div className="tile-topline">
        <span className="tag">公告</span>
        <time className="market-time">{item.time}</time>
      </div>
      <h3 className="news-tile__title">{item.title}</h3>
      <a
        className="news-tile__link"
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`查看公告 ${item.title}`}
        title="查看原文"
      >
        查看原文
        <ExternalLink size={14} />
      </a>
    </article>
  );
}
