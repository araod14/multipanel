# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **multi-user control plane that sits on top of Freqtrade without modifying it**. An
admin provisions **one Freqtrade container per user** (each with its own config, SQLite
trade DB, exchange API keys, and generated REST credentials); each user manages their
own bot through a custom frontend that the control plane proxies to that instance's REST
API. Designed for a small, static set of users (~2-10) on a single VPS.

The Freqtrade source it integrates against lives in a sibling checkout at `../freqtrade`
— read-only reference, never modified. The feature set is complete: provisioning, the
guarded proxy, the admin panel, the user dashboard, and real-money hardening all work.

Backend is `backend/` (FastAPI), the SPA is `frontend/` (React + TS + Vite), deployment
is `deploy/` (host nginx + docker-compose). User-facing docs worth reading:
[`README.md`](./README.md) (feature overview + dashboard metric definitions),
[`RUNNING.md`](./RUNNING.md) (dev + first-use walkthrough),
[`deploy/README.md`](./deploy/README.md) (VPS guide).

## Commands

A `Makefile` at the repo root wraps everything; `make help` lists targets. Docker must be
running for anything involving bots. Python 3.11+ (developed on 3.14), Node 18+.

```bash
make install      # backend venv (backend/.venv) + frontend npm deps
make env          # backend/.env from the example, with generated CP_JWT_SECRET/CP_FERNET_KEY
                  # then set CP_BOOTSTRAP_ADMIN_EMAIL / _PASSWORD by hand
make dev-start    # backend :9000 + frontend :5173 in background (logs in /tmp/cp-*.log)
make dev-stop
make backend      # foreground backend, to watch logs (terminal 1)
make frontend     # foreground Vite dev server (terminal 2)
make clean        # kill dev servers + cp-bot-* containers, drop the dev DB and _test_bots
```

`make backend` / `dev-start` set `CP_BOT_DATA_ROOT=$PWD/backend/_test_bots`,
`CP_BOT_ADDRESS_MODE=docker_ip` and `CP_DEFAULT_EXCHANGE=kraken` — all three matter in
dev (see gotchas). Log in at http://localhost:5173 as the bootstrap admin.

Frontend type-check + production build: `npm --prefix frontend run build` (runs `tsc`).

### Tests

There is no automated test suite. The backend is verified by the `smoke_*.py` scripts in
`backend/`, each of which launches **real** Freqtrade containers:

```bash
cd backend
# Fully offline (no server, no Docker, no network) — the real-money guard rails:
.venv/bin/python smoke_exchange_probe.py   # Binance signature vector, live caps, allowlist

# Self-contained (start their own containers, no server needed):
CP_BOT_DATA_ROOT=$PWD/_test_bots CP_DEFAULT_EXCHANGE=kraken .venv/bin/python smoke_provision.py
CP_BOT_DATA_ROOT=$PWD/_test_bots CP_DEFAULT_EXCHANGE=kraken .venv/bin/python smoke_user_strategy.py

# Need a control plane already running; pass its port as argv[1], run from backend/:
.venv/bin/python smoke_proxy.py 9000       # user -> own bot proxy + authorization checks
.venv/bin/python smoke_hardening.py 9000   # key injection, secret-at-rest, live guard rails
```

`smoke_hardening.py` needs the server started with **`CP_VALIDATE_EXCHANGE_KEYS=false`**:
it stores deliberately fake keys, which a real probe would rightly reject.

The frontend is verified by `npm run build` plus a Playwright walkthrough. If you add
real tests, prefer `ruff` + `pytest` (backend) and Vitest (frontend).

## Architecture

Request flow: **client → control plane (only internet-facing) → per-user Freqtrade
container** on a private docker network (`control-plane-bots`) with **no published host
ports**. The control plane reaches each bot on port 8080 by container name (prod) or
container IP (dev).

