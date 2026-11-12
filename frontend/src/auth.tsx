import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./lib/client.ts";
import type { Me } from "./types.ts";

interface AuthCtx {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, org: string) => Promise<void>;
  logout: () => void;
}
const Ctx = createContext<AuthCtx | null>(null);
export const useAuth = (): AuthCtx => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState<boolean>(!!api.getToken());

  const logout = useCallback(() => { api.clearToken(); setUser(null); window.location.hash = "/"; }, []);

  useEffect(() => {
    if (!api.getToken()) return;
    api.me().then(setUser, () => setUser(null)).finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    const on = () => setUser(null); // token expired or revoked: drop to the login screen
    window.addEventListener("vg:unauthorized", on);
    return () => window.removeEventListener("vg:unauthorized", on);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    setUser(await api.me());
    window.location.hash = "/";
  }, []);
  const register = useCallback(async (email: string, password: string, org: string) => {
    await api.register(email, password, org);
    await login(email, password);
  }, [login]);

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
