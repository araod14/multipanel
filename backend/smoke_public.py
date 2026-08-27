"""Smoke test for the public (unauthenticated) results page.

Drives the running control-plane HTTP API end-to-end:
  admin login -> create user -> provision bot -> wait for the bot's REST API ->
  GET /api/public/results with NO Authorization header ->
  field-allowlist check (no secrets leak) -> cache check -> bot-down check ->
  rate-limit check -> teardown.

Run against a server started with:
  CP_BOT_DATA_ROOT=$PWD/_test_bots CP_DEFAULT_EXCHANGE=kraken \
  CP_BOT_ADDRESS_MODE=docker_ip uvicorn app.main:app --port <PORT>
and pass the port as argv[1].
"""

import sys
import time

import httpx

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "devpassword123"
USERNAME = "publictrader"
USER_PASSWORD = "public-pass-123"

# Substrings that must never appear anywhere in the public payload. The endpoint is
# reachable by anyone, so a leak here is a real incident, not a cosmetic bug.
FORBIDDEN = (
    "@",  # any email address
    "cp-bot-",  # container names / internal hostnames
    "_enc",
    "api_password",
    "api_username",
    "jwt_secret",
    "ws_token",
    "password_hash",
    "secret",
)


def main(port: int) -> int:
    base = f"http://127.0.0.1:{port}/api"
    c = httpx.Client(base_url=base, timeout=30)

    print("[1/8] Admin login ...")
    r = c.post("/auth/login", json={"identifier": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    admin_h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    print("[2/8] Create user (clean slate) + provision bot ...")
    _purge_user(c, admin_h)
    r = c.post(
        "/admin/users",
        headers=admin_h,
        json={"username": USERNAME, "email": f"{USERNAME}@example.com", "password": USER_PASSWORD},
    )
    r.raise_for_status()
    user_id = r.json()["id"]
    r = c.post(f"/admin/users/{user_id}/provision", headers=admin_h)
    r.raise_for_status()

    print("[3/8] Wait for the bot's REST API (up to 150s) ...")
    r = c.post("/auth/login", json={"identifier": USERNAME, "password": USER_PASSWORD})
    r.raise_for_status()
    user_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    if not _wait_for_ping(c, user_h):
        print("      FAIL: bot never came up")
        _teardown(c, admin_h, user_id)
        return 1

    print("[4/8] GET /public/results with NO Authorization header ...")
    r = c.get("/public/results")
    print(f"      HTTP {r.status_code}")
    ok_anon = r.status_code == 200
    if not ok_anon:
        print(f"      FAIL: {r.text[:300]}")
        _teardown(c, admin_h, user_id)
        return 1
    payload = r.json()
    account = _find(payload, USERNAME)
    print(
        f"      accounts={len(payload['accounts'])} "
        f"totals.reachable={payload['totals']['reachable']}"
    )

    print("[5/8] Field allowlist (nothing sensitive in the payload) ...")
    blob = r.text.lower()
    leaked = [needle for needle in FORBIDDEN if needle in blob]
    ok_no_leak = not leaked
    print("      leaked:", leaked or "none")

    print("[6/8] The account reports strategy, pairs and amounts ...")
    ok_shape = account is not None and _has_shape(account)
    if account is not None:
        print(
            f"      strategy={account['strategy_label']!r} "
            f"pairs={account['pairs']} stake={account['stake_amount']} "
            f"reachable={account['reachable']} state={account['container_state']}"
        )

    print("[7/8] Snapshot is cached (two calls share generated_at) ...")
    first = c.get("/public/results").json()["generated_at"]
    second = c.get("/public/results").json()["generated_at"]
    ok_cache = first == second
    print(f"      {first} == {second} -> {ok_cache}")

    print("[8/8] A stopped bot still lists its configuration ...")
    c.post(f"/admin/users/{user_id}/bot/stop", headers=admin_h).raise_for_status()
    ok_down = _wait_for_unreachable(c, USERNAME)
    print(f"      account still listed with config, reachable=false -> {ok_down}")

    print("[+] Rate limit answers 429 under a burst ...")
    codes = {c.get("/public/results").status_code for _ in range(45)}
    ok_rate = 429 in codes
    print(f"      status codes seen: {sorted(codes)}")

    _teardown(c, admin_h, user_id)

    passed = ok_anon and ok_no_leak and ok_shape and ok_cache and ok_down and ok_rate
    print("\nRESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


def _wait_for_ping(c: httpx.Client, user_h: dict) -> bool:
    for i in range(150):
        r = c.get("/me/bot/ft/ping", headers=user_h)
        if r.status_code == 200 and r.json().get("status") == "pong":
            print(f"      bot answered ping after ~{i}s")
            return True
        time.sleep(1)
    return False


def _wait_for_unreachable(c: httpx.Client, username: str) -> bool:
    """Poll past the cache TTL until the stopped bot is reported unreachable."""
    for _ in range(20):
        time.sleep(3)
        account = _find(c.get("/public/results").json(), username)
        if account is None:
            return False
        if not account["reachable"]:
            # Config must survive the bot going away — that is the whole point.
            return _has_shape(account)
    return False


def _has_shape(account: dict) -> bool:
    return (
        bool(account.get("strategy_label"))
        and isinstance(account.get("pairs"), list)
        and account.get("stake_amount") is not None
        and account.get("max_open_trades") is not None
    )


def _find(payload: dict, username: str) -> dict | None:
    return next((a for a in payload["accounts"] if a["username"] == username), None)


def _purge_user(c: httpx.Client, admin_h: dict) -> None:
    r = c.get("/admin/users", headers=admin_h)
    r.raise_for_status()
    for u in r.json():
        if u["username"] == USERNAME:
            c.delete(f"/admin/users/{u['id']}", headers=admin_h)


def _teardown(c: httpx.Client, admin_h: dict, user_id: int) -> None:
    print("      tearing down (delete user -> deprovision container) ...")
    c.delete(f"/admin/users/{user_id}", headers=admin_h)


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1])))
