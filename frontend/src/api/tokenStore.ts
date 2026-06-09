// Small persistent store for the control plane's own session tokens.

export type Kind = "admin" | "user";

const ACCESS = "cp_access";
const REFRESH = "cp_refresh";
const KIND = "cp_kind";

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS);
  },
  get refresh() {
    return localStorage.getItem(REFRESH);
  },
  get kind(): Kind | null {
    return localStorage.getItem(KIND) as Kind | null;
  },
  set(access: string, refresh: string, kind: Kind) {
    localStorage.setItem(ACCESS, access);
    localStorage.setItem(REFRESH, refresh);
    localStorage.setItem(KIND, kind);
  },
  setAccess(access: string) {
    localStorage.setItem(ACCESS, access);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
    localStorage.removeItem(KIND);
  },
};
