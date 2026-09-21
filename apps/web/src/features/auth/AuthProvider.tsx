import { ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import {
  enrollTotp,
  loginAccount,
  logoutAccount,
  refreshAccount,
  registerAccount,
  verifyTotp,
} from "./api";
import type { LoginRequest, RegistrationRequest, TokenResponse } from "./api";
import { AuthContext, AuthStatus } from "./AuthContext";
import {
  AuthSession,
  clearAuthSession,
  decodeAccessToken,
  hasRecentMfa,
  isAccessTokenCurrent,
  readAuthSession,
  writeAuthSession,
} from "./session";

type Props = {
  children: ReactNode;
};

export function AuthProvider({ children }: Props) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const applyTokenResponse = useCallback((response: TokenResponse) => {
    const next = {
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
    };
    if (!decodeAccessToken(next.accessToken)) {
      throw new Error("身份服务返回了无效的访问令牌");
    }
    writeAuthSession(next);
    setSession(next);
    setStatus("authenticated");
  }, []);

  const clearSession = useCallback(() => {
    clearAuthSession();
    setSession(null);
    setStatus("anonymous");
  }, []);

  const refreshSession = useCallback(
    async (refreshToken: string) => {
      try {
        applyTokenResponse(await refreshAccount(refreshToken));
      } catch {
        clearSession();
      }
    },
    [applyTokenResponse, clearSession],
  );

  useEffect(() => {
    const stored = readAuthSession();
    if (!stored) {
      setStatus("anonymous");
      return;
    }
    if (isAccessTokenCurrent(stored.accessToken)) {
      setSession(stored);
      setStatus("authenticated");
      return;
    }
    void refreshSession(stored.refreshToken);
  }, [refreshSession]);

  useEffect(() => {
    if (!session) {
      return;
    }
    const claims = decodeAccessToken(session.accessToken);
    if (!claims) {
      clearSession();
      return;
    }
    const delay = Math.max(claims.exp * 1000 - Date.now() - 30_000, 0);
    const timer = window.setTimeout(
      () => void refreshSession(session.refreshToken),
      Math.min(delay, 2_147_483_647),
    );
    return () => window.clearTimeout(timer);
  }, [clearSession, refreshSession, session]);

  const login = useCallback(
    async (input: LoginRequest) => {
      const normalized = {
        ...input,
        email: input.email.trim().toLowerCase(),
      };
      const response = await loginAccount(normalized);
      applyTokenResponse(response);
      localStorage.setItem("qt.last_email", normalized.email);
    },
    [applyTokenResponse],
  );

  const register = useCallback(
    async (input: RegistrationRequest) => {
      const normalized = {
        ...input,
        email: input.email.trim().toLowerCase(),
      };
      const response = await registerAccount(normalized);
      applyTokenResponse(response);
      localStorage.setItem("qt.last_email", normalized.email);
    },
    [applyTokenResponse],
  );

  const logout = useCallback(async () => {
    if (session) {
      try {
        await logoutAccount(session.accessToken);
      } catch {
        // 服务端会话不可用时仍需清理浏览器中的本地会话。
      } finally {
        clearSession();
      }
      return;
    }
    clearSession();
  }, [clearSession, session]);

  const enrollMfa = useCallback(async () => {
    if (!session) {
      throw new Error("登录会话不可用");
    }
    return enrollTotp(session.accessToken);
  }, [session]);

  const verifyMfa = useCallback(
    async (code: string) => {
      if (!session) {
        throw new Error("登录会话不可用");
      }
      const accessToken = await verifyTotp(session.accessToken, code);
      const next = { ...session, accessToken };
      writeAuthSession(next);
      setSession(next);
    },
    [session],
  );

  const value = useMemo(
    () => ({
      status,
      accessToken: session?.accessToken ?? null,
      claims: session ? decodeAccessToken(session.accessToken) : null,
      login,
      register,
      logout,
      enrollMfa,
      verifyMfa,
      hasRecentMfa: () => session !== null && hasRecentMfa(session.accessToken),
    }),
    [enrollMfa, login, logout, register, session, status, verifyMfa],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
