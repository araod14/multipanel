"""Phase 1 smoke test: provision a real dry-run Freqtrade container and verify it.

Run from the backend dir with a writable CP_BOT_DATA_ROOT, e.g.:

    CP_BOT_DATA_ROOT=$PWD/_test_bots .venv/bin/python smoke_provision.py

It provisions a bot, waits for its REST API, hits the public /ping, then logs in
with the generated api_server credentials (proving FREQTRADE__* env injection),
and finally tears the container down.
"""

import sys
import time

import httpx

from app.bootstrap import init_database
from app.database import SessionLocal
from app.models.user import User
from app.security.passwords import hash_password
from app.security.vault import decrypt
from app.services import provisioning
from app.services.runtime import BotRuntime

USERNAME = "smoketrader"
NETWORK = "control-plane-bots"


def main() -> int:
    init_database()
    runtime = BotRuntime()

    with SessionLocal() as db:
        # Fresh user each run.
        existing = db.query(User).filter(User.username == USERNAME).one_or_none()
        if existing is not None:
            if existing.bot is not None:
                provisioning.deprovision_bot(db, existing.bot)
            db.delete(existing)
            db.commit()

        user = User(
            username=USERNAME,
            email=f"{USERNAME}@example.com",
            password_hash=hash_password("smoke-pass-123"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"[1/5] Provisioning container for {USERNAME} ...")
        instance = provisioning.provision_bot(db, user, runtime=runtime)
        db.commit()
        db.refresh(instance)
        api_password = decrypt(instance.api_password_enc)
        print(f"      container={instance.container_name} status={instance.status.value}")

    # Resolve the container IP on the bot network (host-side dev access).
    print("[2/5] Waiting for container IP ...")
    ip = None
    for _ in range(30):
        ip = runtime.ip_address(instance.container_name, NETWORK)
        if ip:
            break
        time.sleep(1)
    if not ip:
        print("      FAIL: no IP assigned")
        print(runtime.logs(instance.container_name, tail=40))
        return 1
    base = f"http://{ip}:8080"
    print(f"      ip={ip}")

    print("[3/5] Polling /api/v1/ping (up to 150s; kraken can be slow) ...")
    pinged = False
    for i in range(150):
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
        print(f"      FAIL: ping never succeeded. status={runtime.status(instance.container_name)}")
        print(runtime.logs(instance.container_name, tail=120))
        _cleanup(runtime, instance.container_name)
        return 1

    print("[4/5] Logging in with generated api credentials ...")
    ok = False
    try:
        r = httpx.post(
            f"{base}/api/v1/token/login",
            auth=(instance.api_username, api_password),
            timeout=5,
        )
        if r.status_code == 200 and "access_token" in r.json():
            ok = True
            print("      token/login -> access_token received (env injection works)")
        else:
            print(f"      FAIL: login status={r.status_code} body={r.text[:200]}")
    except httpx.HTTPError as exc:
        print(f"      FAIL: login error {exc}")

    print("[5/5] Tearing down container ...")
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
