import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { BinanceOverview } from "./types";
import { BinanceAccountOverview } from "./BinanceAccountOverview";

function overview(): BinanceOverview {
  return {
    account: {
      alias: "主账号",
      environment: "demo",
      apiKeyFingerprint: "sha256:1234567890abcdef",
      connectionStatus: "connected",
      lastVerifiedAt: "2026-09-21T08:00:00Z",
    },
    permissions: {
      status: "ok",
      data: {
        canRead: true,
        canSpotTrade: true,
        canFuturesTrade: true,
        ipRestricted: true,
        canWithdraw: false,
        canInternalTransfer: false,
        canUniversalTransfer: false,
      },
      error: null,
    },
    spot: {
      status: "ok",
      data: {
        balances: [{ asset: "BTC", free: "0.25", locked: "0", total: "0.25" }],
        asOf: "2026-09-21T08:00:00Z",
      },
      error: null,
    },
    usdm: {
      status: "ok",
      data: {
        balances: [
          {
            asset: "USDT",
            walletBalance: "1000",
            availableBalance: "800",
            unrealizedPnl: "12.5",
          },
        ],
        positions: [
          {
            symbol: "BTCUSDT",
            side: "long",
            quantity: "0.01",
            entryPrice: "60000",
            markPrice: "61250",
            unrealizedPnl: "12.5",
            leverage: 5,
            marginMode: "cross",
          },
        ],
        asOf: "2026-09-21T08:00:00Z",
      },
      error: null,
    },
    asOf: "2026-09-21T08:00:00Z",
  };
}

describe("BinanceAccountOverview", () => {
  it("switches between spot, USD-M, and permission views", async () => {
    const user = userEvent.setup();
    render(<BinanceAccountOverview overview={overview()} />);

    expect(screen.getByRole("tab", { name: "现货资产" })).toBeInTheDocument();
    expect(screen.getByText("BTC")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "U 本位" }));
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("5x")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "API 权限" }));
    expect(screen.getByText("读取")).toBeInTheDocument();
    expect(screen.getByText("固定 IP")).toBeInTheDocument();
  });

  it("keeps healthy sections available when spot fails", async () => {
    const user = userEvent.setup();
    const partial = overview();
    partial.spot = {
      status: "error",
      data: null,
      error: {
        code: "binance.spot_unavailable",
        message: "现货数据暂不可用",
      },
    };
    render(<BinanceAccountOverview overview={partial} />);

    expect(screen.getByText("现货数据暂不可用")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "U 本位" }));
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
  });
});
