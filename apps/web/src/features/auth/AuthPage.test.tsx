import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthPage } from "../../pages/AuthPage";
import { renderWithAuth } from "../../test/authTestUtils";
import { AuthApiError } from "./api";

afterEach(() => {
  localStorage.clear();
});

describe("AuthPage", () => {
  it("submits the login identity", async () => {
    const user = userEvent.setup();
    const login = vi.fn().mockResolvedValue(undefined);
    renderWithAuth(<AuthPage />, {
      status: "anonymous",
      accessToken: null,
      claims: null,
      login,
    });

    await user.type(screen.getByLabelText("邮箱"), "admin@example.com");
    await user.type(screen.getByLabelText("密码"), "strong-password");
    await user.click(screen.getByRole("button", { name: "登录" }));

    expect(login).toHaveBeenCalledWith({
      email: "admin@example.com",
      password: "strong-password",
    });
  });

  it("validates password confirmation before registration", async () => {
    const user = userEvent.setup();
    const register = vi.fn();
    renderWithAuth(<AuthPage />, {
      status: "anonymous",
      accessToken: null,
      claims: null,
      register,
    });

    await user.click(screen.getByRole("tab", { name: "注册" }));
    await user.type(screen.getByLabelText("邮箱"), "admin@example.com");
    await user.type(screen.getByLabelText("密码"), "strong-password");
    await user.type(screen.getByLabelText("确认密码"), "different-password");
    await user.click(screen.getByRole("button", { name: "创建并登录" }));

    expect(screen.getByRole("alert")).toHaveTextContent("两次输入的密码不一致");
    expect(register).not.toHaveBeenCalled();
  });

  it("explains when production registration is already closed", async () => {
    const user = userEvent.setup();
    const register = vi
      .fn()
      .mockRejectedValue(
        new AuthApiError(
          "system owner has already been registered",
          "registration.closed",
          409,
        ),
      );
    renderWithAuth(<AuthPage />, {
      status: "anonymous",
      accessToken: null,
      claims: null,
      register,
    });

    await user.click(screen.getByRole("tab", { name: "注册" }));
    await user.type(screen.getByLabelText("邮箱"), "second@example.com");
    await user.type(screen.getByLabelText("密码"), "strong-password");
    await user.type(screen.getByLabelText("确认密码"), "strong-password");
    await user.click(screen.getByRole("button", { name: "创建并登录" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "系统已完成初始化，请使用所有者账号登录",
    );
  });
});
