import { AlertTriangle, RefreshCw, Search } from "lucide-react";
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useAuth } from "../auth/AuthContext";
import { getLatestQuotes } from "./api";
import { InstrumentHistory } from "./InstrumentHistory";
import { MarketTable } from "./MarketTable";
import type { Exchange, LatestQuotesResponse, MarketQuote } from "./types";

type ExchangeFilter = "ALL" | Exchange;

export function MarketOverviewPage() {
  const auth = useAuth();
  const tenantId = auth.claims?.tenant_id ?? "";
  const [data, setData] = useState<LatestQuotesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [exchange, setExchange] = useState<ExchangeFilter>("ALL");
  const [selectedQuote, setSelectedQuote] = useState<MarketQuote | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());

  const load = useCallback(async () => {
    if (!tenantId) {
      setError("当前租户不可用");
      setLoading(false);
      return;
    }
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    try {
      setData(await getLatestQuotes(tenantId, controller.signal));
      setError("");
    } catch (requestError) {
      if (!controller.signal.aborted) {
        setError(
          requestError instanceof Error ? requestError.message : "行情加载失败",
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [tenantId]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 5_000);
    return () => {
      window.clearInterval(timer);
      requestRef.current?.abort();
    };
  }, [load]);

  const visibleQuotes = useMemo(() => {
    return (data?.items ?? []).filter((quote) => {
      const searchMatches =
        !deferredQuery ||
        quote.symbol.includes(deferredQuery) ||
        quote.name.toLowerCase().includes(deferredQuery);
      const exchangeMatches = exchange === "ALL" || quote.exchange === exchange;
      return searchMatches && exchangeMatches;
    });
  }, [data, deferredQuery, exchange]);

  const coverage = data?.coverage;
  const statusText =
    coverage?.status === "collected" ? "沪深覆盖完整" : "覆盖待核验";

  return (
    <div className="page market-page">
      <div className="market-page__title">
        <div>
          <h1>沪深行情</h1>
          <p>上交所与深交所 · mootdx 最新快照</p>
        </div>
        <div className="market-page__status">
          <span
            className={`coverage-state coverage-state--${coverage?.status ?? "unknown"}`}
          >
            <span
              className={`status-dot status-dot--${
                coverage?.status === "collected" ? "ok" : "warning"
              }`}
            />
            {statusText}
          </span>
          <time>{formatAsOf(data?.as_of)}</time>
          <button
            className="button button--secondary"
            disabled={loading}
            onClick={() => void load()}
            type="button"
          >
            <RefreshCw
              aria-hidden="true"
              className={loading ? "is-spinning" : ""}
              size={15}
            />
            刷新
          </button>
        </div>
      </div>

      <section className="market-metrics" aria-label="行情概览">
        <Metric
          label="沪深覆盖"
          value={
            coverage
              ? `${formatInteger(coverage.received)} / ${formatInteger(coverage.expected)}`
              : "--"
          }
          detail="MOOTDX 沪深候选集合"
        />
        <Metric
          label="上交所"
          value={formatInteger(coverage?.markets.SSE?.received)}
          detail={`应采 ${formatInteger(coverage?.markets.SSE?.expected)}`}
        />
        <Metric
          label="深交所"
          value={formatInteger(coverage?.markets.SZSE?.received)}
          detail={`应采 ${formatInteger(coverage?.markets.SZSE?.expected)}`}
        />
      </section>

      <section className="market-workspace" aria-label="沪深行情列表">
        <div className="market-toolbar">
          <label className="market-search">
            <Search aria-hidden="true" size={16} />
            <input
              aria-label="搜索证券"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索代码或名称"
              value={query}
            />
          </label>
          <div className="segmented-control" role="group" aria-label="交易所">
            {(
              [
                ["ALL", "沪深"],
                ["SSE", "上交所"],
                ["SZSE", "深交所"],
              ] as const
            ).map(([value, label]) => (
              <button
                aria-pressed={exchange === value}
                key={value}
                onClick={() => setExchange(value)}
                type="button"
              >
                {label}
              </button>
            ))}
          </div>
          <span className="market-toolbar__count">
            {formatInteger(visibleQuotes.length)} 只
          </span>
        </div>

        {error && (
          <div className="market-alert" role="alert">
            <AlertTriangle aria-hidden="true" size={16} />
            <span>{error}</span>
            <button onClick={() => void load()} type="button">
              重试
            </button>
          </div>
        )}
        {loading && !data ? (
          <div className="market-loading" role="status">
            正在读取真实行情
          </div>
        ) : (
          <MarketTable
            onSelect={setSelectedQuote}
            quotes={visibleQuotes}
            selected={selectedQuote}
          />
        )}
      </section>

      {selectedQuote && (
        <InstrumentHistory quote={selectedQuote} tenantId={tenantId} />
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="market-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function formatInteger(value: number | undefined) {
  return value === undefined ? "--" : value.toLocaleString("zh-CN");
}

function formatAsOf(value: string | null | undefined) {
  if (!value) {
    return "等待数据";
  }
  return `数据时间 ${new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value))}`;
}
