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
  it("requires recent MFA before opening account binding", async () => {
    const user = userEvent.setup();
    const verifyMfa = vi.fn().mockResolvedValue("elevated-access-token");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({
          code: "binance.account_missing",
          detail: "未绑定B账号",
        }),
      }),
    );
    renderWithAuth(<BinanceAssetsPanel />, {
      hasRecentMfa: () => false,
      verifyMfa,
    });

    await user.click(await screen.findByRole("button", { name: "模拟账号" }));
    expect(
      screen.getByRole("heading", { name: "验证身份" }),
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("动态验证码"), "123456");
    await user.click(screen.getByRole("button", { name: "验证并继续" }));

    await waitFor(() => {
      expect(verifyMfa).toHaveBeenCalledWith("123456");
      expect(
        screen.getByRole("heading", { name: "添加B模拟账号" }),
      ).toBeInTheDocument();
    });
  });
});
