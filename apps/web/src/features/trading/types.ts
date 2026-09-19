export type MarketGroup = "cn_equity" | "hk_us_equity" | "binance";

export type TradingProvider =
  | "tonghuashun"
  | "caixin"
  | "futu"
  | "longbridge"
  | "binance";

export type BinanceScope =
  | "spot"
  | "cross_margin"
  | "isolated_margin"
  | "usdm_futures";

export type CredentialType = "ed25519" | "hmac" | "rsa";

export type TradingAccountDraft = {
  alias: string;
  marketGroup: MarketGroup;
  provider: TradingProvider;
  environment: "production";
  credentialType?: CredentialType;
  apiKey?: string;
  privateKeyOrSecret?: string;
  enabledScopes: BinanceScope[];
  isolatedSymbols: string[];
  ipWhitelistConfirmed: boolean;
};

export type TradingAccount = {
  id: string;
  alias: string;
  provider: TradingProvider;
  environment: "production";
  fingerprint?: string;
  scopes: BinanceScope[];
  status: "pending_authorization" | "read_only" | "active" | "disabled";
  connectionStatus: "disconnected" | "checking" | "connected";
  tradingEnabled: boolean;
  lastSyncedAt: string | null;
};
