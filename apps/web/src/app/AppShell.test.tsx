import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../test/authTestUtils";
import { AppShell } from "./AppShell";

function renderShell(initialPath = "/") {
  return renderWithAuth(
    <MemoryRouter initialEntries={[initialPath]}>
      <AppShell />
    </MemoryRouter>,
  );
}

function missingAccountResponse(): Response {
  return {
    ok: false,
    status: 404,
    json: async () => ({
      code: "binance.account_missing",
      detail: "未绑定B账号",
    }),
  } as Response;
}

function healthyResponse(): Response {
  return {
    ok: true,
    status: 200,
    json: async () => ({ status: "ready" }),
  } as Response;
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        String(input).endsWith("/api/v1/trading/health")
          ? healthyResponse()
          : missingAccountResponse(),
      ),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AppShell", () => {
  it("exposes the three primary sections and the current user", async () => {
    renderShell();

    const navigation = screen.getByRole("navigation", { name: "主导航" });
    expect(navigation).toHaveTextContent("首页");
    expect(navigation).toHaveTextContent("策略");
    expect(navigation).toHaveTextContent("交易");

    const userLink = screen.getByRole("link", {
      name: "用户详情 admin@example.com",
    });
    expect(userLink).toHaveTextContent("admin@example.com");
    expect(await screen.findByText("系统正常")).toBeInTheDocument();
  });

  it("renders the home page on the root path", () => {
    renderShell();

    expect(
      screen.getByRole("heading", { name: "行情", level: 2 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "资讯", level: 2 }),
    ).toBeInTheDocument();
  });

  it("marks unavailable strategy actions as planned", () => {
    renderShell("/strategies");

    expect(
      screen.getByRole("heading", { name: "策略", level: 2 }),
    ).toBeInTheDocument();
    expect(screen.getByText("策略功能规划中")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "策略" })).toBeDisabled();
  });

  it("renders assets and orders on the trading page", async () => {
    renderShell("/trading");

    expect(
      await screen.findByRole("heading", { name: "资产", level: 2 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "订单", level: 2 }),
    ).toBeInTheDocument();
    // 订单能力尚未开放，展示空列表提示
    expect(screen.getByText("当前没有进行中的订单")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "订单" })).toBeDisabled();
  });
});
