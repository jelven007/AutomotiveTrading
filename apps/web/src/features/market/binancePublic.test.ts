import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAnnouncements, fetchMarketQuotes } from "./binancePublic";

// 按请求 URL 分派 mock 响应，模拟币安公开接口
function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string) => {
      if (input.includes("/ticker/24hr")) {
        return jsonResponse([
          {
            symbol: "BTCUSDT",
            lastPrice: "63842.10",
            priceChangePercent: "1.36",
          },
          {
            symbol: "ETHUSDT",
            lastPrice: "2450.55",
            priceChangePercent: "-0.82",
          },
        ]);
      }
      if (input.includes("/klines")) {
        // 4 号下标为收盘价
        return jsonResponse([
          [0, 0, 0, 0, "100"],
          [0, 0, 0, 0, "110"],
          [0, 0, 0, 0, "105"],
        ]);
      }
      if (input.includes("/cms/article/list/query")) {
        return jsonResponse({
          data: {
            catalogs: [
              {
                articles: [
                  {
                    id: 1,
                    code: "abc123",
                    title: "Binance Will List Foo",
                    releaseDate: 1789983001032,
                  },
                ],
              },
            ],
          },
        });
      }
      return jsonResponse({}, false);
    }),
  );
}

function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 500,
    json: async () => body,
  } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("binancePublic", () => {
  it("normalizes tickers and sparklines into market quotes", async () => {
    stubFetch();
    const quotes = await fetchMarketQuotes(["BTCUSDT", "ETHUSDT"]);

    expect(quotes).toHaveLength(2);
    expect(quotes[0]).toMatchObject({
      symbol: "BTCUSDT",
      displayName: "BTC/USDT",
      changePercent: "+1.36%",
      trend: "up",
    });
    expect(quotes[1]).toMatchObject({ trend: "down", changePercent: "-0.82%" });
    // 走势点位应覆盖完整 150 宽视图
    expect(quotes[0].points.startsWith("0.0,")).toBe(true);
    expect(quotes[0].points).toContain("150.0,");
  });

  it("maps announcements into linkable news items", async () => {
    stubFetch();
    const news = await fetchAnnouncements(5);

    expect(news).toHaveLength(1);
    expect(news[0]).toMatchObject({
      id: 1,
      title: "Binance Will List Foo",
      url: "https://www.binance.com/en/support/announcement/abc123",
    });
  });

  it("throws when the public endpoint fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false)));
    await expect(fetchAnnouncements()).rejects.toThrow("币安公开接口请求失败");
  });
});
