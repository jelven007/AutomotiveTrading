import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  type UTCTimestamp,
} from "lightweight-charts";
import { AlertTriangle, LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { getInstrumentHistory } from "./api";
import type {
  InstrumentHistoryResponse,
  MarketBar,
  MarketMinute,
  MarketQuote,
} from "./types";

type HistoryTab = "minute" | "bar" | "transaction";

type Props = {
  quote: MarketQuote;
  tenantId: string;
};

const tabs: Array<[HistoryTab, string]> = [
  ["minute", "分时"],
  ["bar", "日 K"],
  ["transaction", "分笔"],
];

export function InstrumentHistory({ quote, tenantId }: Props) {
  const [activeTab, setActiveTab] = useState<HistoryTab>("minute");
  const [data, setData] = useState<InstrumentHistoryResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setActiveTab("minute");
    setData(null);
    setError("");
    setLoading(true);
    void getInstrumentHistory(
      tenantId,
      quote.exchange,
      quote.symbol,
      controller.signal,
    )
      .then(setData)
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "历史行情加载失败",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [quote.exchange, quote.symbol, tenantId]);

  const activeResponse =
    activeTab === "minute"
      ? data?.minutes
      : activeTab === "bar"
        ? data?.bars
        : data?.transactions;
  const statusLabel =
    activeResponse?.coverage === "partial"
      ? "覆盖可能不完整"
      : activeResponse?.coverage === "collected"
        ? "采集完成"
        : "等待后台回填";

  return (
    <section className="instrument-history" aria-label="个股历史行情">
      <header className="instrument-history__header">
        <div>
          <h2>
            {quote.name || quote.symbol} {quote.symbol}
          </h2>
          <span>
            {quote.exchange === "SSE" ? "上交所" : "深交所"}
            {activeResponse?.trade_date
              ? ` · ${activeResponse.trade_date}`
              : ""}
          </span>
        </div>
        <div aria-label="历史行情视图" className="history-tabs" role="tablist">
          {tabs.map(([value, label]) => (
            <button
              aria-selected={activeTab === value}
              key={value}
              onClick={() => setActiveTab(value)}
              role="tab"
              type="button"
            >
              {label}
            </button>
          ))}
        </div>
        <span
          className={`history-coverage history-coverage--${
            activeResponse?.coverage ?? "pending"
          }`}
        >
          {statusLabel}
        </span>
      </header>

      <div className="instrument-history__body">
        {loading ? (
          <div className="history-state" role="status">
            <LoaderCircle
              aria-hidden="true"
              className="is-spinning"
              size={17}
            />
            正在读取历史行情
          </div>
        ) : error ? (
          <div className="history-state history-state--error" role="alert">
            <AlertTriangle aria-hidden="true" size={17} />
            {error}
          </div>
        ) : !activeResponse?.items.length ? (
          <div className="history-state" role="status">
            该证券历史数据仍在后台回填
          </div>
        ) : activeTab === "minute" && data ? (
          <HistoryChart kind="minute" rows={data.minutes.items} />
        ) : activeTab === "bar" && data ? (
          <HistoryChart kind="bar" rows={data.bars.items} />
        ) : data ? (
          <TransactionTape rows={data.transactions.items} />
        ) : null}
      </div>

      <footer className="instrument-history__footer">
        <span>
          {activeResponse?.items.length ?? 0}{" "}
          {activeTab === "transaction" ? "笔" : "根"}
        </span>
        <span>数据源 MOOTDX</span>
      </footer>
    </section>
  );
}

function HistoryChart({
  kind,
  rows,
}: {
  kind: "minute" | "bar";
  rows: MarketMinute[] | MarketBar[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRows = useMemo(() => rows, [rows]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const chart = createChart(container, {
      width: Math.max(container.clientWidth, 320),
      height: 320,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#66717d",
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#edf0f2" },
        horzLines: { color: "#edf0f2" },
      },
      rightPriceScale: { borderColor: "#d9dee3" },
      timeScale: { borderColor: "#d9dee3", timeVisible: kind === "minute" },
    });
    if (kind === "bar") {
      const series = chart.addSeries(CandlestickSeries, {
        upColor: "#c83f49",
        downColor: "#138a62",
        borderVisible: false,
        wickUpColor: "#c83f49",
        wickDownColor: "#138a62",
      });
      series.setData(
        (chartRows as MarketBar[]).map((row) => ({
          time: toTimestamp(row.event_time),
          open: Number(row.open),
          high: Number(row.high),
          low: Number(row.low),
          close: Number(row.close),
        })),
      );
    } else {
      const prices = chart.addSeries(LineSeries, {
        color: "#1468d4",
        lineWidth: 2,
        priceLineVisible: false,
      });
      prices.setData(
        (chartRows as MarketMinute[]).map((row) => ({
          time: toTimestamp(row.event_time),
          value: Number(row.price),
        })),
      );
      const volumes = chart.addSeries(HistogramSeries, {
        color: "#a9b8c8",
        priceFormat: { type: "volume" },
        priceScaleId: "",
      });
      volumes.priceScale().applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
      });
      volumes.setData(
        (chartRows as MarketMinute[]).map((row) => ({
          time: toTimestamp(row.event_time),
          value: Number(row.volume),
        })),
      );
    }
    chart.timeScale().fitContent();
    if (typeof ResizeObserver === "undefined") {
      return () => chart.remove();
    }
    const resize = new ResizeObserver(([entry]) => {
      chart.applyOptions({ width: Math.max(entry.contentRect.width, 320) });
    });
    resize.observe(container);
    return () => {
      resize.disconnect();
      chart.remove();
    };
  }, [chartRows, kind]);

  return <div className="history-chart" ref={containerRef} />;
}

function TransactionTape({
  rows,
}: {
  rows: InstrumentHistoryResponse["transactions"]["items"];
}) {
  return (
    <div className="transaction-tape" role="table" aria-rowcount={rows.length}>
      <div className="transaction-tape__header" role="row">
        <span role="columnheader">时间</span>
        <span role="columnheader">价格</span>
        <span role="columnheader">数量</span>
        <span role="columnheader">方向</span>
      </div>
      <div className="transaction-tape__body">
        {rows.map((row) => (
          <div
            className="transaction-tape__row"
            key={`${row.event_time}:${row.source_offset}`}
            role="row"
          >
            <time role="cell">{formatTime(row.event_time)}</time>
            <span role="cell">{formatNumber(row.price)}</span>
            <span role="cell">{formatNumber(row.quantity)}</span>
            <span
              className={`transaction-side transaction-side--${row.side}`}
              role="cell"
            >
              {row.side === "buy"
                ? "买入"
                : row.side === "sell"
                  ? "卖出"
                  : "中性"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function toTimestamp(value: string) {
  return Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatNumber(value: string) {
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 2,
  }).format(Number(value));
}
