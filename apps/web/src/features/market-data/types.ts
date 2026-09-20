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
