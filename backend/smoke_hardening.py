"""Phase 5 smoke test: exchange-key injection, secret-at-rest, dry-run gate.

Verifies:
  * setting exchange creds returns masked metadata (no secrets),
  * the decrypted key/secret reach the container as FREQTRADE__EXCHANGE__* env,
  * the plaintext secret is ABSENT from config.json and the control-plane DB,
  * enabling live mode (dry_run=false) without exchange keys is refused (409).

Run against a server started with (from backend/):
  CP_BOT_DATA_ROOT=$PWD/_test_bots CP_DEFAULT_EXCHANGE=kraken \
  CP_BOT_ADDRESS_MODE=docker_ip uvicorn app.main:app --port <PORT>
and pass the port as argv[1]. Must be run from backend/ (reads ./control_plane.sqlite).
"""

import sys
import time
from pathlib import Path

import docker
import httpx

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "devpassword123"
USERNAME = "hardtrader"
USER_PASSWORD = "hard-pass-123"

FAKE_KEY = "FAKEKEY_AAA_1234"
FAKE_SECRET = "FAKE_SECRET_ZZZ_9988776655"

BOT_DATA_ROOT = Path("_test_bots")
CP_DB = Path("control_plane.sqlite")


def main(port: int) -> int:
    base = f"http://127.0.0.1:{port}/api"
    c = httpx.Client(base_url=base, timeout=30)
    dclient = docker.from_env()

    print("[1/8] Admin login + clean user ...")
    admin_h = _admin_headers(c)
    _purge_user(c, admin_h)
    user_id = c.post(
        "/admin/users",
        headers=admin_h,
        json={"username": USERNAME, "email": f"{USERNAME}@example.com", "password": USER_PASSWORD},
    ).json()["id"]

    print("[2/8] Provision dry-run bot ...")
    c.post(f"/admin/users/{user_id}/provision", headers=admin_h).raise_for_status()

    print("[3/8] Set exchange credentials (encrypted) ...")
    r = c.put(
        f"/admin/users/{user_id}/exchange",
        headers=admin_h,
        json={"exchange_name": "kraken", "key": FAKE_KEY, "secret": FAKE_SECRET},
    )
    r.raise_for_status()
    meta = r.json()
    ok_mask = meta["key_masked"].endswith("1234") and FAKE_KEY[:4] not in meta["key_masked"]
    ok_meta = meta["exchange_name"] == "kraken" and meta["has_password"] is False
    print(f"      metadata={meta} masked_ok={ok_mask}")

    print("[4/8] Wait for container + inspect injected env ...")
    name = f"cp-bot-{USERNAME}"
    env = _wait_env(dclient, name)
    ok_env = env.get("FREQTRADE__EXCHANGE__KEY") == FAKE_KEY and (
        env.get("FREQTRADE__EXCHANGE__SECRET") == FAKE_SECRET
    )
    print(f"      env has injected key/secret: {ok_env}")

    print("[5/8] Secret must be ABSENT from config.json on disk ...")
    config_text = (BOT_DATA_ROOT / USERNAME / "config.json").read_text()
    ok_not_in_config = FAKE_SECRET not in config_text and FAKE_KEY not in config_text
    print(f"      secret absent from config.json: {ok_not_in_config}")

    print("[6/8] Secret must be ABSENT (plaintext) from control-plane DB ...")
    db_bytes = CP_DB.read_bytes()
    ok_not_in_db = FAKE_SECRET.encode() not in db_bytes and FAKE_KEY.encode() not in db_bytes
    print(f"      secret absent from control_plane.sqlite: {ok_not_in_db}")

    print("[7/8] dry-run gate: live mode without keys must be refused ...")
    c.delete(f"/admin/users/{user_id}/exchange", headers=admin_h).raise_for_status()
    r_live = c.post(f"/admin/users/{user_id}/bot/mode", headers=admin_h, json={"dry_run": False})
    ok_gate = r_live.status_code == 409
    print(f"      live-without-keys -> HTTP {r_live.status_code} (expect 409)")

    print("[8/8] Teardown ...")
    c.delete(f"/admin/users/{user_id}", headers=admin_h)

    passed = ok_mask and ok_meta and ok_env and ok_not_in_config and ok_not_in_db and ok_gate
    print("\nRESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


def _admin_headers(c: httpx.Client) -> dict:
    r = c.post("/auth/login", json={"identifier": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _purge_user(c: httpx.Client, admin_h: dict) -> None:
    for u in c.get("/admin/users", headers=admin_h).json():
        if u["username"] == USERNAME:
            c.delete(f"/admin/users/{u['id']}", headers=admin_h)


def _wait_env(dclient, name: str) -> dict:
    for _ in range(30):
        try:
            container = dclient.containers.get(name)
            raw = container.attrs["Config"]["Env"]
            return dict(e.split("=", 1) for e in raw if "=" in e)
        except docker.errors.NotFound:
            time.sleep(1)
    return {}


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1])))
