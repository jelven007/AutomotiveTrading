import type { LatestQuotesResponse } from "./types";

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
