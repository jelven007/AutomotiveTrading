import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithProvider } from "../../test/renderAuthProvider";
import { useAuth } from "./AuthContext";

function jsonResponse(body: object, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function accessToken(mfaTime: number | null = null, expiresIn = 900): string {
  const now = Math.floor(Date.now() / 1000);
  const payload = btoa(
    JSON.stringify({
      sub: "user-a",
      email: "admin@example.com",
      tenant_id: "tenant-a",
      roles: ["tenant_admin"],
      iat: now,
      exp: now + expiresIn,
      mfa_enabled: mfaTime !== null,
      mfa_time: mfaTime,
    }),
  )
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
  return `header.${payload}.signature`;
}

function AuthProbe() {
  const auth = useAuth();
  return (
    <div>
      <span>{auth.status}</span>
      <span>{auth.claims?.tenant_id ?? "no-tenant"}</span>
      <span>{auth.hasRecentMfa() ? "mfa-ready" : "mfa-required"}</span>
      <button
        onClick={() =>
          void auth.login({
            email: "admin@example.com",
            password: "strong-password",
          })
        }
      >
        login
      </button>
      <button onClick={() => void auth.verifyMfa("123456")}>mfa</button>
    </div>
  );
}

afterEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("AuthProvider", () => {
  it("stores a login session and replaces the access token after MFA", async () => {
    const user = userEvent.setup();
    const now = Math.floor(Date.now() / 1000);
    const loginToken = accessToken();
    const elevatedToken = accessToken(now);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: loginToken,
          refresh_token: "refresh-token",
          token_type: "Bearer",
          expires_in: 900,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: elevatedToken,
          token_type: "Bearer",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProvider(<AuthProbe />);

    expect(await screen.findByText("anonymous")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "login" }));

    expect(await screen.findByText("tenant-a")).toBeInTheDocument();
    expect(sessionStorage.getItem("qt.access_token")).toBe(loginToken);
    expect(screen.getByText("mfa-required")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "mfa" }));

    await waitFor(() =>
      expect(sessionStorage.getItem("qt.access_token")).toBe(elevatedToken),
    );
    expect(screen.getByText("mfa-ready")).toBeInTheDocument();
  });

  it("refreshes an expired stored session during startup", async () => {
    const refreshedToken = accessToken();
    sessionStorage.setItem("qt.access_token", accessToken(null, -60));
    sessionStorage.setItem("qt.refresh_token", "old-refresh-token");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        access_token: refreshedToken,
        refresh_token: "new-refresh-token",
        token_type: "Bearer",
        expires_in: 900,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProvider(<AuthProbe />);

    expect(await screen.findByText("authenticated")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/refresh",
      expect.objectContaining({ method: "POST" }),
    );
    expect(sessionStorage.getItem("qt.refresh_token")).toBe(
      "new-refresh-token",
    );
  });
});
