export type Exchange = "SSE" | "SZSE";

export type QualityStatus =
  | "healthy"
  | "stale"
  | "partial"
  | "conflict"
  | "invalid"
  | "unavailable";

export type MarketQuote = {
  exchange: Exchange;
  symbol: string;
  name: string;
  source_time: string | null;
  collected_at: string | null;
  last_price: string;
  previous_close: string;
  change_percent: string;
  open_price: string;
  high_price: string;
  low_price: string;
  volume: string;
  amount: string;
  quality_status: QualityStatus;
  quality_reasons: string[];
  source_id: string;
};

export type MarketCoverage = {
  status: "collected" | "partial";
  expected: number;
  received: number;
  missing: number;
  duration_ms: number;
  observed_at: string | null;
  source: "mootdx";
  markets: Record<
    Exchange,
    {
      expected: number;
      received: number;
      missing: string[];
      source_error: string | null;
      universe_complete: boolean;
    }
  >;
};

export type LatestQuotesResponse = {
  scope: Exchange[];
  as_of: string | null;
  available: number;
  returned: number;
  quality: Record<string, number>;
  coverage: MarketCoverage | null;
  items: MarketQuote[];
};

export type HistoryCoverage = "collected" | "partial" | "pending";

type HistoryResponse<T> = {
  provider: "mootdx";
  exchange: Exchange;
  symbol: string;
  trade_date?: string | null;
  coverage: HistoryCoverage;
  items: T[];
};

export type MarketBar = {
  event_time: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
  amount: string;
  source_id: string;
  quality_status: "healthy" | "partial";
};

export type MarketMinute = {
  event_time: string;
  price: string;
  volume: string;
  source_offset: number;
  source_id: string;
  quality_status: "healthy" | "partial";
};

export type MarketTransaction = {
  event_time: string;
  price: string;
  quantity: string;
  side: "buy" | "sell" | "neutral";
  source_offset: number;
  source_id: string;
  quality_status: "healthy" | "partial";
};

export type BarsResponse = HistoryResponse<MarketBar>;
export type MinutesResponse = HistoryResponse<MarketMinute>;
export type TransactionsResponse = HistoryResponse<MarketTransaction>;

export type InstrumentHistoryResponse = {
  bars: BarsResponse;
  minutes: MinutesResponse;
  transactions: TransactionsResponse;
};
