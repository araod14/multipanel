import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import { login as apiLogin, logout as apiLogout } from "../api/auth";
import { tokenStore, type Kind } from "../api/tokenStore";

interface AuthState {
  kind: Kind | null;
  isAuthed: boolean;
  login: (identifier: string, password: string) => Promise<Kind>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [kind, setKind] = useState<Kind | null>(tokenStore.kind);

  const value = useMemo<AuthState>(
    () => ({
      kind,
      isAuthed: kind !== null && tokenStore.access !== null,
      async login(identifier, password) {
        const { kind: k } = await apiLogin(identifier, password);
        setKind(k);
        return k;
      },
      logout() {
        apiLogout();
        setKind(null);
      },
    }),
    [kind],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
