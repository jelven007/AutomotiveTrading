import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  it("only exposes Binance and the current user", async () => {
    const user = userEvent.setup();
    renderShell();

    const navigation = screen.getByRole("navigation", { name: "主导航" });
    expect(navigation).toHaveTextContent("币安");
    expect(navigation).not.toHaveTextContent("策略");
    expect(navigation).not.toHaveTextContent("数据");

    const userLink = screen.getByRole("link", {
      name: "用户详情 admin@example.com",
    });
    expect(userLink).toHaveTextContent("admin@example.com");
    expect(
      screen.queryByRole("combobox", { name: "当前市场" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "账户菜单" }),
    ).not.toBeInTheDocument();

    await user.click(userLink);
    expect(
      screen.getByRole("heading", { name: "用户详情", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("admin@example.com")).toHaveLength(2);
  });

  it("redirects the root path to the Binance account", async () => {
    renderShell();

    expect(
      await screen.findByRole("heading", { name: "币安账户", level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "添加账号" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "尚未绑定币安账号", level: 2 }),
    ).toBeInTheDocument();
  });

  it("does not expose trading controls in the read-only binance workspace", async () => {
    renderShell("/trading/binance");

    expect(
      await screen.findByRole("heading", { name: "币安账户", level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "急停" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "下单" }),
    ).not.toBeInTheDocument();
  });
});
