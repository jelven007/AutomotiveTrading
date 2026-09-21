import { createContext, useContext } from "react";

import type { LoginRequest, RegistrationRequest, TotpEnrollment } from "./api";
import type { AuthClaims } from "./session";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export type AuthContextValue = {
  status: AuthStatus;
  accessToken: string | null;
  claims: AuthClaims | null;
  login: (input: LoginRequest) => Promise<void>;
  register: (input: RegistrationRequest) => Promise<void>;
  logout: () => Promise<void>;
  enrollMfa: () => Promise<TotpEnrollment>;
  verifyMfa: (code: string) => Promise<void>;
  hasRecentMfa: () => boolean;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("AuthProvider is required");
  }
  return context;
}
