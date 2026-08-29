"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getMe, login as loginRequest, logoutSession, refreshToken, type AuthUser } from "@/lib/api";

type AuthContextValue = {
  user: AuthUser | null;
  accessToken: string | null;
  refreshTokenValue: string | null;
  loading: boolean;
  authError: string | null;
  login: (email: string, password: string) => Promise<AuthUser>;
  logout: () => void;
  setSession: (accessToken: string, refreshTokenValue: string, user: AuthUser) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const ACCESS_KEY = "nadi_access_token";
const REFRESH_KEY = "nadi_refresh_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshTokenValue, setRefreshTokenValue] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  function setSession(nextAccessToken: string, nextRefreshToken: string, nextUser: AuthUser) {
    localStorage.setItem(ACCESS_KEY, nextAccessToken);
    localStorage.setItem(REFRESH_KEY, nextRefreshToken);
    setAccessToken(nextAccessToken);
    setRefreshTokenValue(nextRefreshToken);
    setUser(nextUser);
    setAuthError(null);
  }

  function logout() {
    const storedAccess = localStorage.getItem(ACCESS_KEY);
    const storedRefresh = localStorage.getItem(REFRESH_KEY);
    logoutSession(storedRefresh, storedAccess).catch(() => undefined);
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    setAccessToken(null);
    setRefreshTokenValue(null);
    setUser(null);
  }

  async function login(email: string, password: string) {
    const tokens = await loginRequest(email, password);
    setSession(tokens.access_token, tokens.refresh_token, tokens.user);
    return tokens.user;
  }

  useEffect(() => {
    async function recover() {
      const storedAccess = localStorage.getItem(ACCESS_KEY);
      const storedRefresh = localStorage.getItem(REFRESH_KEY);
      if (!storedAccess || !storedRefresh) {
        setLoading(false);
        return;
      }
      try {
        const recovered = await getMe(storedAccess);
        setAccessToken(storedAccess);
        setRefreshTokenValue(storedRefresh);
        setUser(recovered);
      } catch {
        try {
          const tokens = await refreshToken(storedRefresh);
          setSession(tokens.access_token, tokens.refresh_token, tokens.user);
        } catch {
          logout();
          setAuthError("Session expired");
        }
      } finally {
        setLoading(false);
      }
    }
    recover();
  }, []);

  const value = useMemo(
    () => ({ user, accessToken, refreshTokenValue, loading, authError, login, logout, setSession }),
    [user, accessToken, refreshTokenValue, loading, authError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}
