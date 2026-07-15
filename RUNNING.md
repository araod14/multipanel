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
3. *(For live trading)* add the user's **exchange API key/secret** — verified against the
   exchange, then encrypted at rest and injected into the container; never written to disk.
4. *(Optional)* flip the bot to **LIVE** — see the ladder below.

As that **user** (`/app`):
- **Dashboard** — status, performance, balance.
- **Settings** — pick a strategy and edit pairs, stake, max open trades, stoploss, ROI and
  timeframe. **Saving re-provisions the bot** with the new config.
- **Controls** — start/stop the trading loop, force entry/exit.
- **Trades** — open positions.

Everything a user does is proxied only to **their own** bot.

---

## 2b. Going live with real money (Binance)

**There is no testnet, and that is not an omission.** Freqtrade does not support sandbox
accounts (`docs/faq.md`: *"Does freqtrade support sandbox accounts? No"*) because sandbox
markets have unrealistic order books and liquidity. Binance's testnet exists but Freqtrade
disables it deliberately (`supports_demo_trading: False`, *"a separate market — not a
simulated live market"*). **Dry-run is the rehearsal** — it runs against real prices and
real order books, and it is the only one Freqtrade considers meaningful.

So the ladder has exactly three rungs:

1. **Dry-run** (the default). Validates the strategy against live market data, risking
   nothing. Let it run long enough to see trades open and close.
2. **First live run, deliberately tiny.** Validates the plumbing that dry-run cannot: real
   keys, real permissions, real order placement, real fees. Use `stake_amount = 15`,
   `max_open_trades = 1`, one liquid pair (BTC/USDT). Binance's `MIN_NOTIONAL` is 5 USDT,
   so 15 is comfortably tradable.
3. **Normal live**, once you have seen a real order fill correctly.

### The Binance API key

Create an **HMAC-SHA256** key (an RSA/Ed25519 key cannot be verified automatically) with:

- **Enable Spot & Margin Trading** — on. The key is rejected without it.
- **Enable Withdrawals** — **off**. A trading bot never needs it, and the UI warns if set.
- **IP allowlist** — restrict it to your VPS's public IP.

The key is probed against Binance before being stored: a wrong key is refused immediately
(422) rather than surfacing later as a container that will not boot. If Binance is
unreachable the save returns 503 and offers to store it unverified.

### The guard rails

Live settings are bounded by two independent mechanisms:

- The control plane **refuses** unsafe settings: no `"unlimited"` stake, per-trade stake
  within `CP_LIVE_MIN_STAKE`..`CP_LIVE_MAX_CAPITAL`, and `stake x max_open_trades` never
  above `CP_LIVE_MAX_CAPITAL` (default 25 USDT). It rejects rather than silently clamping.
- The generated config sets Freqtrade's own **`available_capital`**, so the bot cannot
  deploy more than the cap even if the account holds far more.

Raise `CP_LIVE_MAX_CAPITAL` in `backend/.env` when you are ready to trade larger.

> `dry_run_wallet` is ignored in live mode — Binance reports your real balance.

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
