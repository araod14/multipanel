import { api } from "./client";
import type { BotConfig, BotConfigInput, BotInstance } from "./types";

// The user API is a guarded proxy: /me/bot/ft/<path> forwards to the user's own
// Freqtrade instance. Responses are passed through as-is, so these are loosely typed.

export const userApi = {
  async myBot(): Promise<BotInstance> {
    return (await api.get("/me/bot")).data;
  },
  async getConfig(): Promise<BotConfig> {
    return (await api.get("/me/bot/config")).data;
  },
  async saveConfig(body: BotConfigInput): Promise<BotConfig> {
    return (await api.put("/me/bot/config", body)).data;
  },
  async ft<T = unknown>(path: string): Promise<T> {
    return (await api.get(`/me/bot/ft/${path}`)).data;
  },
  async ftPost<T = unknown>(path: string, body?: unknown): Promise<T> {
    return (await api.post(`/me/bot/ft/${path}`, body)).data;
  },
  // Convenience wrappers for the common endpoints.
  status: () => userApi.ft("status"),
  profit: () => userApi.ft("profit"),
  balance: () => userApi.ft("balance"),
  whitelist: () => userApi.ft("whitelist"),
  daily: () => userApi.ft("daily"),
  trades: () => userApi.ft("trades"),
  logs: () => userApi.ft("logs"),
  start: () => userApi.ftPost("start"),
  stop: () => userApi.ftPost("stop"),
  forceEnter: (pair: string, side: "long" | "short" = "long") =>
    userApi.ftPost("forceenter", { pair, side }),
  forceExit: (tradeid: string) => userApi.ftPost("forceexit", { tradeid }),
};
