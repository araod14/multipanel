# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **multi-user control plane that sits on top of Freqtrade without modifying it**. An
admin provisions **one Freqtrade container per user** (each with its own config, SQLite
trade DB, exchange API keys, and generated REST credentials); each user manages their
own bot through a custom frontend that the control plane proxies to that instance's REST
API. Designed for a small, static set of users (~2-10) on a single VPS.

The Freqtrade source it integrates against lives in a sibling checkout at
`../freqtrade`. The full design and phased build order are in
`~/.claude/plans/quiero-poder-crear-usuarios-splendid-token.md`. **All phases are
implemented and verified** (foundations, provisioning, proxy/gateway, admin React panel,
user React frontend, real-money hardening). Backend lives in `backend/` (FastAPI),
the SPA in `frontend/` (React + TS + Vite), and deployment in `deploy/` (Caddy + compose).

## Setup & commands

Everything lives under `backend/`. Python 3.11+ (developed on 3.14).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then fill in real secrets (see below)
python -c "import secrets; print('CP_JWT_SECRET=' + secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print('CP_FERNET_KEY=' + Fernet.generate_key().decode())"

uvicorn app.main:app --reload --port 9000   # API + Swagger at /docs
```

On startup the app creates tables (`Base.metadata.create_all`) and bootstraps the first
admin from `CP_BOOTSTRAP_ADMIN_*` if no admin exists.

### Provisioning smoke test (launches a real Freqtrade container via Docker)

```bash
cd backend
CP_BOT_DATA_ROOT=$PWD/_test_bots CP_DEFAULT_EXCHANGE=kraken .venv/bin/python smoke_provision.py
```

Provisions a dry-run bot, polls its `/api/v1/ping`, then logs in with the generated
credentials to prove `FREQTRADE__*` env injection works, then tears the container down.

**Environment gotchas (this dev machine / geo-restricted networks):**
- Binance returns HTTP 451 and cannot load markets here — use `CP_DEFAULT_EXCHANGE=kraken`
  for local container tests. Freqtrade's REST API only starts *after* markets load, so an
  unreachable exchange means `/ping` never comes up.
- `fiat_display_currency` is intentionally disabled in `config_builder` because it makes a
  blocking CoinGecko call at startup (120s hang where CoinGecko is unreachable).

### Frontend (React + TS + Vite)

```bash
cd frontend
npm install
npm run dev      # dev server on :5173, proxies /api -> 127.0.0.1:9000
npm run build    # type-check (tsc) + production build into dist/
```

Single SPA with two route trees behind one app: `/admin/*` (admin role) and `/app/*`
(user role), gated by `ProtectedRoute`. Auth tokens live in `localStorage`
(`api/tokenStore.ts`); the axios client (`api/client.ts`) attaches the Bearer header and
refreshes once on 401. The user area only talks to the guarded proxy (`/me/bot/ft/*`).

There is no automated test suite yet. Backend is verified by the `smoke_*.py` scripts
(provisioning, proxy, hardening); the frontend by `npm run build` + a Playwright
walkthrough. If you add tests, prefer `ruff`+`pytest` (backend) and Vitest (frontend).

## Architecture

Request flow: **client → control plane (only internet-facing, TLS) → per-user Freqtrade
container** on a private docker network (`control-plane-bots`) with **no published host
ports**. The control plane reaches each bot by container name on port 8080.

### Layers (`backend/app/`)

- **`config.py`** — `Settings` (pydantic-settings, `CP_` env prefix / `.env`), cached via
  `get_settings()`. All tunables (DB url, JWT/Fernet secrets, freqtrade image, bot network,
  `bot_data_root`, `default_exchange`) flow from here.
- **`database.py`** — SQLAlchemy 2.0 engine/session + declarative `Base`. `get_db()` is the
  FastAPI session dependency.
- **`models/`** — `AdminUser`, `User` (1:1 → `BotInstance`, 1:1 → `ExchangeCredential`),
  `StrategyTemplate`, `BotInstance`, `ExchangeCredential`, `AuditLog`. Secret columns
  (`*_enc`) hold Fernet ciphertext, never plaintext.
- **`security/`** — `vault` (Fernet encrypt/decrypt for secrets at rest), `passwords`
  (bcrypt directly — **not** passlib, which breaks on bcrypt 4.x), `tokens` (the control
  plane's *own* admin/user JWTs, distinct from each bot's JWTs), `deps` (RBAC dependencies
  `CurrentAdmin` / `CurrentUser` / `DbSession`).
- **`routers/`** — `auth` (login/refresh for both admins and users), `admin` (user CRUD +
  bot lifecycle endpoints). User-facing proxy router arrives in Phase 2.
- **`services/`** — the provisioning pipeline:
  - `credentials` — CSPRNG generation of a bot's `api_server` username/password/jwt/ws_token.
  - `config_builder` — renders the per-user `config.json` from a non-secret base + strategy
    template. **Secrets are deliberately omitted** and injected via env at launch.
  - `strategy_assets` — a minimal valid no-op strategy emitted into the user's
    `strategies/` dir so a fresh bot boots cleanly without trading.
  - `runtime` — `BotRuntime`, the Docker SDK wrapper (`ContainerSpec`, network ensure,
    run/start/stop/remove, ip/logs). The only place that talks to Docker.
  - `provisioning` — orchestrates: generate+encrypt creds → write `config.json` + strategy
    to `bot_data_root/<username>/` → build `FREQTRADE__*` env (decrypting secrets in-memory)
    → launch container → keep the `BotInstance` row in sync.
  - `audit` — append-only audit entries for sensitive actions.

### Key design invariants (do not break)

1. **Never modify the Freqtrade core** (`../freqtrade`). This app only *consumes* the
   unmodified `freqtradeorg/freqtrade` image and its REST API + config/env contract.
2. **Secrets never touch disk in plaintext.** Exchange keys and per-bot api credentials are
   Fernet-encrypted at rest and only decrypted in-memory to inject as `FREQTRADE__*` env
   vars (which Freqtrade merges into config before schema validation — see
   `../freqtrade/freqtrade/configuration/environment_vars.py`). The generated `config.json`
   contains only non-secret fields.
3. **Two separate JWT systems.** `security/tokens.py` issues the control plane's own session
   tokens (admin/user). Each Freqtrade instance has its *own* JWT secret; the proxy layer
   (Phase 2) authenticates to instances using their generated credentials.
4. **Bot containers stay off the public internet** — internal docker network, no published
   ports; only the control plane is exposed.

## Conventions

- SQLAlchemy 2.0 style (`Mapped` / `mapped_column`). Enum columns use `native_enum=False`.
- Type hints throughout; reST-style docstrings on public functions.
- `.env`, `.venv/`, `_test_bots/`, and `*.sqlite` are local-only — keep them out of version
  control (no `.gitignore` exists yet; add one before committing).
