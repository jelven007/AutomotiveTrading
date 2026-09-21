import { useCallback, useEffect, useState } from "react";

import {
  fetchAnnouncements,
  fetchMarketQuotes,
  MARKET_SYMBOLS,
  type MarketQuote,
  type NewsItem,
} from "./binancePublic";

// 数据加载态：行情、资讯、实时价共用
export type LoadState = "loading" | "ready" | "error";

// 全站统一的自动刷新节奏：每秒一次静默刷新
const REFRESH_INTERVAL_MS = 1000;

// 通用实时轮询：首次进入展示 loading，其后每秒静默刷新。
// 静默刷新失败时保留已有数据，避免界面闪烁。
function useLivePolling<T>(
  loader: () => Promise<T>,
  initial: T,
): { data: T; state: LoadState } {
  const [data, setData] = useState<T>(initial);
  const [state, setState] = useState<LoadState>("loading");

  const load = useCallback(
    async (silent: boolean) => {
      if (!silent) {
        setState("loading");
      }
      try {
        setData(await loader());
        setState("ready");
      } catch {
        setState((prev) => (silent && prev === "ready" ? prev : "error"));
      }
    },
    [loader],
  );

  useEffect(() => {
    void load(false);
    const timer = setInterval(() => void load(true), REFRESH_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [load]);

  return { data, state };
}

// 实时行情：默认取首页展示的交易对，也可传入自定义集合（如交易页仅 BTC/USDT）
export function useLiveMarketQuotes(symbols: string[] = MARKET_SYMBOLS): {
  quotes: MarketQuote[];
  state: LoadState;
} {
  const loader = useCallback(() => fetchMarketQuotes(symbols), [symbols]);
  const { data, state } = useLivePolling<MarketQuote[]>(loader, []);
  return { quotes: data, state };
}

// 实时资讯：币安官方公告列表
export function useLiveAnnouncements(limit = 5): {
  news: NewsItem[];
  state: LoadState;
} {
  const loader = useCallback(() => fetchAnnouncements(limit), [limit]);
  const { data, state } = useLivePolling<NewsItem[]>(loader, []);
  return { news: data, state };
}
