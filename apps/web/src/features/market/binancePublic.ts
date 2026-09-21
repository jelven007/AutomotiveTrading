// 币安公开数据取数：行情走 data-api.binance.vision，资讯走公告 CMS。
// 均为浏览器可直连的公开接口（CORS: *），无需 API Key。

const MARKET_ROOT = "https://data-api.binance.vision/api/v3";
const CMS_ROOT = "https://www.binance.com/bapi/composite/v1/public/cms";
const ANNOUNCEMENT_BASE = "https://www.binance.com/en/support/announcement";

// 首页行情展示的现货交易对
export const MARKET_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"];

export type MarketQuote = {
  symbol: string; // 原始交易对，如 BTCUSDT
  displayName: string; // 展示名，如 BTC/USDT
  price: string; // 已格式化的现价
  changePercent: string; // 带符号的 24h 涨跌幅，如 +1.36%
  trend: "up" | "down"; // 走势方向，驱动配色
  points: string; // 迷你走势 polyline 点位（150x42 viewBox）
};

export type NewsItem = {
  id: number;
  title: string;
  url: string;
  time: string; // 已格式化的发布时间
};

type Ticker24hr = {
  symbol: string;
  lastPrice: string;
  priceChangePercent: string;
};

type AnnouncementResponse = {
  data?: {
    catalogs?: Array<{
      articles?: Array<{
        id: number;
        code: string;
        title: string;
        releaseDate: number;
      }>;
    }>;
  };
};

// 拉取行情：一次批量取 24hr ticker，再并行取各交易对的走势
export async function fetchMarketQuotes(
  symbols: string[] = MARKET_SYMBOLS,
): Promise<MarketQuote[]> {
  const query = encodeURIComponent(JSON.stringify(symbols));
  const [tickers, sparklines] = await Promise.all([
    fetchJson<Ticker24hr[]>(`${MARKET_ROOT}/ticker/24hr?symbols=${query}`),
    Promise.all(symbols.map((symbol) => fetchSparkline(symbol))),
  ]);

  // 以 symbol 建索引，保证展示顺序与传入 symbols 一致
  const tickerBySymbol = new Map(tickers.map((item) => [item.symbol, item]));
  return symbols.map((symbol, index) => {
    const ticker = tickerBySymbol.get(symbol);
    const changePercent = Number(ticker?.priceChangePercent ?? "0");
    return {
      symbol,
      displayName: toDisplayName(symbol),
      price: formatPrice(Number(ticker?.lastPrice ?? "0")),
      changePercent: formatPercent(changePercent),
      trend: changePercent >= 0 ? "up" : "down",
      points: sparklines[index],
    };
  });
}

// 拉取资讯：币安公告 CMS 的“新币上线”栏目
export async function fetchAnnouncements(limit = 5): Promise<NewsItem[]> {
  const url =
    `${CMS_ROOT}/article/list/query` +
    `?type=1&catalogId=48&pageNo=1&pageSize=${limit}`;
  const payload = await fetchJson<AnnouncementResponse>(url);
  const articles = payload.data?.catalogs?.[0]?.articles ?? [];
  return articles.slice(0, limit).map((article) => ({
    id: article.id,
    title: article.title,
    url: `${ANNOUNCEMENT_BASE}/${article.code}`,
    time: formatDate(article.releaseDate),
  }));
}

// 取单个交易对近 24 小时 K 线并归一化为 polyline 点位
async function fetchSparkline(symbol: string): Promise<string> {
  const klines = await fetchJson<unknown[][]>(
    `${MARKET_ROOT}/klines?symbol=${symbol}&interval=1h&limit=24`,
  );
  // K 线数组下标 4 为收盘价
  const closes = klines.map((row) => Number(row[4]));
  return buildSparklinePoints(closes);
}

// 将收盘价序列映射到 150x42 视图坐标；y 轴翻转使高价位于上方
function buildSparklinePoints(closes: number[]): string {
  if (closes.length < 2) {
    return "0,21 150,21";
  }
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  return closes
    .map((close, index) => {
      const x = (index / (closes.length - 1)) * 150;
      const y = 40 - ((close - min) / range) * 38;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`币安公开接口请求失败（${response.status}）`);
  }
  return (await response.json()) as T;
}

function toDisplayName(symbol: string): string {
  // 目前均为 USDT 计价，拆分为「基础/计价」形式
  return symbol.endsWith("USDT") ? `${symbol.slice(0, -4)}/USDT` : symbol;
}

function formatPrice(value: number): string {
  // 高价保留 2 位、低价保留更多位，兼顾可读性
  const digits = value >= 100 ? 2 : value >= 1 ? 3 : 5;
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatDate(epochMs: number): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(epochMs));
}
