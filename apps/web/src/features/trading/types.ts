export type BinanceAccountDraft = {
  alias: string;
  apiKey: string;
  apiSecret: string;
};

export type BinanceAccountSummary = {
  alias: string;
  environment: "demo";
  apiKeyFingerprint: string;
  connectionStatus: "connected" | "disconnected" | "error";
  lastVerifiedAt: string;
};

export type BinancePermissionOverview = {
  canRead: boolean;
  canSpotTrade: boolean;
  canFuturesTrade: boolean;
  canWithdraw: boolean;
  canInternalTransfer: boolean;
  canUniversalTransfer: boolean;
};

export type SpotBalance = {
  asset: string;
  free: string;
  locked: string;
  total: string;
};

export type UsdmBalance = {
  asset: string;
  walletBalance: string;
  availableBalance: string;
  unrealizedPnl: string;
};

export type UsdmPosition = {
  symbol: string;
  side: "long" | "short" | "flat";
  quantity: string;
  entryPrice: string;
  markPrice: string | null;
  unrealizedPnl: string | null;
  leverage: number | null;
  marginMode: "cross" | "isolated" | null;
};

export type OverviewSection<T> = {
  status: "ok" | "error";
  data: T | null;
  error: { code: string; message: string } | null;
};

export type BinanceOverview = {
  account: BinanceAccountSummary;
  permissions: OverviewSection<BinancePermissionOverview>;
  spot: OverviewSection<{ balances: SpotBalance[]; asOf: string }>;
  usdm: OverviewSection<{
    balances: UsdmBalance[];
    positions: UsdmPosition[];
    asOf: string;
  }>;
  asOf: string;
};
