# Freqtrade Control Plane

A small multi-user orchestration layer **on top of [Freqtrade](https://www.freqtrade.io)**,
without modifying its core. An admin provisions **one isolated Freqtrade container per
user** (each with its own config, trade database, exchange API keys and generated REST
credentials); each user manages their own bot through a custom web frontend that the
control plane securely proxies to that instance's REST API.

> Built for a small, static set of users on a single VPS. Real exchange keys are
> encrypted at rest and only ever injected into containers as environment variables.

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

## Quick start (development)

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in CP_JWT_SECRET, CP_FERNET_KEY, CP_BOOTSTRAP_ADMIN_*
uvicorn app.main:app --reload --port 9000
```

Frontend:

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 (proxies /api -> :9000)
```

## Production

```bash
cd deploy
# set your domain in Caddyfile and real secrets in ../backend/.env
docker compose up -d --build
```

## Security model

- Exchange API keys and per-bot REST credentials are **Fernet-encrypted at rest**
  (`CP_FERNET_KEY`, kept out of the database) and decrypted only in-memory to inject as
  `FREQTRADE__*` env vars — never written to disk in plaintext.
- Bot containers run on an **internal docker network with no published ports**; only the
  control plane is exposed, behind TLS.
- Live trading (`dry_run=false`) is gated: it requires stored exchange credentials.
- A user can only ever reach **their own** bot instance.

See [`CLAUDE.md`](./CLAUDE.md) for the full developer guide and design invariants.
