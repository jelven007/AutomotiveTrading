import type { ReactNode } from "react";

import { AuthContext, type AuthContextValue } from "./AuthContext";

const unavailable = async () => {
  throw new Error("本地无登录模式未启用身份操作");
};

const localWorkspace: AuthContextValue = {
  status: "authenticated",
  accessToken: null,
  claims: {
    sub: "local-user",
    tenant_id: "local-workspace",
    roles: ["tenant_admin"],
    exp: 4_102_444_800,
    iat: 0,
    mfa_enabled: false,
    mfa_time: null,
  },
  login: unavailable,
  register: unavailable,
  logout: async () => undefined,
  enrollMfa: unavailable,
  verifyMfa: unavailable,
  hasRecentMfa: () => false,
};

export function LocalWorkspaceProvider({ children }: { children: ReactNode }) {
  return (
    <AuthContext.Provider value={localWorkspace}>
      {children}
    </AuthContext.Provider>
  );
}
