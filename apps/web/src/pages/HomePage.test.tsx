import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "./HomePage";

// 复用一份成功响应，覆盖行情与资讯两类请求
function stubSuccess() {
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
        ]);
      }
      if (input.includes("/klines")) {
        return jsonResponse([
          [0, 0, 0, 0, "100"],
          [0, 0, 0, 0, "120"],
        ]);
      }
      return jsonResponse({
        data: {
          catalogs: [
            {
              articles: [
                {
                  id: 9,
                  code: "code9",
                  title: "Binance Will List Bar",
                  releaseDate: 1789983001032,
                },
              ],
            },
          ],
        },
      });
    }),
  );
}

function jsonResponse(body: unknown, ok = true): Response {
  return { ok, status: ok ? 200 : 500, json: async () => body } as Response;
}

beforeEach(() => {
  stubSuccess();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HomePage", () => {
  it("renders live Binance market quotes and announcements", async () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { name: "行情", level: 2 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "资讯", level: 2 }),
    ).toBeInTheDocument();

    // 行情：展示归一化后的交易对
    expect(await screen.findByText("BTC/USDT")).toBeInTheDocument();
    // 资讯：公告标题渲染为可点击外链
    const link = await screen.findByRole("link", {
      name: "查看公告 Binance Will List Bar",
    });
    expect(link).toHaveAttribute(
      "href",
      "https://www.binance.com/en/support/announcement/code9",
    );
  });

  it("shows an error state when the market endpoint fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false)));
    render(<HomePage />);

    await waitFor(() => {
      expect(
        screen.getByText("行情数据加载失败，请稍后重试"),
      ).toBeInTheDocument();
    });
  });

  it("silently re-fetches every 5 seconds", async () => {
    vi.useFakeTimers();
    try {
      render(<HomePage />);
      const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
      // 首次加载后清零，仅统计定时器触发的请求
      await vi.waitFor(() =>
        expect(fetchMock.mock.calls.length).toBeGreaterThan(0),
      );
      fetchMock.mockClear();

      // 推进 5 秒，应触发一轮静默刷新（行情 + 资讯）
      await vi.advanceTimersByTimeAsync(5000);
      expect(fetchMock).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
