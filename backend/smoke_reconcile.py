"""Smoke test for trading-state persistence and the reconciler.

Reproduces the real incident — a host reboot restarts every bot container, and because
Freqtrade boots with ``initial_state: stopped`` the trading loop silently stays idle —
and proves the reconciler now heals it:

  provision -> user starts trading -> restart the container (the reboot) ->
  bot comes back stopped -> reconciler resumes it -> user stops trading ->
  restart again -> reconciler leaves it alone -> teardown

Run against a server started with:
  CP_BOT_DATA_ROOT=$PWD/_test_bots CP_DEFAULT_EXCHANGE=kraken \
  CP_BOT_ADDRESS_MODE=docker_ip CP_TRADING_RECONCILE_INTERVAL=30 \
  uvicorn app.main:app --port <PORT>
and pass the port as argv[1].

The interval matters: it must comfortably exceed how long a restarted bot takes to
answer its REST API (~15s), or the reconciler resumes the bot before this test can
observe it idle — and a test that never sees the broken state cannot prove the fix.
"""

import subprocess
import sys
import time

import httpx

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "devpassword123"
USERNAME = "reconciler"
USER_PASSWORD = "reconcile-pass-123"

# Generous: the reconciler only acts once the bot's REST API is answering again, and
# Freqtrade must reload markets before that happens.
RESUME_TIMEOUT = 180


def main(port: int) -> int:
    base = f"http://127.0.0.1:{port}/api"
    c = httpx.Client(base_url=base, timeout=30)

    print("[1/7] Admin login + provision a bot ...")
    r = c.post("/auth/login", json={"identifier": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    admin_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
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
    container = r.json()["container_name"]

    r = c.post("/auth/login", json={"identifier": USERNAME, "password": USER_PASSWORD})
    r.raise_for_status()
    user_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    if not _wait_for_ping(c, user_h):
        print("      FAIL: bot never came up")
        _teardown(c, admin_h, user_id)
        return 1

    print("[2/7] A fresh bot is stopped and not flagged as trading ...")
    ok_initial = _bot_state(c, user_h) == "stopped" and _flag(c, user_h) is False
    print(f"      state={_bot_state(c, user_h)} trading_enabled={_flag(c, user_h)}")

    print("[3/7] User starts trading -> intent persisted ...")
    rs = c.post("/me/bot/ft/start", headers=user_h)
    time.sleep(3)
    ok_started = rs.status_code == 200 and _flag(c, user_h) is True
    print(f"      HTTP {rs.status_code} state={_bot_state(c, user_h)} trading_enabled={_flag(c, user_h)}")

    print(f"[4/7] Restart {container} — this is the host reboot ...")
    subprocess.run(["docker", "restart", container], check=True, capture_output=True)
    if not _wait_for_ping(c, user_h):
        print("      FAIL: bot never came back")
        _teardown(c, admin_h, user_id)
        return 1
    # The bug being fixed: the bot must come back idle. Observing that is the whole
    # point — resuming a bot that was never stopped would prove nothing.
    came_back = _bot_state(c, user_h)
    observed_idle = came_back == "stopped"
    print(f"      came back as state={came_back} (Freqtrade's initial_state)")
    if not observed_idle:
        print("      FAIL: never saw the bot idle — raise CP_TRADING_RECONCILE_INTERVAL")

    print("[5/7] Reconciler resumes it ...")
    resumed, waited = _wait_for_state(c, user_h, "running", RESUME_TIMEOUT)
    print(f"      state={_bot_state(c, user_h)} after ~{waited}s -> {resumed}")

    print("[6/7] User stops trading -> intent cleared ...")
    rs = c.post("/me/bot/ft/stop", headers=user_h)
    time.sleep(3)
    ok_stopped = rs.status_code == 200 and _flag(c, user_h) is False
    print(f"      HTTP {rs.status_code} state={_bot_state(c, user_h)} trading_enabled={_flag(c, user_h)}")

    print("[7/7] After another restart the reconciler leaves it stopped ...")
    subprocess.run(["docker", "restart", container], check=True, capture_output=True)
    if not _wait_for_ping(c, user_h):
        print("      FAIL: bot never came back")
        _teardown(c, admin_h, user_id)
        return 1
    # Watch across several reconciler passes: it must never start a bot nobody asked for.
    stayed = True
    for _ in range(6):
        time.sleep(5)
        if _bot_state(c, user_h) == "running":
            stayed = False
            break
    print(f"      stayed stopped across ~30s of passes -> {stayed}")

    _teardown(c, admin_h, user_id)

    passed = ok_initial and ok_started and observed_idle and resumed and ok_stopped and stayed
    print("\nRESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


def _bot_state(c: httpx.Client, user_h: dict) -> str | None:
    r = c.get("/me/bot/ft/show_config", headers=user_h)
    return r.json().get("state") if r.status_code == 200 else None


def _flag(c: httpx.Client, user_h: dict) -> bool | None:
    r = c.get("/me/bot", headers=user_h)
    return r.json().get("trading_enabled") if r.status_code == 200 else None


def _wait_for_state(c: httpx.Client, user_h: dict, want: str, timeout: int) -> tuple[bool, int]:
    for i in range(timeout):
        if _bot_state(c, user_h) == want:
            return True, i
        time.sleep(1)
    return False, timeout


def _wait_for_ping(c: httpx.Client, user_h: dict) -> bool:
    for _ in range(180):
        r = c.get("/me/bot/ft/ping", headers=user_h)
        if r.status_code == 200 and r.json().get("status") == "pong":
            return True
        time.sleep(1)
    return False


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
