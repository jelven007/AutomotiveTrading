import { readAccessToken } from "../auth/session";
import type {
  BinanceAccountDraft,
  BinanceAccountSummary,
  BinanceOverview,
} from "./types";

type BinanceAccountResponse = {
  alias: string;
  environment: "demo";
  api_key_fingerprint: string;
  connection_status: BinanceAccountSummary["connectionStatus"];
  last_verified_at: string;
};

type BinanceOverviewResponse = {
  account: BinanceAccountResponse;
  permissions: {
    status: "ok" | "error";
    data: {
      can_read: boolean;
      can_spot_trade: boolean;
      can_futures_trade: boolean;
      ip_restricted: boolean;
      can_withdraw: boolean;
      can_internal_transfer: boolean;
      can_universal_transfer: boolean;
    } | null;
    error: { code: string; message: string } | null;
  };
  spot: {
    status: "ok" | "error";
    data: {
      balances: Array<{
        asset: string;
        free: string;
        locked: string;
        total: string;
      }>;
      as_of: string;
    } | null;
    error: { code: string; message: string } | null;
  };
  usdm: {
    status: "ok" | "error";
    data: {
      balances: Array<{
        asset: string;
        wallet_balance: string;
        available_balance: string;
        unrealized_pnl: string;
      }>;
      positions: Array<{
        symbol: string;
        side: "long" | "short" | "flat";
        quantity: string;
        entry_price: string;
        mark_price: string | null;
        unrealized_pnl: string | null;
        leverage: number | null;
        margin_mode: "cross" | "isolated" | null;
      }>;
      as_of: string;
    } | null;
    error: { code: string; message: string } | null;
  };
  as_of: string;
};

const API_ROOT = "/api/v1/trading/binance";

export class TradingApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
  ) {
    super(message);
  }
}

export function getTradingAccessToken(): string | null {
  return readAccessToken();
}

export async function replaceBinanceAccount(
  accessToken: string,
  account: BinanceAccountDraft,
): Promise<BinanceAccountSummary> {
  const response = await fetch(`${API_ROOT}/account`, {
    method: "PUT",
    headers: authenticatedHeaders(accessToken, true),
    body: JSON.stringify({
      alias: account.alias,
      api_key: account.apiKey,
      api_secret: account.apiSecret,
      ip_whitelist_confirmed: account.ipWhitelistConfirmed,
    }),
  });
  return normalizeAccount(
    await parseResponse<BinanceAccountResponse>(response),
  );
}

export async function deleteBinanceAccount(accessToken: string): Promise<void> {
  const response = await fetch(`${API_ROOT}/account`, {
    method: "DELETE",
    headers: authenticatedHeaders(accessToken),
  });
  if (!response.ok) {
    await parseResponse<never>(response);
  }
}

export async function fetchBinanceOverview(
  accessToken: string,
  refresh = false,
): Promise<BinanceOverview> {
  const suffix = refresh ? "?refresh=true" : "";
  const response = await fetch(`${API_ROOT}/overview${suffix}`, {
    headers: authenticatedHeaders(accessToken),
  });
  return normalizeOverview(
    await parseResponse<BinanceOverviewResponse>(response),
  );
}

function authenticatedHeaders(
  accessToken: string,
  withContentType = false,
): Record<string, string> {
  return {
    Authorization: `Bearer ${accessToken}`,
    ...(withContentType ? { "Content-Type": "application/json" } : {}),
  };
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

function normalizeAccount(
  account: BinanceAccountResponse,
): BinanceAccountSummary {
  return {
    alias: account.alias,
    environment: account.environment,
    apiKeyFingerprint: account.api_key_fingerprint,
    connectionStatus: account.connection_status,
    lastVerifiedAt: account.last_verified_at,
  };
}

function normalizeOverview(overview: BinanceOverviewResponse): BinanceOverview {
  return {
    account: normalizeAccount(overview.account),
    permissions: {
      status: overview.permissions.status,
      data: overview.permissions.data
        ? {
            canRead: overview.permissions.data.can_read,
            canSpotTrade: overview.permissions.data.can_spot_trade,
            canFuturesTrade: overview.permissions.data.can_futures_trade,
            ipRestricted: overview.permissions.data.ip_restricted,
            canWithdraw: overview.permissions.data.can_withdraw,
            canInternalTransfer:
              overview.permissions.data.can_internal_transfer,
            canUniversalTransfer:
              overview.permissions.data.can_universal_transfer,
          }
        : null,
      error: overview.permissions.error,
    },
    spot: {
      status: overview.spot.status,
      data: overview.spot.data
        ? {
            balances: overview.spot.data.balances,
            asOf: overview.spot.data.as_of,
          }
        : null,
      error: overview.spot.error,
    },
    usdm: {
      status: overview.usdm.status,
      data: overview.usdm.data
        ? {
            balances: overview.usdm.data.balances.map((balance) => ({
              asset: balance.asset,
              walletBalance: balance.wallet_balance,
              availableBalance: balance.available_balance,
              unrealizedPnl: balance.unrealized_pnl,
            })),
            positions: overview.usdm.data.positions.map((position) => ({
              symbol: position.symbol,
              side: position.side,
              quantity: position.quantity,
              entryPrice: position.entry_price,
              markPrice: position.mark_price,
              unrealizedPnl: position.unrealized_pnl,
              leverage: position.leverage,
              marginMode: position.margin_mode,
            })),
            asOf: overview.usdm.data.as_of,
          }
        : null,
      error: overview.usdm.error,
    },
    asOf: overview.as_of,
  };
}
