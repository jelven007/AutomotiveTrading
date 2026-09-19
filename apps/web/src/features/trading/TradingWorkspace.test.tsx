import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BinanceTradingPage } from "../../pages/trading/BinanceTradingPage";

function jsonResponse(body: object, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("TradingWorkspace API integration", () => {
  it("only shows an account after the trading API accepts the credentials", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("qt.access_token", "access-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            id: "account-1",
            alias: "主帐号",
            market_group: "binance",
            provider: "binance",
            environment: "production",
            credential_type: "ed25519",
            api_key_fingerprint: "sha256:1234567890abcdef",
            status: "read_only",
            connection_status: "connected",
            trading_enabled: false,
            scopes: [{ scope_type: "spot" }],
            last_synced_at: "2026-09-19T12:00:00Z",
          },
          201,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter initialEntries={["/trading/binance"]}>
        <BinanceTradingPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: "添加帐号" }));
    await user.type(
      screen.getByRole("textbox", { name: "帐号别名" }),
      "主帐号",
    );
    await user.type(screen.getByLabelText("API Key"), "api-key-sensitive");
    await user.type(
      screen.getByLabelText("Ed25519 私钥"),
      "private-key-sensitive",
    );
    await user.click(
      screen.getByRole("checkbox", {
        name: "已配置固定出口 IP 白名单",
      }),
    );
    await user.click(screen.getByRole("button", { name: "保存为只读帐号" }));

    expect(
      await screen.findByText("sha256:1234567890abcdef"),
    ).toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("api-key-sensitive"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("private-key-sensitive"),
    ).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/v1/trading/accounts/bind",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer access-token",
        }),
      }),
    );
  });

  it("does not create a local account when the login session is missing", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/trading/binance"]}>
        <BinanceTradingPage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "添加帐号" }));
    await user.type(
      screen.getByRole("textbox", { name: "帐号别名" }),
      "未保存帐号",
    );
    await user.type(screen.getByLabelText("API Key"), "api-key-sensitive");
    await user.type(
      screen.getByLabelText("Ed25519 私钥"),
      "private-key-sensitive",
    );
    await user.click(
      screen.getByRole("checkbox", {
        name: "已配置固定出口 IP 白名单",
      }),
    );
    await user.click(screen.getByRole("button", { name: "保存为只读帐号" }));

    expect(
      await screen.findByText("登录会话不可用，帐号未保存。"),
    ).toBeInTheDocument();
    expect(screen.queryByText("未保存帐号")).not.toBeInTheDocument();
  });
});
