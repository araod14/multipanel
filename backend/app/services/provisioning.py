"""Provisioning service: turn a User into a running Freqtrade container.

Responsibilities:
  * generate + encrypt the instance's api_server credentials,
  * render the per-user ``config.json`` and a default strategy on disk,
  * inject secrets as ``FREQTRADE__*`` env vars and launch the container,
  * keep the :class:`BotInstance` bookkeeping row in sync.

Secrets never touch ``config.json``; they exist in plaintext only in the container
environment and transiently in this process's memory.
"""

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.bot_instance import BotInstance, BotStatus
from app.models.exchange_credential import ExchangeCredential
from app.models.user import User
from app.security import vault
from app.services import bot_config, config_builder, strategy_assets
from app.services.credentials import generate_instance_credentials
from app.services.runtime import BotRuntime, ContainerSpec

logger = logging.getLogger("control_plane.provisioning")

CONTAINER_USER_DATA = "/freqtrade/user_data"
CONTAINER_CONFIG = f"{CONTAINER_USER_DATA}/config.json"
CONTAINER_DB_URL = f"sqlite:////{CONTAINER_USER_DATA.strip('/')}/trades.sqlite"
CONTAINER_LOGFILE = f"{CONTAINER_USER_DATA}/logs/freqtrade.log"


class LiveModeWithoutKeys(RuntimeError):
    """Raised when enabling live trading for a user that has no exchange credentials."""


class LiveConfigRejected(RuntimeError):
    """Raised when a bot's stored settings are not safe to run with real money."""


def _container_name(username: str) -> str:
    return f"cp-bot-{username}"


def _host_dir(username: str) -> Path:
    return Path(get_settings().bot_data_root) / username


def provision_bot(
    db: Session,
    user: User,
    *,
    dry_run: bool | None = None,
    runtime: BotRuntime | None = None,
) -> BotInstance:
    """Provision (or re-provision) and start a Freqtrade container for ``user``.

    Idempotent: re-provisioning regenerates the api credentials and config and
    recreates the container so updated exchange keys / mode take effect. Any cached
    proxy JWT for this instance is invalidated.

    :param dry_run: desired trading mode. ``None`` keeps the instance's current mode
        (or ``True`` for a brand-new instance). ``False`` requires exchange credentials.
    """
    from app.services import proxy  # local import avoids an import cycle

    runtime = runtime or BotRuntime()

    existing = user.bot
    desired_dry_run = dry_run if dry_run is not None else (existing.dry_run if existing else True)
    if not desired_dry_run:
        # Single choke point: every live launch passes through here, whatever triggered it
        # (mode switch, config edit, credential rotation, re-provision). Both checks run
        # before anything is written to disk or handed to Docker.
        if user.exchange_credential is None:
            raise LiveModeWithoutKeys("cannot run live (dry_run=false) without exchange credentials")
        stored = bot_config.effective(existing.user_config_json if existing else None)
        try:
            bot_config.validate(stored, dry_run=False)
        except bot_config.ConfigValidationError as exc:
            raise LiveConfigRejected(f"settings are not safe for live trading: {exc}") from exc

    creds = generate_instance_credentials(user.username)
    name = _container_name(user.username)

    instance = existing or BotInstance(user_id=user.id)
    instance.container_name = name
    instance.internal_hostname = name
    instance.dry_run = desired_dry_run
    instance.stake_currency = bot_config.STAKE_CURRENCY
    instance.db_path = CONTAINER_DB_URL
    instance.api_username = creds.api_username
    instance.api_password_enc = vault.encrypt(creds.api_password)
    instance.jwt_secret_enc = vault.encrypt(creds.jwt_secret)
    instance.ws_token_enc = vault.encrypt(creds.ws_token)
    instance.status = BotStatus.provisioned
    if existing is None:
        db.add(instance)
        user.bot = instance

    _render_user_data(user, instance)
    spec = _build_spec(user, instance, creds=creds)

    try:
        runtime.run(spec)
        instance.status = BotStatus.running
    except Exception:  # noqa: BLE001 - record failure, surface to caller
        instance.status = BotStatus.error
        db.flush()
        logger.exception("Failed to launch container for user %s", user.username)
        raise

    db.flush()
    if instance.id is not None:
        proxy.invalidate(instance.id)
    return instance


