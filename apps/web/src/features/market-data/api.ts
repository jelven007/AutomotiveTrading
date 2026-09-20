import type {
  BarsResponse,
  Exchange,
  InstrumentHistoryResponse,
  LatestQuotesResponse,
  MinutesResponse,
  TransactionsResponse,
} from "./types";

const LATEST_QUOTES_URL = "/api/v1/market/quotes/latest?limit=10000";

export async function getLatestQuotes(
  tenantId: string,
  signal?: AbortSignal,
): Promise<LatestQuotesResponse> {
  const response = await fetch(LATEST_QUOTES_URL, {
    headers: { "X-Tenant-ID": tenantId },
    signal,
  });
  if (!response.ok) {
    throw new Error(`行情接口返回 ${response.status}`);
  }
  return (await response.json()) as LatestQuotesResponse;
}

export async function getInstrumentHistory(
  tenantId: string,
  exchange: Exchange,
  symbol: string,
  signal?: AbortSignal,
): Promise<InstrumentHistoryResponse> {
  const prefix = `/api/v1/market`;
  const headers = { "X-Tenant-ID": tenantId };
  const [bars, minutes, transactions] = await Promise.all([
    request<BarsResponse>(
      `${prefix}/bars/${exchange}/${symbol}?interval=1d&limit=240`,
      headers,
      signal,
    ),
    request<MinutesResponse>(
      `${prefix}/minutes/${exchange}/${symbol}`,
      headers,
      signal,
    ),
    request<TransactionsResponse>(
      `${prefix}/transactions/${exchange}/${symbol}?limit=200`,
      headers,
      signal,
    ),
  ]);
  return { bars, minutes, transactions };
}

async function request<T>(
  url: string,
  headers: Record<string, string>,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(url, { headers, signal });
  if (!response.ok) {
    throw new Error(`历史行情接口返回 ${response.status}`);
  }
  return (await response.json()) as T;
}
