import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppRouter } from "./router";

describe("AppRouter", () => {
  afterEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("opens the login page when no authenticated session exists", async () => {
    window.history.pushState({}, "", "/");
    render(<AppRouter />);

    expect(await screen.findByText("登录 Quant Desk")).toBeVisible();
    expect(
      screen.queryByRole("navigation", { name: "主导航" }),
    ).not.toBeInTheDocument();
  });
});
