import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithAuth } from "../../test/authTestUtils";
import { BinanceAssetsPanel } from "./BinanceAssetsPanel";

vi.mock("../market/BtcSpotPriceCard", () => ({
  BtcSpotPriceCard: () => <div>BTC/USDT</div>,
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BinanceAssetsPanel", () => {
  it("submits the account after one MFA step without re-entering credentials", async () => {
    const user = userEvent.setup();
    const verifyMfa = vi.fn().mockResolvedValue("elevated-access-token");
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PUT") {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              alias: "模拟账号",
              environment: "demo",
              api_key_fingerprint: "sha256:1234567890abcdef",
              connection_status: "connected",
              last_verified_at: "2026-09-22T08:00:00Z",
            }),
          };
        }
        return {
          ok: false,
          status: 404,
          json: async () => ({
            code: "binance.account_missing",
            detail: "未绑定B账号",
          }),
        };
      },
    );
    vi.stubGlobal(
      "fetch",
      fetchMock,
    );
    renderWithAuth(<BinanceAssetsPanel />, {
      hasRecentMfa: () => false,
      verifyMfa,
    });

    await user.click(await screen.findByRole("button", { name: "模拟账号" }));
    expect(
      screen.getByRole("heading", { name: "添加B模拟账号" }),
    ).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "账号别名" }), "模拟账号");
    await user.type(screen.getByLabelText("API Key"), "demo-api-key");
    await user.type(screen.getByLabelText("API Secret"), "demo-api-secret");
    await user.click(
      screen.getByRole("checkbox", { name: "已配置固定出口 IP 白名单" }),
    );
    await user.click(screen.getByRole("button", { name: "保存账号" }));

    expect(
      screen.getByRole("heading", { name: "验证身份" }),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText("动态验证码"), "123456");
    await user.click(screen.getByRole("button", { name: "验证并继续" }));

    await waitFor(() => {
      expect(verifyMfa).toHaveBeenCalledWith("123456");
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/trading/binance/account",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            alias: "模拟账号",
            api_key: "demo-api-key",
            api_secret: "demo-api-secret",
            ip_whitelist_confirmed: true,
          }),
        }),
      );
    });
  });
});
