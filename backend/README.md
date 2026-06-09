# Freqtrade Control Plane — Backend

Multi-user orchestration layer that sits **on top of** Freqtrade (without modifying
its core). An admin provisions one Freqtrade container per user; each user manages
their own bot through a custom frontend that proxies to that instance's REST API.

See the full design in `../../.claude/plans/quiero-poder-crear-usuarios-splendid-token.md`.

## Layout

```
app/
  config.py          # settings (CP_* env vars / .env)
  database.py        # SQLAlchemy engine, session, Base
  bootstrap.py       # create tables + bootstrap first admin
  main.py            # FastAPI app
  models/            # AdminUser, User, StrategyTemplate, BotInstance,
                     #   ExchangeCredential, AuditLog
  schemas/           # Pydantic request/response models
  security/          # vault (Fernet), passwords (bcrypt), tokens (JWT), deps (RBAC)
  routers/           # auth, admin  (proxy/user routers land in Phase 2)
  services/          # audit  (provisioning/proxy land in Phases 1-2)
```

## Quick start (development)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Generate real secrets:
python -c "import secrets; print('CP_JWT_SECRET=' + secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print('CP_FERNET_KEY=' + Fernet.generate_key().decode())"
# Paste both into .env, set CP_BOOTSTRAP_ADMIN_* too.

uvicorn app.main:app --reload --port 9000
```

Then open `http://localhost:9000/docs`.

### Smoke test the auth flow

```bash
# Log in as the bootstrap admin
curl -s -X POST localhost:9000/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"identifier":"admin@example.com","password":"<bootstrap password>"}'
```

## Build phases

- **Phase 0 (this):** foundations — DB, models, admin auth + RBAC, secret vault.
- **Phase 1:** provisioning — config generator, credential generator, Docker lifecycle (dry-run).
- **Phase 2:** proxy/gateway to per-user instances + user-facing endpoints.
- **Phase 3:** admin React panel.
- **Phase 4:** user React frontend.
- **Phase 5:** real-money hardening (encrypted exchange keys, TLS, network lockdown, rotation).

## Security notes

- Secrets (exchange keys, per-bot api credentials) are **encrypted at rest** with
  Fernet (`CP_FERNET_KEY`, kept out of the DB) and only decrypted in-memory to inject
  as `FREQTRADE__*` env vars into containers. They are never written to disk in plaintext.
- Per-user Freqtrade containers must run on an **internal docker network with no
  published host ports**. Only the control plane is internet-facing, behind TLS.
