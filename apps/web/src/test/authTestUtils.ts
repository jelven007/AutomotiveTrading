import { createElement, ReactElement } from "react";
import { render } from "@testing-library/react";

import { AuthContext, AuthContextValue } from "../features/auth/AuthContext";

export function createAuthValue(
  overrides: Partial<AuthContextValue> = {},
): AuthContextValue {
  return {
    status: "authenticated",
    accessToken: "access-token",
    claims: {
      sub: "user-a",
      email: "admin@example.com",
      tenant_id: "tenant-a",
      roles: ["tenant_admin"],
      exp: Math.floor(Date.now() / 1000) + 900,
      iat: Math.floor(Date.now() / 1000),
      mfa_enabled: true,
      mfa_time: Math.floor(Date.now() / 1000),
    },
    login: async () => undefined,
    register: async () => undefined,
    logout: async () => undefined,
    enrollMfa: async () => ({
      secret: "BASE32SECRET",
      provisioningUri: "otpauth://totp/Quant%20Desk:user",
    }),
    verifyMfa: async () => undefined,
    hasRecentMfa: () => true,
    ...overrides,
  };
}

export function renderWithAuth(
  element: ReactElement,
  value?: Partial<AuthContextValue>,
) {
  return render(
    createElement(
      AuthContext.Provider,
      { value: createAuthValue(value) },
      element,
    ),
  );
}
