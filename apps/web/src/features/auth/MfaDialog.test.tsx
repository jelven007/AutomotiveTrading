import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createAuthValue, renderWithAuth } from "../../test/authTestUtils";
import { MfaDialog } from "./MfaDialog";

const { toCanvas } = vi.hoisted(() => ({
  toCanvas: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("qrcode", () => ({
  default: { toCanvas },
}));

describe("MfaDialog", () => {
  it("verifies a six-digit code before continuing", async () => {
    const user = userEvent.setup();
    const verifyMfa = vi.fn().mockResolvedValue(undefined);
    const onVerified = vi.fn();
    renderWithAuth(<MfaDialog onCancel={vi.fn()} onVerified={onVerified} />, {
      verifyMfa,
    });

    await user.type(screen.getByLabelText("动态验证码"), "123456");
    await user.click(screen.getByRole("button", { name: "验证并继续" }));

    await waitFor(() => expect(verifyMfa).toHaveBeenCalledWith("123456"));
    expect(onVerified).toHaveBeenCalledOnce();
  });

  it("starts TOTP enrollment and renders its QR code", async () => {
    const user = userEvent.setup();
    const enrollMfa = vi.fn().mockResolvedValue({
      secret: "BASE32SECRET",
      provisioningUri: "otpauth://totp/Quant%20Desk:user",
    });
    renderWithAuth(<MfaDialog onCancel={vi.fn()} onVerified={vi.fn()} />, {
      claims: {
        ...createAuthValue().claims!,
        mfa_enabled: false,
        mfa_time: null,
      },
      enrollMfa,
    });

    await user.click(screen.getByRole("button", { name: "配置验证器" }));

    expect(await screen.findByText("BASE32SECRET")).toBeInTheDocument();
    await waitFor(() =>
      expect(toCanvas).toHaveBeenCalledWith(
        expect.any(HTMLCanvasElement),
        "otpauth://totp/Quant%20Desk:user",
        expect.objectContaining({ width: 184 }),
      ),
    );
  });
});
