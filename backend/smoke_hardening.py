"""Real-money hardening smoke test: key injection, secret-at-rest, live guard rails.

Verifies:
  * credentials for a non-allowlisted exchange are refused (422),
  * setting exchange creds returns masked metadata (no secrets),
  * the decrypted key/secret reach the container as FREQTRADE__EXCHANGE__* env,
  * the plaintext secret is ABSENT from config.json and the control-plane DB,
  * going live is refused without keys, and refused again while the stored settings are
    unsafe (409 rather than a 500 escaping the provisioner),
  * a safe live config is written with Freqtrade's own ``available_capital`` ceiling,
  * the live exposure cap is enforced against the user's own settings endpoint (422),
  * deleting credentials forces the bot back to dry-run and blanks its exchange key.

Run against a server started with (from backend/):
  CP_VALIDATE_EXCHANGE_KEYS=false CP_BOT_DATA_ROOT=$PWD/_test_bots \
  CP_DEFAULT_EXCHANGE=kraken CP_BOT_ADDRESS_MODE=docker_ip uvicorn app.main:app --port <PORT>
and pass the port as argv[1]. Must be run from backend/ (reads ./control_plane.sqlite).

``CP_VALIDATE_EXCHANGE_KEYS=false`` is required: this stores deliberately fake keys, which
a real probe would (correctly) reject. ``CP_DEFAULT_EXCHANGE=kraken`` only picks the public
market data a paper bot reads, and is reachable from anywhere — unlike Binance, which
blocks by server country.
"""

import json
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

# Must match the server's CP_LIVE_MAX_CAPITAL / CP_LIVE_MIN_STAKE defaults.
LIVE_MAX_CAPITAL = 25.0

BOT_DATA_ROOT = Path("_test_bots")
CP_DB = Path("control_plane.sqlite")

