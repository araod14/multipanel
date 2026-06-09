import axios from "axios";

import { tokenStore, type Kind } from "./tokenStore";

export interface LoginResult {
  kind: Kind;
}

// Login uses a bare axios call (no auth header / interceptors needed).
export async function login(identifier: string, password: string): Promise<LoginResult> {
  const res = await axios.post("/api/auth/login", { identifier, password });
  const { access_token, refresh_token, kind } = res.data;
  tokenStore.set(access_token, refresh_token, kind);
  return { kind };
}

export function logout() {
  tokenStore.clear();
}
