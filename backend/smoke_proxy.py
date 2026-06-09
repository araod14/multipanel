"""Phase 2 smoke test: the authenticated proxy from a user to their own bot.

Drives the running control-plane HTTP API end-to-end:
  admin login -> create user -> provision bot -> user login ->
  user calls /api/me/bot/ft/{ping,status,profit} (proxied to the bot) ->
  authorization checks -> teardown.

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
USERNAME = "proxytrader"
USER_PASSWORD = "proxy-pass-123"


def main(port: int) -> int:
    base = f"http://127.0.0.1:{port}/api"
    c = httpx.Client(base_url=base, timeout=30)

    print("[1/7] Admin login ...")
    r = c.post("/auth/login", json={"identifier": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    admin_h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    print("[2/7] Create user (clean slate) ...")
    _purge_user(c, admin_h)
    r = c.post(
        "/admin/users",
        headers=admin_h,
        json={"username": USERNAME, "email": f"{USERNAME}@example.com", "password": USER_PASSWORD},
    )
    r.raise_for_status()
    user_id = r.json()["id"]

    print("[3/7] Provision bot (launches container) ...")
    r = c.post(f"/admin/users/{user_id}/provision", headers=admin_h)
    r.raise_for_status()
    print(f"      bot status={r.json()['status']}")

    print("[4/7] User login (gets a control-plane token, NOT bot creds) ...")
    r = c.post("/auth/login", json={"identifier": USERNAME, "password": USER_PASSWORD})
    r.raise_for_status()
    user_h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    print("[5/7] Proxy /ping through the control plane (up to 150s) ...")
    ok_ping = False
    for i in range(150):
        rp = c.get("/me/bot/ft/ping", headers=user_h)
        if rp.status_code == 200 and rp.json().get("status") == "pong":
            ok_ping = True
            print(f"      proxied ping -> {rp.json()} (after ~{i}s)")
            break
        time.sleep(1)
    if not ok_ping:
        print("      FAIL: proxied ping never succeeded")
        _teardown(c, admin_h, user_id)
        return 1

    print("[6/7] Proxy authenticated endpoints (status, profit) ...")
    rs = c.get("/me/bot/ft/status", headers=user_h)
    rpf = c.get("/me/bot/ft/profit", headers=user_h)
    print(f"      status -> HTTP {rs.status_code}; profit -> HTTP {rpf.status_code}")
    ok_auth_calls = rs.status_code == 200 and rpf.status_code == 200

    print("[7/7] Authorization checks ...")
    # Disallowed path must be 403.
    r_forbidden = c.get("/me/bot/ft/show_logs_secret", headers=user_h)
    # No token must be 401/403.
    r_anon = c.get("/me/bot/ft/status")
    # Admin (wrong role) must not use a user endpoint.
    r_wrongrole = c.get("/me/bot/ft/status", headers=admin_h)
    print(
        f"      disallowed-path={r_forbidden.status_code} "
        f"anon={r_anon.status_code} admin-on-user-route={r_wrongrole.status_code}"
    )
    ok_authz = (
        r_forbidden.status_code == 403
        and r_anon.status_code in (401, 403)
        and r_wrongrole.status_code == 403
    )

    _teardown(c, admin_h, user_id)

    passed = ok_ping and ok_auth_calls and ok_authz
    print("\nRESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


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