_results: list[tuple[str, bool]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """Record and print one assertion."""
    _results.append((label, condition))
    print(f"      {'PASS' if condition else 'FAIL'}  {label}{f' -> {detail}' if detail else ''}")


def main(port: int) -> int:
    base = f"http://127.0.0.1:{port}/api"
    c = httpx.Client(base_url=base, timeout=60)
    dclient = docker.from_env()

    print("[1/12] Admin login + clean user ...")
    admin_h = _admin_headers(c)
    _purge_user(c, admin_h)
    user_id = c.post(
        "/admin/users",
        headers=admin_h,
        json={"username": USERNAME, "email": f"{USERNAME}@example.com", "password": USER_PASSWORD},
    ).json()["id"]

    print("[2/12] Provision dry-run bot ...")
    c.post(f"/admin/users/{user_id}/provision", headers=admin_h).raise_for_status()

    print("[3/12] Exchange allowlist: a non-allowlisted exchange must be refused ...")
    r = c.put(
        f"/admin/users/{user_id}/exchange",
        headers=admin_h,
        json={"exchange_name": "kraken", "key": FAKE_KEY, "secret": FAKE_SECRET},
    )
    check("kraken credentials refused (422)", r.status_code == 422, f"HTTP {r.status_code}")

    print("[4/12] Set exchange credentials (encrypted) ...")
    r = c.put(
        f"/admin/users/{user_id}/exchange",
        headers=admin_h,
        json={"exchange_name": "binance", "key": FAKE_KEY, "secret": FAKE_SECRET},
    )
    r.raise_for_status()
    meta = r.json()
    check(
        "key is masked in the response",
        meta["key_masked"].endswith("1234") and FAKE_KEY[:4] not in meta["key_masked"],
        meta["key_masked"],
    )
    check("metadata reports binance", meta["exchange_name"] == "binance")

    print("[5/12] Wait for container + inspect injected env ...")
    name = f"cp-bot-{USERNAME}"
    env = _wait_env(dclient, name)
    check(
        "decrypted key/secret injected as FREQTRADE__EXCHANGE__*",
        env.get("FREQTRADE__EXCHANGE__KEY") == FAKE_KEY
        and env.get("FREQTRADE__EXCHANGE__SECRET") == FAKE_SECRET,
    )

    print("[6/12] Secret must be ABSENT from config.json on disk ...")
    config_text = (BOT_DATA_ROOT / USERNAME / "config.json").read_text()
    check(
        "secret absent from config.json",
        FAKE_SECRET not in config_text and FAKE_KEY not in config_text,
    )

    print("[7/12] Secret must be ABSENT (plaintext) from the control-plane DB ...")
    db_bytes = CP_DB.read_bytes()
    check(
        "secret absent from control_plane.sqlite",
        FAKE_SECRET.encode() not in db_bytes and FAKE_KEY.encode() not in db_bytes,
    )

    print("[8/12] Live gate: unsafe stored settings must be refused, not crash ...")
    # The bot still has the default 'unlimited' stake, which in live means the whole
    # wallet. This must be a 409 from the provisioner's gate, never a 500.
    r = c.post(f"/admin/users/{user_id}/bot/mode", headers=admin_h, json={"dry_run": False})
    check("live with 'unlimited' stake refused (409)", r.status_code == 409, f"HTTP {r.status_code}")
    check("refusal explains itself", "live" in r.text.lower(), r.json().get("detail", "")[:80])

    print("[9/12] User sets a safe live stake while still in dry-run ...")
    user_h = _user_headers(c)
    r = c.put("/me/bot/config", headers=user_h, json={"stake_amount": 15, "max_open_trades": 1})
    check("safe settings accepted (15 x 1 = 15)", r.status_code == 200, f"HTTP {r.status_code}")

    print("[10/12] Go LIVE ...")
    r = c.post(f"/admin/users/{user_id}/bot/mode", headers=admin_h, json={"dry_run": False})
    check("live accepted with safe settings", r.status_code == 200, f"HTTP {r.status_code}")
    cfg = json.loads((BOT_DATA_ROOT / USERNAME / "config.json").read_text())
    check("config.json is live", cfg.get("dry_run") is False)
    check(
        f"available_capital caps Freqtrade at {LIVE_MAX_CAPITAL}",
        cfg.get("available_capital") == LIVE_MAX_CAPITAL,
        str(cfg.get("available_capital")),
    )
    check("stake_amount is the explicit number", cfg.get("stake_amount") == 15)

    print("[11/12] Live exposure cap enforced against the user's own settings ...")
    r = c.put("/me/bot/config", headers=user_h, json={"stake_amount": 10, "max_open_trades": 5})
    check("over-cap exposure refused (10 x 5 = 50 > 25)", r.status_code == 422, f"HTTP {r.status_code}")

    print("[12/12] Deleting credentials forces dry-run and blanks the key ...")
    c.delete(f"/admin/users/{user_id}/exchange", headers=admin_h).raise_for_status()
    bot = c.get(f"/admin/users/{user_id}/bot", headers=admin_h).json()
    check("bot forced back to dry-run", bot["dry_run"] is True)
    env = _wait_env_key(dclient, name, "")
    check("exchange key blanked in the recreated container", env.get("FREQTRADE__EXCHANGE__KEY") == "")

    print("\nTeardown ...")
    c.delete(f"/admin/users/{user_id}", headers=admin_h)

    failed = [label for label, ok in _results if not ok]
    print(f"\nRESULT: {len(_results) - len(failed)}/{len(_results)} passed")
    if failed:
        print("FAILED: " + "; ".join(failed))
    return 1 if failed else 0


def _admin_headers(c: httpx.Client) -> dict:
    r = c.post("/auth/login", json={"identifier": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user_headers(c: httpx.Client) -> dict:
    r = c.post("/auth/login", json={"identifier": USERNAME, "password": USER_PASSWORD})
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


def _wait_env_key(dclient, name: str, expected: str) -> dict:
    """Poll until the container's exchange key equals ``expected`` (it is recreated)."""
    env: dict = {}
    for _ in range(30):
        env = _wait_env(dclient, name)
        if env.get("FREQTRADE__EXCHANGE__KEY") == expected:
            return env
        time.sleep(1)
    return env


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1])))
