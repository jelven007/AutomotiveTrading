import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ModelServicesPage } from "../../pages/settings/ModelServicesPage";

describe("ModelServicesPage", () => {
  it("lets tenant administrators add a model without retaining the API key", async () => {
    const user = userEvent.setup();
    render(<ModelServicesPage role="tenant_admin" />);

    await user.click(screen.getByRole("button", { name: "新增模型服务" }));
    await user.type(
      screen.getByRole("textbox", { name: "配置名称" }),
      "研究主模型",
    );
    await user.type(
      screen.getByRole("textbox", { name: "模型 ID" }),
      "gpt-production",
    );
    await user.type(screen.getByLabelText("API Key"), "sk-never-render-again");
    await user.click(screen.getByRole("button", { name: "保存配置" }));

    expect(screen.getByText("研究主模型")).toBeInTheDocument();
    expect(
      screen.queryByDisplayValue("sk-never-render-again"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("sk-never-render-again")).not.toBeInTheDocument();
    expect(screen.getByText("已配置")).toBeInTheDocument();
  });

  it("marks planned providers and disables connection testing", () => {
    render(<ModelServicesPage role="tenant_admin" />);

    expect(screen.getByText("本地 Ollama")).toBeInTheDocument();
    expect(screen.getByText("待开放")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "测试 本地 Ollama" }),
    ).toBeDisabled();
  });

  it("keeps model administration read-only for researchers", () => {
    render(<ModelServicesPage role="researcher" />);

    expect(screen.getByText("仅可查看与选择已启用模型")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "新增模型服务" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /轮换/ }),
    ).not.toBeInTheDocument();
  });
});
