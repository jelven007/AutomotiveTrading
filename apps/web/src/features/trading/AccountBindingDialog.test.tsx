import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AccountBindingDialog } from "./AccountBindingDialog";

describe("AccountBindingDialog", () => {
  it("binds a B Demo account and clears credentials", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<AccountBindingDialog onCancel={vi.fn()} onSave={onSave} />);

    expect(
      screen.getByRole("heading", { name: "添加B模拟账号" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "凭据类型" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("group", { name: "帐号 Scope" }),
    ).not.toBeInTheDocument();

    await user.type(
      screen.getByRole("textbox", { name: "账号别名" }),
      "主帐号",
    );
    await user.type(screen.getByLabelText("API Key"), "api-key-sensitive");
    await user.type(screen.getByLabelText("API Secret"), "secret-sensitive");
    await user.click(
      screen.getByRole("checkbox", { name: "已配置固定出口 IP 白名单" }),
    );
    await user.click(screen.getByRole("button", { name: "保存账号" }));

    expect(onSave).toHaveBeenCalledWith({
      alias: "主帐号",
      apiKey: "api-key-sensitive",
      apiSecret: "secret-sensitive",
      ipWhitelistConfirmed: true,
    });
    expect(
      screen.queryByDisplayValue("api-key-sensitive"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("secret-sensitive"),
    ).not.toBeInTheDocument();
  });

  it("clears entered credentials before cancelling", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<AccountBindingDialog onCancel={onCancel} onSave={vi.fn()} />);

    await user.type(screen.getByLabelText("API Key"), "temporary-api-key");
    await user.type(screen.getByLabelText("API Secret"), "temporary-secret");
    await user.click(screen.getByRole("button", { name: "取消" }));

    expect(onCancel).toHaveBeenCalledOnce();
    expect(
      screen.queryByDisplayValue("temporary-api-key"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("temporary-secret"),
    ).not.toBeInTheDocument();
  });
});
