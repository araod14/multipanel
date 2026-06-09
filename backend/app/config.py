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
    # Default exchange used when a user has no exchange credential yet (dry-run).
    default_exchange: str = "binance"
    # How the control plane addresses bot containers:
    #   "dns"       -> http://<container_name>:8080 (control plane runs on the bot network)
    #   "docker_ip" -> resolve the container IP via the Docker SDK (host-side dev)
    bot_address_mode: str = "dns"

    # --- Bootstrap admin ---
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
