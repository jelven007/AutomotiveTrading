import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AccountBindingDialog } from "./AccountBindingDialog";

describe("AccountBindingDialog", () => {
  it("binds a production binance account and clears credentials", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(
      <AccountBindingDialog
        marketGroup="binance"
        providers={["binance"]}
        onCancel={vi.fn()}
        onSave={onSave}
      />,
    );

    expect(
      screen.getByRole("option", { name: "Ed25519（推荐）" }),
    ).toBeInTheDocument();
    for (const scope of ["现货", "全仓杠杆", "逐仓杠杆", "U 本位永续"]) {
      expect(screen.getByRole("checkbox", { name: scope })).toBeInTheDocument();
    }

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
      screen.getByRole("checkbox", { name: "已配置固定出口 IP 白名单" }),
    );
    await user.click(screen.getByRole("button", { name: "保存为只读帐号" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        alias: "主帐号",
        provider: "binance",
        environment: "production",
        credentialType: "ed25519",
        enabledScopes: ["spot"],
        ipWhitelistConfirmed: true,
      }),
    );
    expect(
      screen.queryByDisplayValue("api-key-sensitive"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("private-key-sensitive"),
    ).not.toBeInTheDocument();
  });

  it("clears entered credentials before cancelling", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <AccountBindingDialog
        marketGroup="binance"
        providers={["binance"]}
        onCancel={onCancel}
        onSave={vi.fn()}
      />,
    );

    await user.type(screen.getByLabelText("API Key"), "temporary-api-key");
    await user.type(
      screen.getByLabelText("Ed25519 私钥"),
      "temporary-private-key",
    );
    await user.click(screen.getByRole("button", { name: "取消" }));

    expect(onCancel).toHaveBeenCalledOnce();
    expect(
      screen.queryByDisplayValue("temporary-api-key"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("temporary-private-key"),
    ).not.toBeInTheDocument();
  });

  it("only offers approved providers for each securities market", () => {
    const { rerender } = render(
      <AccountBindingDialog
        marketGroup="cn_equity"
        providers={["tonghuashun", "caixin"]}
        onCancel={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByRole("option", { name: "同花顺" })).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "财信证券" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "富途" }),
    ).not.toBeInTheDocument();

    rerender(
      <AccountBindingDialog
        marketGroup="hk_us_equity"
        providers={["futu", "longbridge"]}
        onCancel={vi.fn()}
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByRole("option", { name: "富途" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "长桥" })).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "同花顺" }),
    ).not.toBeInTheDocument();
  });
});
