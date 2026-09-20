import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppRouter } from "./router";

describe("AppRouter", () => {
  it("opens the workspace directly without a login gate", () => {
    window.history.pushState({}, "", "/");
    render(<AppRouter />);

    expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
    expect(screen.queryByText("登录 Quant Desk")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "登录" }),
    ).not.toBeInTheDocument();
  });
});
