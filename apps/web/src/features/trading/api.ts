import type {
  BinanceScope,
  CredentialType,
  MarketGroup,
  TradingAccount,
  TradingAccountDraft,
  TradingProvider,
} from "./types";

type AccountResponse = {
  id: string;
  alias: string;
  market_group: MarketGroup;
  provider: TradingProvider;
  environment: "production";
  credential_type: CredentialType | null;
  api_key_fingerprint: string | null;
  status: TradingAccount["status"];
  connection_status: TradingAccount["connectionStatus"];
  trading_enabled: boolean;
  scopes: Array<{ scope_type: BinanceScope }>;
  last_synced_at: string | null;
};

const API_ROOT = "/api/v1/trading";

export class TradingApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
  ) {
    super(message);
  }
}

export function getTradingAccessToken(): string | null {
  return sessionStorage.getItem("qt.access_token");
}

export async function fetchTradingAccounts(
  accessToken: string,
  marketGroup: MarketGroup,
): Promise<TradingAccount[]> {
  const response = await fetch(`${API_ROOT}/accounts`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const payload = await parseResponse<AccountResponse[]>(response);
  return payload
    .filter((account) => account.market_group === marketGroup)
    .map(normalizeAccount);
}

export async function bindTradingAccount(
  accessToken: string,
  account: TradingAccountDraft,
): Promise<TradingAccount> {
  const response = await fetch(`${API_ROOT}/accounts/bind`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      alias: account.alias,
      market_group: account.marketGroup,
      provider: account.provider,
      environment: account.environment,
      credential_type: account.credentialType,
      api_key: account.apiKey,
      private_key_or_secret: account.privateKeyOrSecret,
      enabled_scopes: account.enabledScopes,
      isolated_symbols: account.isolatedSymbols,
      ip_whitelist_confirmed: account.ipWhitelistConfirmed,
    }),
  });
  return normalizeAccount(await parseResponse<AccountResponse>(response));
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as
    | T
    | { code?: string; detail?: string };
  if (!response.ok) {
    const problem = payload as { code?: string; detail?: string };
    throw new TradingApiError(
      problem.detail || "交易服务请求失败",
      problem.code || "trading.request_failed",
    );
  }
  return payload as T;
}

function normalizeAccount(account: AccountResponse): TradingAccount {
  return {
    id: account.id,
    alias: account.alias,
    provider: account.provider,
    environment: account.environment,
    fingerprint: account.api_key_fingerprint ?? undefined,
    scopes: account.scopes.map((scope) => scope.scope_type),
    status: account.status,
    connectionStatus: account.connection_status,
    tradingEnabled: account.trading_enabled,
    lastSyncedAt: account.last_synced_at,
  };
}
