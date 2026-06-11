# Running the Control Plane

Two ways to run it: **development** (fast, hot-reload, on your machine) and
**production** (Docker Compose + TLS on a VPS). Both launch real Freqtrade containers,
so **Docker must be installed and running** either way.

> Quick reference of every shortcut: `make help`.

---

## 1. Development (local)

### Prerequisites
- Python 3.11+ and Node 18+.
- Docker running (the control plane starts one Freqtrade container per user).

### One-time setup
```bash
make install      # backend venv + frontend npm deps
make env          # creates backend/.env with generated CP_JWT_SECRET / CP_FERNET_KEY
```
Then edit `backend/.env` and set `CP_BOOTSTRAP_ADMIN_EMAIL` / `CP_BOOTSTRAP_ADMIN_PASSWORD`
(your first admin login). Optionally set `CP_DEFAULT_EXCHANGE` (see the note below).

### Start it
```bash
make dev-start    # backend on :9000 and frontend on :5173, in the background
# ...work...
make dev-stop     # stop both
```
Or run them in two terminals to watch logs live:
```bash
make backend      # terminal 1
make frontend     # terminal 2
```

Open **http://localhost:5173** and log in as the bootstrap admin.

> In dev, `make` sets `CP_BOT_ADDRESS_MODE=docker_ip` so the control plane (running on
> your host) can reach bot containers by IP. In production this is `dns` (containers reach
> each other by name on the internal network).

### Exchange note (important in some regions)
Freqtrade's REST API only starts **after** it loads markets from the exchange, so the
exchange must be reachable. If Binance returns HTTP 451 (geo-restricted) where you are,
use a reachable one:
```bash
make dev-start EXCHANGE=kraken      # default in dev is already kraken
```

---

## 2. First-use walkthrough (in the UI)

As **admin** (`/admin`):
1. **Create a user** (username, email, password).
2. Open the user → **Provision bot**. A `cp-bot-<username>` container starts in dry-run.
3. *(For live trading)* add the user's **exchange API key/secret** — encrypted at rest and
   injected into the container; never written to disk.
4. *(Optional)* flip the bot to **LIVE** (requires stored exchange credentials).

As that **user** (`/app`):
- **Dashboard** — status, performance, balance.
- **Settings** — pick a strategy and edit pairs, stake, max open trades, stoploss, ROI and
  timeframe. **Saving re-provisions the bot** with the new config.
- **Controls** — start/stop the trading loop, force entry/exit.
- **Trades** — open positions.

Everything a user does is proxied only to **their own** bot.

---

## 3. Production (VPS, Docker Compose + TLS)

See **[`deploy/README.md`](./deploy/README.md)** for the full guide. In short:
```bash
# edit deploy/Caddyfile (your domain) and backend/.env (real secrets), then:
make pull-freqtrade   # pre-pull the Freqtrade image
make build            # build the control-plane image
make up               # start caddy + control plane (only caddy is exposed, with TLS)
make logs             # follow logs
make down             # stop
```
You upload **only this repo** — Freqtrade is pulled automatically as the official image.

---

## 4. Operations

```bash
make backup BOT_DATA_ROOT=/srv/control-plane/bots   # tar each user's data + trades.sqlite
make ps            # compose stack status
docker logs -f cp-bot-<username>                    # a specific user's bot logs
make clean         # stop dev servers + bot containers, remove local dev state
```

---

## 5. Dev gotchas

- **Schema changes:** there are no Alembic migrations yet; the app uses
  `Base.metadata.create_all`, which does **not** alter existing tables. After changing a
  model, delete the dev DB so it is recreated: `rm backend/control_plane.sqlite` (or
  `make clean`).
- **`fiat_display_currency`** is disabled by default (it makes a blocking CoinGecko call at
  startup); re-enable it in `backend/app/services/config_builder.py` only where CoinGecko
  is reachable.
- **Secrets:** `backend/.env` and `CP_FERNET_KEY` are never committed. Losing the Fernet
  key makes stored exchange keys undecryptable — back it up.
