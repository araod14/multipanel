"""End-to-end check: act as a user who picks a strategy and runs the bot dry.

Mirrors the exact path the user endpoint (PUT /me/bot/config) takes:
    bot_config.validate(..., dry_run=...)  ->  provisioning.provision_bot(..., dry_run=True)

Then talks to the bot's own REST API to prove the chosen strategy is loaded and
dry-run is active. Run from backend/ with kraken (Binance is geo-blocked here):

    CP_BOT_DATA_ROOT=$PWD/_test_bots CP_DEFAULT_EXCHANGE=kraken \
        .venv/bin/python smoke_user_strategy.py
"""

import sys
import time

import httpx

from app.bootstrap import init_database
from app.database import SessionLocal
from app.models.user import User
from app.security.passwords import hash_password
from app.security.vault import decrypt
from app.services import bot_config, provisioning, strategy_assets
from app.services.runtime import BotRuntime

USERNAME = "demotrader"
NETWORK = "control-plane-bots"
CHOSEN_STRATEGY = "strategy002"  # the user's pick from the dropdown


def main() -> int:
    spec = strategy_assets.get_spec(CHOSEN_STRATEGY)
    print(f"User picks strategy: {CHOSEN_STRATEGY!r} -> {spec.label}")
    print(f"  {spec.description}\n")

    init_database()
    runtime = BotRuntime()

    with SessionLocal() as db:
        existing = db.query(User).filter(User.username == USERNAME).one_or_none()
        if existing is not None:
            if existing.bot is not None:
                provisioning.deprovision_bot(db, existing.bot)
            db.delete(existing)
            db.commit()

        user = User(
            username=USERNAME,
            email=f"{USERNAME}@example.com",
            password_hash=hash_password("demo-pass-123"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # [1] Provision a fresh dry-run bot (as admin would on user creation).
        print("[1/6] Provisioning dry-run bot ...")
        instance = provisioning.provision_bot(db, user, dry_run=True, runtime=runtime)
        db.commit()
        db.refresh(instance)
        print(f"      container={instance.container_name} dry_run={instance.dry_run}")

        # [2] User saves settings choosing the strategy (same as the PUT endpoint).
        print(f"[2/6] Applying user settings (strategy={CHOSEN_STRATEGY}) ...")
        current = bot_config.effective(instance.user_config_json)
        merged = {**current, "strategy": CHOSEN_STRATEGY}
        instance.user_config_json = bot_config.validate(merged, dry_run=instance.dry_run)
        provisioning.provision_bot(db, user, runtime=runtime)  # re-provision, keeps dry_run
        db.commit()
        db.refresh(instance)
        api_password = decrypt(instance.api_password_enc)
        print(f"      re-provisioned; status={instance.status.value} dry_run={instance.dry_run}")

    # [3] Wait for container IP.
    print("[3/6] Waiting for container IP ...")
    ip = None
    for _ in range(30):
        ip = runtime.ip_address(instance.container_name, NETWORK)
        if ip:
            break
        time.sleep(1)
    if not ip:
        print("      FAIL: no IP assigned")
        print(runtime.logs(instance.container_name, tail=40))
        _cleanup(runtime, instance.container_name)
        return 1
    base = f"http://{ip}:8080"
    print(f"      ip={ip}")

    # [4] Poll until the REST API is up (kraken market load can be slow).
    print("[4/6] Polling /api/v1/ping (up to 180s) ...")
    pinged = False
    for i in range(180):
        try:
            r = httpx.get(f"{base}/api/v1/ping", timeout=3)
            if r.status_code == 200:
                pinged = True
                print(f"      ping -> {r.json()} (after ~{i}s)")
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    if not pinged:
        print(f"      FAIL: ping never came up. status={runtime.status(instance.container_name)}")
        print(runtime.logs(instance.container_name, tail=120))
        _cleanup(runtime, instance.container_name)
        return 1

    # [5] Log in and read the bot's live config.
    print("[5/6] Logging in and reading show_config ...")
    ok = False
    try:
        login = httpx.post(
            f"{base}/api/v1/token/login",
            auth=(instance.api_username, api_password),
            timeout=5,
        )
        token = login.json().get("access_token")
        cfg = httpx.get(
            f"{base}/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        ).json()
        running_strategy = cfg.get("strategy")
        dry = cfg.get("dry_run")
        state = cfg.get("state")
        print(f"      strategy={running_strategy} dry_run={dry} state={state}")
        print(f"      timeframe={cfg.get('timeframe')} stake_currency={cfg.get('stake_currency')}")
        ok = running_strategy == spec.class_name and dry is True
    except (httpx.HTTPError, ValueError) as exc:
        print(f"      FAIL: {exc}")

    # [6] Start trading (dry) and confirm the bot accepts the running state.
    if ok:
        print("[6/6] Starting the bot in dry-run ...")
        try:
            start = httpx.post(
                f"{base}/api/v1/start",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            ).json()
            print(f"      start -> {start}")
            time.sleep(3)
            status = httpx.get(
                f"{base}/api/v1/show_config",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            ).json()
            print(f"      state now={status.get('state')} (dry_run={status.get('dry_run')})")
            ok = status.get("dry_run") is True
        except (httpx.HTTPError, ValueError) as exc:
            print(f"      FAIL: {exc}")
            ok = False

    print("\nTearing down container ...")
    _cleanup(runtime, instance.container_name)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def _cleanup(runtime: BotRuntime, name: str) -> None:
    try:
        runtime.remove(name, ignore_missing=True)
    except Exception as exc:  # noqa: BLE001
        print(f"      cleanup warning: {exc}")


if __name__ == "__main__":
    sys.exit(main())
