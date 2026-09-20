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

vi.mock("lightweight-charts", () => ({
  CandlestickSeries: {},
  ColorType: { Solid: "solid" },
  HistogramSeries: {},
  LineSeries: {},
  createChart: () => ({
    addSeries: () => ({
      priceScale: () => ({ applyOptions: vi.fn() }),
      setData: vi.fn(),
    }),
    applyOptions: vi.fn(),
    remove: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn() }),
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

  it("opens persisted minute, daily bar, and transaction views", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      const data = url.includes("/bars/")
        ? {
            provider: "mootdx",
            exchange: "SSE",
            symbol: "600000",
            coverage: "collected",
            items: [
              {
                event_time: "2026-09-18T07:00:00Z",
                open: "9.05",
                high: "9.15",
                low: "9.00",
                close: "9.07",
                volume: "51759300",
                amount: "469969408",
                source_id: "tdx-node",
                quality_status: "healthy",
              },
            ],
          }
        : url.includes("/minutes/")
          ? {
              provider: "mootdx",
              exchange: "SSE",
              symbol: "600000",
              trade_date: "2026-09-18",
              coverage: "collected",
              items: [
                {
                  event_time: "2026-09-18T01:31:00Z",
                  price: "9.02",
                  volume: "1360400",
                  source_offset: 0,
                  source_id: "tdx-node",
                  quality_status: "healthy",
                },
              ],
            }
          : url.includes("/transactions/")
            ? {
                provider: "mootdx",
                exchange: "SSE",
                symbol: "600000",
                trade_date: "2026-09-18",
                coverage: "partial",
                items: [
                  {
                    event_time: "2026-09-18T01:31:00Z",
                    price: "9.02",
                    quantity: "300",
                    side: "buy",
                    source_offset: 0,
                    source_id: "tdx-node",
                    quality_status: "partial",
                  },
                ],
              }
            : response;
      return Promise.resolve({ ok: true, status: 200, json: async () => data });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithAuth(<MarketOverviewPage />);

    await user.click(
      await screen.findByRole("button", { name: /浦发银行 600000/ }),
    );
    expect(
      await screen.findByRole("heading", { name: "浦发银行 600000" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "分时" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await user.click(screen.getByRole("tab", { name: "日 K" }));
    expect(screen.getByText("1 根")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "分笔" }));
    expect(screen.getByText("买入")).toBeInTheDocument();
    expect(screen.getByText("覆盖可能不完整")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/market/minutes/SSE/600000",
      expect.objectContaining({ headers: { "X-Tenant-ID": "tenant-a" } }),
    );
  });
});
