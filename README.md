# Freqtrade Control Plane

A small multi-user orchestration layer **on top of [Freqtrade](https://www.freqtrade.io)**,
without modifying its core. An admin provisions **one isolated Freqtrade container per
user** (each with its own config, trade database, exchange API keys and generated REST
credentials); each user manages their own bot through a custom web frontend that the
control plane securely proxies to that instance's REST API.

> Built for a small, static set of users on a single VPS. Real exchange keys are
> encrypted at rest and only ever injected into containers as environment variables.

## Features

- **Admin panel** — create/delete users, provision and start/stop each user's bot, set
  their (encrypted) exchange API keys, and switch a bot between dry-run and live trading.
- **Per-user bot, fully isolated** — own container, config, trade database and keys.
- **Self-service settings** — each user picks a strategy and edits a safe set of
  parameters (pairs, stake, max open trades, stoploss, take-profit ROI, timeframe) from
  their own dashboard; saving re-provisions their bot.
- **Secure by construction** — exchange keys encrypted at rest; bots on an internal
  network with no public ports; only the TLS-terminated control plane is exposed.

## Architecture

```
internet --TLS--> control plane (only exposed service)
                       |
        ┌──────────────┼───────────────┐   internal docker network, no published ports
        ▼              ▼               ▼
   freqtrade-userA  freqtrade-userB  freqtrade-userN
   own config/db/keys, reached by container name on :8080
```

- **Backend** (`backend/`) — FastAPI + SQLAlchemy. Auth (admin/user JWT + RBAC), a Fernet
  secret vault, a provisioning service that renders per-user configs and drives bot
  containers via the Docker SDK, and an authenticated reverse proxy to each instance.
- **Frontend** (`frontend/`) — React + TypeScript + Vite single SPA with `/admin/*`
  (admin panel) and `/app/*` (user dashboard) route trees.
- **Deploy** (`deploy/`) — Caddy (automatic TLS) + docker-compose; only the control plane
  is internet-facing.

## Running

A `Makefile` wraps the common tasks (`make help` lists them). Docker must be running.

**Development:**
```bash
make install      # backend venv + frontend deps
make env          # backend/.env with generated secrets (then set CP_BOOTSTRAP_ADMIN_*)
make dev-start    # backend :9000 + frontend :5173 in the background
# open http://localhost:5173 and log in as the bootstrap admin
make dev-stop
```

**Production (VPS, TLS):**
```bash
make pull-freqtrade build up    # caddy + control plane; only caddy is exposed
```

Full instructions and a first-use walkthrough are in **[`RUNNING.md`](./RUNNING.md)**;
production specifics in **[`deploy/README.md`](./deploy/README.md)**.

## Security model

- Exchange API keys and per-bot REST credentials are **Fernet-encrypted at rest**
  (`CP_FERNET_KEY`, kept out of the database) and decrypted only in-memory to inject as
  `FREQTRADE__*` env vars — never written to disk in plaintext.
- Bot containers run on an **internal docker network with no published ports**; only the
  control plane is exposed, behind TLS.
- Live trading (`dry_run=false`) is gated: it requires stored exchange credentials.
- A user can only ever reach **their own** bot instance.

See [`CLAUDE.md`](./CLAUDE.md) for the full developer guide and design invariants.