In production the control plane serves both the API and the built SPA on a single origin,
listening on `127.0.0.1:9000`; the VPS's **existing host nginx** terminates TLS and
reverse-proxies to it (`deploy/nginx.danelbot.conf`). Caddy is *not* used — the box
already runs nginx for other sites and they would fight over :80/:443. Note that the
`Makefile`, `README.md` and `deploy/README.md` still describe a Caddy setup and a
`deploy/Caddyfile` that does not exist; `deploy/docker-compose.yml` is the truth.

### Backend layers (`backend/app/`)

- **`config.py`** — `Settings` (pydantic-settings, `CP_` prefix / `.env`), cached via
  `get_settings()`. Every tunable flows from here: DB url, JWT/Fernet secrets, freqtrade
  image, bot network, `bot_data_root`, `default_exchange`, `bot_address_mode`.
- **`database.py`** — SQLAlchemy 2.0 engine/session + declarative `Base`; `get_db()` is
  the FastAPI session dependency. **`bootstrap.py`** — `create_all` + first admin.
- **`main.py`** — app factory; routers under `/api`, then the SPA catch-all mounted
  **last** so it never shadows the API (unknown `/api/*` still 404s properly).
- **`models/`** — `AdminUser`, `User` (1:1 → `BotInstance`, 1:1 → `ExchangeCredential`),
  `StrategyTemplate`, `BotInstance`, `ExchangeCredential`, `AuditLog`. `*_enc` columns
  hold Fernet ciphertext, never plaintext.
- **`security/`** — `vault` (Fernet encrypt/decrypt at rest), `passwords` (bcrypt
  directly — **not** passlib, which breaks on bcrypt 4.x), `tokens` (the control plane's
  *own* admin/user JWTs), `deps` (`CurrentAdmin` / `CurrentUser` / `DbSession`).
- **`routers/`** — `auth` (login/refresh for admins and users), `admin` (user CRUD + bot
  lifecycle + exchange keys), `user` (the guarded proxy + self-service settings).
- **`services/`**:
  - `credentials` — CSPRNG generation of a bot's `api_server` username/password/jwt/ws_token.
  - `config_builder` — renders the per-user `config.json` from a non-secret base +
    strategy template. **Secrets are deliberately omitted**, injected via env at launch.
  - `strategy_assets` — the `STRATEGIES` registry of selectable templates (`off`,
    `ema_cross`, `strategy001`–`005`), each emitted as a self-contained strategy file
    into the user's `strategies/` dir. `off` is the default: boots cleanly, never trades.
  - `bot_config` — the allowlist of user-editable Freqtrade params + validation. Stored
    as a JSON blob on `BotInstance.user_config_json`; `effective()` merges over `DEFAULTS`.
  - `runtime` — `BotRuntime`, the Docker SDK wrapper. The only place that talks to Docker.
  - `provisioning` — orchestrates: generate+encrypt creds → write `config.json` + strategy
    to `bot_data_root/<username>/` → build `FREQTRADE__*` env (decrypting in-memory) →
    launch container → keep the `BotInstance` row in sync.
  - `proxy` — logs into each bot with its stored credentials, caches the JWT per instance
    id, forwards calls with a Bearer header, refreshes once on 401. `invalidate()` after
    re-provisioning.
  - `exchange_creds`, `audit` — encrypted key storage; append-only sensitive-action log.

### Frontend (`frontend/src/`)

Single SPA, two route trees behind one app: `/admin/*` (admin role) and `/app/*` (user
role), gated by `ProtectedRoute`. Tokens live in `localStorage` (`api/tokenStore.ts`);
the axios client (`api/client.ts`) attaches the Bearer header and refreshes once on 401.
The user area only ever talks to the guarded proxy (`/api/me/bot/ft/*`) and
`/api/me/bot/config`.

### Key design invariants (do not break)

1. **Never modify the Freqtrade core** (`../freqtrade`). This app only *consumes* the
   unmodified `freqtradeorg/freqtrade` image and its REST API + config/env contract.
