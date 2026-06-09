import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import { tokenStore } from "./tokenStore";

// Single axios instance for the whole app. Base path is /api (proxied in dev,
// same-origin behind Caddy in prod).
export const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = tokenStore.access;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.refresh;
  if (!refresh) return null;
  try {
    const res = await axios.post("/api/auth/refresh", { refresh_token: refresh });
    const access = res.data.access_token as string;
    tokenStore.setAccess(access);
    return access;
  } catch {
    tokenStore.clear();
    return null;
  }
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean };
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      refreshing = refreshing ?? refreshAccessToken();
      const access = await refreshing;
      refreshing = null;
      if (access) {
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      }
      // Refresh failed: bounce to login.
      if (location.pathname !== "/login") location.assign("/login");
    }
    return Promise.reject(error);
  },
);
