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

  it("keeps simulation and live environments visible on trading page", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("link", { name: /交易/ }));

    expect(
      screen.getByRole("heading", { name: "模拟交易", level: 2 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "实盘交易", level: 2 }),
    ).toBeInTheDocument();
  });
});
