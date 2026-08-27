"""Control Plane configuration loaded from environment / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    All fields are read from environment variables prefixed with ``CP_`` or from
    a local ``.env`` file. Secrets must never be hard-coded.
    """

    model_config = SettingsConfigDict(env_prefix="CP_", env_file=".env", extra="ignore")

    # --- Control plane database (not the per-user trade DBs) ---
    database_url: str = "sqlite:///./control_plane.sqlite"

    # --- Control plane's own session JWTs ---
    jwt_secret: str = "change-me"
    jwt_access_ttl_minutes: int = 30
    jwt_refresh_ttl_days: int = 7
    jwt_algorithm: str = "HS256"

    # --- Secret vault ---
    fernet_key: str = ""

    # --- Public origin (used for CORS_origins of each bot) ---
    public_origin: str = "https://localhost"

    # --- Per-user Freqtrade containers ---
    freqtrade_image: str = "freqtradeorg/freqtrade:stable"
    bot_network: str = "control-plane-bots"
    bot_data_root: str = "/srv/control-plane/bots"
    # Fallback exchange for a user who has no exchange credential yet, i.e. dry-run only.
    # Deliberately NOT restricted to ``SUPPORTED_EXCHANGES``: that allowlist guards the
    # real-money path (stored credentials), while this only picks which public market data
    # a paper bot reads, so local smoke tests can point it at a reachable exchange.
    default_exchange: str = "binance"
    # How the control plane addresses bot containers:
    #   "dns"       -> http://<container_name>:8080 (control plane runs on the bot network)
    #   "docker_ip" -> resolve the container IP via the Docker SDK (host-side dev)
    bot_address_mode: str = "dns"

    # --- Live (real-money) trading guard rails ---
    # Hard ceiling on the TOTAL stake a live bot may deploy, in stake currency.
    # Emitted into the bot config as ``available_capital``, so Freqtrade enforces it
    # independently of the control plane's own validation.
    live_max_capital: float = 25.0
    # Floor for a live per-trade stake. Binance's MIN_NOTIONAL is 5 USDT, but Freqtrade
    # inflates the effective minimum with ``amount_reserve_percent`` and the stoploss;
    # a stake under a pair's minimum makes Freqtrade skip every trade *silently*.
    live_min_stake: float = 10.0
    # Probe exchange API keys against the exchange before storing them. Disabled by the
    # smoke tests, which store deliberately fake keys.
    validate_exchange_keys: bool = True

    # --- Trading-state reconciliation ---
    # Bot containers boot with ``initial_state: stopped``, so a host reboot leaves every
    # bot idle and silent. ``services/reconciler.py`` re-starts the ones whose owner had
    # them trading. Seconds between passes; 0 disables the loop entirely.
    trading_reconcile_interval: float = 60.0

    # --- Public results page (unauthenticated) ---
    # Serves an anonymous, read-only rollup of every account's trading results at
    # ``GET /api/public/results``. Set to false to take the page down instantly, with no
    # code change and no redeploy of the SPA.
    public_results_enabled: bool = True
    # Seconds a collected rollup is reused. The endpoint fans out to every bot, so this
    # is what stops an anonymous burst from amplifying into N requests per caller.
    public_results_ttl: float = 20.0
    # Per-IP request budget, in requests per minute, before the endpoint answers 429.
    public_results_rate_limit: int = 30

    # --- Bootstrap admin ---
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
