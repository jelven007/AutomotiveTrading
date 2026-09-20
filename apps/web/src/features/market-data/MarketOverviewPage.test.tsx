import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/authTestUtils";
import { MarketOverviewPage } from "./MarketOverviewPage";
import type { LatestQuotesResponse, MarketQuote } from "./types";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getTotalSize: () => count * 44,
    getVirtualItems: () =>
      Array.from({ length: count }, (_, index) => ({
        index,
        key: index,
        size: 44,
        start: index * 44,
      })),
    measureElement: () => undefined,
  }),
}));

function quote(
  symbol: string,
  name: string,
  exchange: "SSE" | "SZSE",
): MarketQuote {
  return {
    exchange,
    symbol,
    name,
    source_time: "2026-09-18T07:00:00Z",
    collected_at: "2026-09-20T01:31:03Z",
    last_price: "10.50",
    previous_close: "10.00",
    change_percent: "5.00",
    open_price: "10.10",
    high_price: "10.80",
    low_price: "9.90",
    volume: "120000",
    amount: "1260000",
    quality_status: "stale",
    quality_reasons: ["source_time_exceeded"],
    source_id: "tdx-node",
  };
}

const response: LatestQuotesResponse = {
  scope: ["SSE", "SZSE"],
  as_of: "2026-09-20T01:31:03Z",
  available: 2,
  returned: 2,
  quality: { stale: 2 },
  coverage: {
    status: "collected",
    expected: 2,
    received: 2,
    missing: 0,
    duration_ms: 2307,
    observed_at: "2026-09-20T01:31:04Z",
    source: "mootdx",
    markets: {
      SSE: {
        expected: 1,
        received: 1,
        missing: [],
        source_error: null,
        universe_complete: true,
      },
      SZSE: {
        expected: 1,
        received: 1,
        missing: [],
        source_error: null,
        universe_complete: true,
      },
    },
  },
  items: [
    quote("600000", "浦发银行", "SSE"),
    quote("000001", "平安银行", "SZSE"),
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MarketOverviewPage", () => {
  it("loads tenant-scoped real quotes and filters the virtual table", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => response,
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithAuth(<MarketOverviewPage />);

    expect(
      await screen.findByRole("heading", { name: "沪深行情" }),
    ).toBeInTheDocument();
    expect(screen.getByText("沪深覆盖完整")).toBeInTheDocument();
    expect(screen.getByText("MOOTDX 沪深候选集合")).toBeInTheDocument();
    expect(screen.getByText("浦发银行")).toBeInTheDocument();
    expect(screen.getByText("平安银行")).toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "质量状态" }),
    ).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/market/quotes/latest?limit=10000",
      expect.objectContaining({
        headers: { "X-Tenant-ID": "tenant-a" },
      }),
    );

    await user.type(screen.getByRole("textbox", { name: "搜索证券" }), "浦发");
    expect(screen.getByText("浦发银行")).toBeInTheDocument();
    expect(screen.queryByText("平安银行")).not.toBeInTheDocument();

    await user.clear(screen.getByRole("textbox", { name: "搜索证券" }));
    await user.click(screen.getByRole("button", { name: "深交所" }));
    await waitFor(() =>
      expect(screen.queryByText("浦发银行")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("平安银行")).toBeInTheDocument();
  });
});