2. **Secrets never touch disk in plaintext.** Exchange keys and per-bot API credentials
   are Fernet-encrypted at rest and decrypted only in-memory to inject as `FREQTRADE__*`
   env vars (Freqtrade merges those into config before schema validation — see
   `../freqtrade/freqtrade/configuration/environment_vars.py`). The generated
   `config.json` contains only non-secret fields.
3. **Two separate JWT systems.** `security/tokens.py` issues the control plane's own
   session tokens. Each Freqtrade instance has its *own* JWT secret; `services/proxy.py`
   authenticates to instances with their generated credentials.
4. **Bot containers stay off the public internet** — internal docker network, no
   published ports; only the control plane is exposed.
5. **The proxy is deny-by-default.** `routers/user.py` forwards only the allowlisted
   `(METHOD, path)` pairs in `_ALLOWED_EXACT` / `_ALLOWED_PREFIX`, and always resolves
   the bot from `CurrentUser`, so a user can never address someone else's instance.
   Widen the allowlist deliberately, never by passing paths through.
6. **Live trading is gated at one choke point.** `provision_bot` is the only way a
   container starts, and when `dry_run=false` it refuses unless (a) exchange credentials
   are stored and (b) the stored settings pass `bot_config.validate(..., dry_run=False)`.
   Both refusals raise from the service and become 409s via the handlers in `main.py` —
   never catch them per-route. Real money is bounded twice, on purpose: the control plane
   rejects unsafe settings, *and* `config_builder` emits `available_capital` so Freqtrade
   itself caps total deployable capital regardless of the wallet balance.
7. **Credentials are allowlisted and verified.** `ExchangeCredentialIn` accepts only
   `SUPPORTED_EXCHANGES`, and `exchange_probe` checks the key against the exchange before
   it is stored. A rejection by the exchange is a 422 and is *never* overridable; an
   unreachable exchange is a 503 that `?force=true` may skip. Keep that asymmetry.

## Conventions

- SQLAlchemy 2.0 style (`Mapped` / `mapped_column`). Enum columns use `native_enum=False`.
- Type hints throughout; reST-style docstrings on public functions.
- The quote currency is fixed to USDT (`bot_config.STAKE_CURRENCY`); every pair is
  `BASE/USDT`. Offer more coins by extending `COMMON_BASE_COINS`.

## Gotchas

- **No migrations.** `alembic` is in requirements but unused; startup calls
  `Base.metadata.create_all`, which does **not** alter existing tables. After changing a
  model, `rm backend/control_plane.sqlite` (or `make clean`) so it is recreated.
- **`CP_BOT_ADDRESS_MODE`** is `docker_ip` in dev (the control plane runs on your host
  and resolves container IPs via the Docker SDK) and `dns` in prod (container names on
  the shared network). `make` sets this for you.
- **Exchange reachability.** Freqtrade's REST API only starts *after* markets load, so an
  unreachable exchange means `/ping` never comes up.
- **The Binance HTTP 451 is about the egress IP, not "this machine".** Binance restricts
  API access by **server country** — freqtrade's `docs/exchanges.md` lists Canada,
  Malaysia, Netherlands and the US as blocked, and it also refuses datacenter/VPN ranges,
  so the same host can get 451 and then 200 as an IP rotates. The production VPS
  (Contabo, France) reaches Binance fine. Verify from the host that actually runs the
  bots: `curl -o /dev/null -w '%{http_code}' https://api.binance.com/api/v3/ping`. If a
  sandbox/dev network is blocked, use `CP_DEFAULT_EXCHANGE=kraken` for local paper bots —
  that only picks which public market data they read, and never touches the money path.
- **`fiat_display_currency`** is intentionally disabled in `config_builder`: it makes a
  blocking CoinGecko call at startup (a 120s hang where CoinGecko is unreachable).
- **Docker-out-of-docker paths.** In prod the control plane asks the *host* daemon to
  bind-mount `CP_BOT_DATA_ROOT`, so that path must be mounted into the control plane at
  the **same** path it has on the host (`/srv/control-plane/bots`).
- **Losing `CP_FERNET_KEY` makes stored exchange keys undecryptable.** Back it up.
