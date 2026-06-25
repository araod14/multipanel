// Shared API types mirroring the backend Pydantic schemas.

export type BotStatus = "provisioned" | "running" | "stopped" | "error";
export type UserStatus = "active" | "suspended";

export interface User {
  id: number;
  username: string;
  email: string;
  status: UserStatus;
  created_at: string;
}

export interface BotInstance {
  id: number;
  user_id: number;
  container_name: string;
  internal_hostname: string;
  status: BotStatus;
  dry_run: boolean;
  stake_currency: string;
  created_at: string;
  last_seen_at: string | null;
}

export interface ExchangeCredentialMeta {
  exchange_name: string;
  key_masked: string;
  has_password: boolean;
  has_uid: boolean;
  updated_at: string;
}

export interface ExchangeCredentialInput {
  exchange_name: string;
  key: string;
  secret: string;
  password?: string;
  uid?: string;
}

export interface StrategyOption {
  key: string;
  label: string;
  description: string;
}

export interface RoiStep {
  minutes: number;
  roi: number;
}

export type PairlistMode = "static" | "volume";

export interface BotConfig {
  strategy: string;
  pairlist_mode: PairlistMode;
  pairs: string[];
  volume_number_assets: number;
  stake_currency: string;
  stake_amount: number | string;
  max_open_trades: number;
  stoploss: number;
  roi_table: RoiStep[];
  timeframe: string;
  trailing_stop: boolean;
  trailing_stop_positive: number | null;
  trailing_stop_positive_offset: number;
  dry_run_wallet: number;
  available_strategies: StrategyOption[];
  available_timeframes: string[];
  available_pairlist_modes: PairlistMode[];
  available_base_coins: string[];
}

export type BotConfigInput = Partial<
  Pick<
    BotConfig,
    | "strategy"
    | "pairlist_mode"
    | "pairs"
    | "volume_number_assets"
    | "stake_amount"
    | "max_open_trades"
    | "stoploss"
    | "roi_table"
    | "timeframe"
    | "trailing_stop"
    | "trailing_stop_positive"
    | "trailing_stop_positive_offset"
    | "dry_run_wallet"
  >
>;
