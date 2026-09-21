export const ACCESS_TOKEN_KEY = "qt.access_token";
export const REFRESH_TOKEN_KEY = "qt.refresh_token";
export const LAST_EMAIL_KEY = "qt.last_email";

export type AuthClaims = {
  sub: string;
  email: string | null;
  tenant_id: string;
  roles: string[];
  exp: number;
  iat: number;
  mfa_enabled: boolean;
  mfa_time: number | null;
};

export type AuthSession = {
  accessToken: string;
  refreshToken: string;
};

export function readAuthSession(): AuthSession | null {
  const accessToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = sessionStorage.getItem(REFRESH_TOKEN_KEY);
  return accessToken && refreshToken ? { accessToken, refreshToken } : null;
}

export function writeAuthSession(session: AuthSession): void {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, session.accessToken);
  sessionStorage.setItem(REFRESH_TOKEN_KEY, session.refreshToken);
}

export function clearAuthSession(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function readAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

export function decodeAccessToken(accessToken: string): AuthClaims | null {
  try {
    const payload = accessToken.split(".")[1];
    if (!payload) {
      return null;
    }
    const normalized = payload.replaceAll("-", "+").replaceAll("_", "/");
    const decoded = JSON.parse(
      atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=")),
    );
    if (
      typeof decoded.sub !== "string" ||
      typeof decoded.tenant_id !== "string" ||
      !Array.isArray(decoded.roles) ||
      typeof decoded.exp !== "number" ||
      typeof decoded.iat !== "number"
    ) {
      return null;
    }
    return {
      sub: decoded.sub,
      email: typeof decoded.email === "string" ? decoded.email : null,
      tenant_id: decoded.tenant_id,
      roles: decoded.roles.map(String),
      exp: decoded.exp,
      iat: decoded.iat,
      mfa_enabled: decoded.mfa_enabled === true,
      mfa_time: typeof decoded.mfa_time === "number" ? decoded.mfa_time : null,
    };
  } catch {
    return null;
  }
}

export function isAccessTokenCurrent(
  accessToken: string,
  nowSeconds = Date.now() / 1000,
): boolean {
  const claims = decodeAccessToken(accessToken);
  return claims !== null && claims.exp > nowSeconds + 30;
}

export function hasRecentMfa(
  accessToken: string,
  maxAgeSeconds = 300,
  nowSeconds = Date.now() / 1000,
): boolean {
  const claims = decodeAccessToken(accessToken);
  return (
    claims?.mfa_time !== null &&
    claims?.mfa_time !== undefined &&
    nowSeconds - claims.mfa_time <= maxAgeSeconds
  );
}
