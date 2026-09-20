import { AlertTriangle, Database, RefreshCw, Search } from "lucide-react";
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
import { MarketTable } from "./MarketTable";
import type { Exchange, LatestQuotesResponse, QualityStatus } from "./types";

type ExchangeFilter = "ALL" | Exchange;
type QualityFilter = "all" | QualityStatus;
type SortKey = "symbol" | "change" | "amount";

const qualityOptions: Array<[QualityFilter, string]> = [
  ["all", "全部质量"],
  ["healthy", "正常"],
  ["stale", "陈旧"],
  ["invalid", "无效"],
  ["unavailable", "不可用"],
];

export function MarketOverviewPage() {
  const auth = useAuth();
  const tenantId = auth.claims?.tenant_id ?? "";
  const [data, setData] = useState<LatestQuotesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [exchange, setExchange] = useState<ExchangeFilter>("ALL");
  const [quality, setQuality] = useState<QualityFilter>("all");
  const [sort, setSort] = useState<SortKey>("symbol");
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
    const filtered = (data?.items ?? []).filter((quote) => {
      const searchMatches =
        !deferredQuery ||
        quote.symbol.includes(deferredQuery) ||
        quote.name.toLowerCase().includes(deferredQuery);
      const exchangeMatches = exchange === "ALL" || quote.exchange === exchange;
      const qualityMatches =
        quality === "all" || quote.quality_status === quality;
      return searchMatches && exchangeMatches && qualityMatches;
    });
    return filtered.sort((left, right) => {
      if (sort === "change") {
        return Number(right.change_percent) - Number(left.change_percent);
      }
      if (sort === "amount") {
        return Number(right.amount) - Number(left.amount);
      }
      return left.symbol.localeCompare(right.symbol);
    });
  }, [data, deferredQuery, exchange, quality, sort]);

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
          detail={
            coverage?.verification === "unverified"
              ? "候选集合，待 Tushare 核验"
              : "证券全集已核验"
          }
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
        <Metric
          label="采集耗时"
          value={
            coverage ? `${coverage.duration_ms.toLocaleString()} ms` : "--"
          }
          detail={`缺口 ${formatInteger(coverage?.missing)}`}
        />
        <Metric
          label="当前结果"
          value={formatInteger(visibleQuotes.length)}
          detail={`可用快照 ${formatInteger(data?.available)}`}
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
          <label className="market-select">
            <span>质量</span>
            <select
              aria-label="质量状态"
              onChange={(event) =>
                setQuality(event.target.value as QualityFilter)
              }
              value={quality}
            >
              {qualityOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="market-select">
            <span>排序</span>
            <select
              aria-label="行情排序"
              onChange={(event) => setSort(event.target.value as SortKey)}
              value={sort}
            >
              <option value="symbol">证券代码</option>
              <option value="change">涨幅优先</option>
              <option value="amount">成交额优先</option>
            </select>
          </label>
          <span className="market-toolbar__source">
            <Database aria-hidden="true" size={14} />
            ClickHouse
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
          <MarketTable quotes={visibleQuotes} />
        )}
      </section>
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
