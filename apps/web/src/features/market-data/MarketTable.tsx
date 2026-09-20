import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";

import type { MarketQuote, QualityStatus } from "./types";

const qualityLabels: Record<QualityStatus, string> = {
  healthy: "正常",
  stale: "陈旧",
  partial: "部分",
  conflict: "冲突",
  invalid: "无效",
  unavailable: "不可用",
};

const numberFormatter = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 2,
});
const compactFormatter = new Intl.NumberFormat("zh-CN", {
  notation: "compact",
  maximumFractionDigits: 2,
});

type Props = {
  quotes: MarketQuote[];
  selected?: MarketQuote | null;
  onSelect?: (quote: MarketQuote) => void;
};

export function MarketTable({ quotes, selected, onSelect }: Props) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: quotes.length,
    getScrollElement: () => viewportRef.current,
    estimateSize: () => 44,
    overscan: 16,
    initialRect: { width: 1200, height: 560 },
  });

  if (quotes.length === 0) {
    return (
      <div className="market-empty" role="status">
        没有符合当前筛选条件的证券
      </div>
    );
  }

  return (
    <div className="market-table" role="table" aria-rowcount={quotes.length}>
      <div className="market-table__header market-table__grid" role="row">
        <span role="columnheader">证券</span>
        <span role="columnheader">最新价</span>
        <span role="columnheader">涨跌幅</span>
        <span role="columnheader">成交额</span>
        <span role="columnheader">源时间</span>
        <span role="columnheader">质量</span>
      </div>
      <div className="market-table__viewport" ref={viewportRef}>
        <div
          className="market-table__body"
          style={{ height: virtualizer.getTotalSize() }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const quote = quotes[virtualRow.index];
            const change = Number(quote.change_percent);
            const direction = change > 0 ? "up" : change < 0 ? "down" : "flat";
            const isSelected =
              quote.exchange === selected?.exchange &&
              quote.symbol === selected.symbol;
            return (
              <div
                aria-rowindex={virtualRow.index + 2}
                className={`market-table__row market-table__grid${
                  isSelected ? " is-selected" : ""
                }`}
                data-index={virtualRow.index}
                key={`${quote.exchange}:${quote.symbol}`}
                ref={virtualizer.measureElement}
                role="row"
                style={{ transform: `translateY(${virtualRow.start}px)` }}
              >
                <span className="market-security" role="cell">
                  <button
                    aria-label={`${quote.name || quote.symbol} ${quote.symbol} 查看历史行情`}
                    aria-pressed={isSelected}
                    onClick={() => onSelect?.(quote)}
                    type="button"
                  >
                    <strong>{quote.name || quote.symbol}</strong>
                    <small>
                      {quote.symbol} · {exchangeLabel(quote.exchange)}
                    </small>
                  </button>
                </span>
                <span className="market-number" role="cell">
                  {formatDecimal(quote.last_price)}
                </span>
                <span
                  className={`market-number market-change market-change--${direction}`}
                  role="cell"
                >
                  {change > 0 ? "+" : ""}
                  {numberFormatter.format(change)}%
                </span>
                <span className="market-number" role="cell">
                  {formatCompact(quote.amount)}
                </span>
                <span className="market-time-cell" role="cell">
                  {formatMarketTime(quote.source_time)}
                </span>
                <span role="cell">
                  <span
                    className={`quality-label quality-label--${quote.quality_status}`}
                    title={quote.quality_reasons.join("、") || undefined}
                  >
                    {qualityLabels[quote.quality_status]}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function exchangeLabel(exchange: MarketQuote["exchange"]) {
  return exchange === "SSE" ? "上交所" : "深交所";
}

function formatDecimal(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? numberFormatter.format(parsed) : "--";
}

function formatCompact(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? compactFormatter.format(parsed) : "--";
}

function formatMarketTime(value: string | null) {
  if (!value || value.startsWith("1970-")) {
    return "时间未知";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
