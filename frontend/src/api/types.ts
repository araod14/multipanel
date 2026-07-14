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

// --- Freqtrade REST responses (subset of fields we actually consume) ---
// These mirror the per-bot Freqtrade API forwarded through /me/bot/ft/*.

/** GET /profit — aggregate trade statistics. */
export interface FtProfit {
  profit_closed_coin: number;
  profit_closed_ratio: number;
  profit_all_coin: number;
  profit_all_ratio: number;
  winning_trades: number;
  losing_trades: number;
  winrate: number;
  profit_factor: number;
  expectancy: number;
  avg_duration: string;
  best_pair: string;
  best_pair_profit_abs: number;
  max_drawdown: number;
  closed_trade_count: number;
  trade_count: number;
}

/** GET /performance — one entry per traded pair. */
export interface FtPerformanceEntry {
  pair: string;
  profit_abs: number;
  profit_ratio: number;
  count: number;
}

/** A single closed trade from GET /trades. */
export interface FtTrade {
  trade_id: number;
  pair: string;
  is_short: boolean;
  strategy: string;
  profit_abs: number;
  profit_ratio: number;
  close_profit_abs: number | null;
  open_rate: number;
  close_rate: number | null;
  open_date: string;
  close_date: string | null;
  exit_reason: string | null;
}

/** GET /trades?limit=&offset= — paginated closed-trade history. */
export interface FtTradesResponse {
  trades: FtTrade[];
  trades_count: number;
  offset: number;
  total_trades: number;
}

/** One currency line from GET /balance. */
export interface FtBalanceCurrency {
  currency: string;
  free: number;
  balance: number;
  est_stake: number;
}

/** GET /balance — wallet balances. */
export interface FtBalance {
  currencies: FtBalanceCurrency[];
  total: number;
  total_bot: number;
  symbol: string;
  stake: string;
  starting_capital: number;
}

/** GET /stats — win/loss breakdown by exit reason and durations. */
export interface FtExitReasonStat {
  wins: number;
  losses: number;
  draws: number;
}

export interface FtStats {
  exit_reasons: Record<string, FtExitReasonStat>;
  durations: Record<string, number | null>;
}
