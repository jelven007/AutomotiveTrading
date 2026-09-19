export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: "Bearer";
  expires_in: number;
};

export type LoginRequest = {
  email: string;
  password: string;
  tenantId: string;
};

export type RegistrationRequest = {
  email: string;
  displayName: string;
  password: string;
  tenantName: string;
};

export type TotpEnrollment = {
  secret: string;
  provisioningUri: string;
};

export class AuthApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message);
  }
}

const API_ROOT = "/api/v1/auth";

export async function loginAccount(input: LoginRequest): Promise<TokenResponse> {
  return request<TokenResponse>(`${API_ROOT}/login`, {
    method: "POST",
    body: JSON.stringify({
      email: input.email,
      password: input.password,
      tenant_id: input.tenantId,
    }),
  });
}

export async function registerAccount(
  input: RegistrationRequest,
): Promise<TokenResponse> {
  return request<TokenResponse>(`${API_ROOT}/register`, {
    method: "POST",
    body: JSON.stringify({
      email: input.email,
      display_name: input.displayName,
      password: input.password,
      tenant_name: input.tenantName,
    }),
  });
}

export async function refreshAccount(
  refreshToken: string,
): Promise<TokenResponse> {
  return request<TokenResponse>(`${API_ROOT}/refresh`, {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function logoutAccount(accessToken: string): Promise<void> {
  await request<void>(`${API_ROOT}/logout`, {
    method: "POST",
    accessToken,
  });
}

export async function enrollTotp(
  accessToken: string,
): Promise<TotpEnrollment> {
  const response = await request<{
    secret: string;
    provisioning_uri: string;
  }>(`${API_ROOT}/mfa/totp/enroll`, {
    method: "POST",
    accessToken,
  });
  return {
    secret: response.secret,
    provisioningUri: response.provisioning_uri,
  };
}

export async function verifyTotp(
  accessToken: string,
  code: string,
): Promise<string> {
  const response = await request<{ access_token: string }>(
    `${API_ROOT}/mfa/totp/verify`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({ code }),
    },
  );
  return response.access_token;
}

type RequestOptions = RequestInit & {
  accessToken?: string;
};

async function request<T>(
  url: string,
  { accessToken, headers, ...options }: RequestOptions,
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...headers,
    },
  });
  if (response.status === 204) {
    return undefined as T;
  }
  const payload = (await response.json()) as
    | T
    | { code?: string; detail?: string; message?: string };
  if (!response.ok) {
    const problem = payload as {
      code?: string;
      detail?: string;
      message?: string;
    };
    throw new AuthApiError(
      problem.detail || problem.message || "身份服务请求失败",
      problem.code || "auth.request_failed",
      response.status,
    );
  }
  return payload as T;
}
