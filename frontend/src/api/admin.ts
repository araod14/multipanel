import { api } from "./client";
import type {
  BotInstance,
  ExchangeCredentialInput,
  ExchangeCredentialMeta,
  User,
} from "./types";

export interface CreateUserInput {
  username: string;
  email: string;
  password: string;
}

export const adminApi = {
  async listUsers(): Promise<User[]> {
    return (await api.get("/admin/users")).data;
  },
  async createUser(input: CreateUserInput): Promise<User> {
    return (await api.post("/admin/users", input)).data;
  },
  async deleteUser(userId: number): Promise<void> {
    await api.delete(`/admin/users/${userId}`);
  },
  async getBot(userId: number): Promise<BotInstance> {
    return (await api.get(`/admin/users/${userId}/bot`)).data;
  },
  async provision(userId: number): Promise<BotInstance> {
    return (await api.post(`/admin/users/${userId}/provision`)).data;
  },
  async startBot(userId: number): Promise<BotInstance> {
    return (await api.post(`/admin/users/${userId}/bot/start`)).data;
  },
  async stopBot(userId: number): Promise<BotInstance> {
    return (await api.post(`/admin/users/${userId}/bot/stop`)).data;
  },
  async setMode(userId: number, dryRun: boolean): Promise<BotInstance> {
    return (await api.post(`/admin/users/${userId}/bot/mode`, { dry_run: dryRun })).data;
  },
  async rotateCredentials(userId: number): Promise<BotInstance> {
    return (await api.post(`/admin/users/${userId}/bot/rotate-credentials`)).data;
  },
  async getExchange(userId: number): Promise<ExchangeCredentialMeta> {
    return (await api.get(`/admin/users/${userId}/exchange`)).data;
  },
  async setExchange(
    userId: number,
    input: ExchangeCredentialInput,
  ): Promise<ExchangeCredentialMeta> {
    return (await api.put(`/admin/users/${userId}/exchange`, input)).data;
  },
  async deleteExchange(userId: number): Promise<void> {
    await api.delete(`/admin/users/${userId}/exchange`);
  },
};
