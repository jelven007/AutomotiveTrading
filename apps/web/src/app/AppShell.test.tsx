import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppShell } from "./AppShell";

function renderShell(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AppShell />
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  it("shows five primary workspaces and context selectors", () => {
    renderShell();

    const navigation = screen.getByRole("navigation", { name: "主导航" });
    for (const label of ["首页", "资讯", "策略", "交易", "数据"]) {
      expect(navigation).toHaveTextContent(label);
    }

    expect(
      screen.getByRole("combobox", { name: "当前租户" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "当前市场" }),
    ).toBeInTheDocument();
  });

  it("redirects trading to the cn workspace and exposes market navigation", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("link", { name: /交易/ }));

    expect(
      await screen.findByRole("heading", { name: "沪深交易", level: 1 }),
    ).toBeInTheDocument();
    const marketNavigation = screen.getByRole("navigation", {
      name: "交易市场",
    });
    for (const label of ["沪深", "港美", "币安"]) {
      expect(marketNavigation).toHaveTextContent(label);
    }
    expect(
      screen.getByRole("button", { name: "添加帐号" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "尚未添加帐号", level: 2 }),
    ).toBeInTheDocument();
    expect(screen.queryByText("贵州茅台")).not.toBeInTheDocument();
  });

  it("shows all supported product scopes in the binance workspace", () => {
    renderShell("/trading/binance");

    expect(
      screen.getByRole("heading", { name: "币安交易", level: 1 }),
    ).toBeInTheDocument();
    const productNavigation = screen.getByRole("tablist", {
      name: "币安产品",
    });
    for (const label of ["现货", "全仓杠杆", "逐仓杠杆", "U 本位永续"]) {
      expect(productNavigation).toHaveTextContent(label);
    }
    expect(screen.getByText("生产交易未启用")).toBeInTheDocument();
  });
});