def start_bot(db: Session, instance: BotInstance, *, runtime: BotRuntime | None = None) -> None:
    """Start the container for an already-provisioned instance."""
    runtime = runtime or BotRuntime()
    runtime.start(instance.container_name)
    instance.status = BotStatus.running
    db.flush()


def stop_bot(db: Session, instance: BotInstance, *, runtime: BotRuntime | None = None) -> None:
    """Stop the container without removing its data."""
    runtime = runtime or BotRuntime()
    runtime.stop(instance.container_name)
    instance.status = BotStatus.stopped
    db.flush()


def deprovision_bot(db: Session, instance: BotInstance, *, runtime: BotRuntime | None = None) -> None:
    """Remove the container (data on disk is left for backup/cleanup elsewhere)."""
    runtime = runtime or BotRuntime()
    runtime.remove(instance.container_name, ignore_missing=True)
    instance.status = BotStatus.stopped
    db.flush()


def _render_user_data(user: User, instance: BotInstance) -> None:
    """Write ``config.json`` and the selected strategy, and ensure dirs exist."""
    host_dir = _host_dir(user.username)
    (host_dir / "strategies").mkdir(parents=True, exist_ok=True)
    (host_dir / "logs").mkdir(parents=True, exist_ok=True)

    user_cfg = bot_config.effective(instance.user_config_json)
    config = config_builder.build_bot_config(
        username=user.username,
        exchange_name=_exchange_name(user),
        dry_run=instance.dry_run,
        user_config=user_cfg,
    )
    (host_dir / "config.json").write_text(json.dumps(config, indent=2))

    spec = strategy_assets.get_spec(user_cfg["strategy"])
    (host_dir / "strategies" / f"{spec.class_name}.py").write_text(spec.source)

    # Freqtrade container runs as a non-root user; make the tree group/other writable
    # so it can write logs and the sqlite db into the bind mount.
    for path in [host_dir, host_dir / "strategies", host_dir / "logs"]:
        path.chmod(0o777)


def _build_spec(user: User, instance: BotInstance, *, creds) -> ContainerSpec:
    settings = get_settings()
    env = _build_env(user, instance, creds)
    user_cfg = bot_config.effective(instance.user_config_json)
    strategy_class = strategy_assets.get_spec(user_cfg["strategy"]).class_name
    command = [
        "trade",
        "--config",
        CONTAINER_CONFIG,
        "--strategy",
        strategy_class,
        "--db-url",
        CONTAINER_DB_URL,
        "--logfile",
        CONTAINER_LOGFILE,
    ]
    return ContainerSpec(
        name=instance.container_name,
        image=settings.freqtrade_image,
        command=command,
        environment=env,
        binds={str(_host_dir(user.username)): CONTAINER_USER_DATA},
        network=settings.bot_network,
    )


def _build_env(user: User, instance: BotInstance, creds) -> dict[str, str]:
    """Assemble the ``FREQTRADE__*`` env, injecting decrypted secrets."""
    env: dict[str, str] = {
        "FREQTRADE__API_SERVER__USERNAME": creds.api_username,
        "FREQTRADE__API_SERVER__PASSWORD": creds.api_password,
        "FREQTRADE__API_SERVER__JWT_SECRET_KEY": creds.jwt_secret,
        "FREQTRADE__API_SERVER__WS_TOKEN": creds.ws_token,
    }
    cred: ExchangeCredential | None = user.exchange_credential
    if cred is not None:
        env["FREQTRADE__EXCHANGE__KEY"] = vault.decrypt(cred.key_enc)
        env["FREQTRADE__EXCHANGE__SECRET"] = vault.decrypt(cred.secret_enc)
        if cred.password_enc:
            env["FREQTRADE__EXCHANGE__PASSWORD"] = vault.decrypt(cred.password_enc)
        if cred.uid_enc:
            env["FREQTRADE__EXCHANGE__UID"] = vault.decrypt(cred.uid_enc)
    else:
        # Dry-run with no real keys.
        env["FREQTRADE__EXCHANGE__KEY"] = ""
        env["FREQTRADE__EXCHANGE__SECRET"] = ""
    return env


def _exchange_name(user: User) -> str:
    cred = user.exchange_credential
    return cred.exchange_name if cred is not None else get_settings().default_exchange
