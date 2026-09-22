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

// 首页行情卡片：仅呈现现价、24h 涨跌与迷你走势。
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

// 资讯列表行：标准资讯流样式（时间 + 标题 + 外链），复用全站 .news-row 列表外观
export function NewsRow({ item }: { item: NewsItem }) {
  return (
    <a
      className="news-row"
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`查看公告 ${item.title}`}
      title="查看原文"
    >
      <time>{item.time}</time>
      <div className="news-row__body">
        <span className="tag">公告</span>
        <h3>{item.title}</h3>
      </div>
      <ExternalLink className="news-row__icon" size={16} aria-hidden="true" />
    </a>
  );
}
