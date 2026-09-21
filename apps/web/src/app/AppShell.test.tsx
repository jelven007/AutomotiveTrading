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
      detail: "未绑定币安账号",
    }),
  } as Response;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(missingAccountResponse()));
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
  });

  it("renders the home page on the root path", () => {
    renderShell();

    expect(
      screen.getByRole("heading", { name: "首页", level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "行情", level: 2 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "资讯", level: 2 }),
    ).toBeInTheDocument();
  });

  it("renders the strategies page with statistics and the strategy table", () => {
    renderShell("/strategies");

    expect(
      screen.getByRole("heading", { name: "策略", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText("策略总数")).toBeInTheDocument();
    expect(screen.getByText("多因子动量")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "创建策略" }),
    ).toBeInTheDocument();
  });

  it("renders total assets and open orders on the trading page", async () => {
    renderShell("/trading");

    expect(
      screen.getByRole("heading", { name: "交易", level: 1 }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "总资产", level: 2 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "当前订单", level: 2 }),
    ).toBeInTheDocument();
    // 订单能力尚未开放，展示阶段二占位提示
    expect(
      screen.getByText("下单与撤单能力将于阶段二开放后接入。"),
    ).toBeInTheDocument();
  });
});
