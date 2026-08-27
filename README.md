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
- **Public results page** — `/results` shows every account's results, efficiency,
  strategy, pairs and amounts side by side, with **no login**. Read-only, cached and
  rate limited; turn it off with `CP_PUBLIC_RESULTS_ENABLED=false`.
- **Secure by construction** — exchange keys encrypted at rest; bots on an internal
  network with no public ports; only the TLS-terminated control plane is exposed.

## Dashboard metrics

The user dashboard surfaces Freqtrade's own trade statistics (`GET /profit`, `/performance`,
`/stats`). All amounts are in the bot's **stake currency** — fiat conversion is disabled on
purpose (it makes a blocking CoinGecko call at startup).

| Metric | What it means |
| --- | --- |
| **Closed profit** | Realized profit from trades that have already been closed. |
| **Total profit** | Closed profit **plus** the current unrealized profit of open trades. |
| **Winrate** | Share of closed trades that ended in profit (`winning / closed`). |
| **Profit factor** | Gross profit of winners ÷ gross loss of losers — see below. |
| **Expectancy** | Average profit expected per trade, in stake currency. |
| **Max drawdown** | Largest peak-to-trough drop in equity; a risk measure, lower is better. |

### Profit factor

```
profit factor = Σ profit of winning trades / |Σ loss of losing trades|
```

It answers *"how much do I win for every unit I lose?"* — a value of `3.0` means 3 units
gained per 1 unit lost.

| Value | Reading |
| --- | --- |
| `> 1` | Wins outweigh losses (profitable) |
| `= 1` | Break-even |
| `< 1` | Losses outweigh wins |
| `∞` | **No losing trades yet** (see below) |

Rules of thumb: below `1` the strategy is not viable, `1`–`1.5` is marginal (fees eat the
edge), above `~2` is solid. With few closed trades the number is very noisy — always read
it next to the trade count and winrate.

It is **not** the winrate: a strategy can win only 30% of its trades and still have a great
profit factor if the winners are far larger than the losers.

> **Why it can show `∞`.** Freqtrade computes
> `winning_profit / abs(losing_profit) if losing_profit else float("inf")`
> ([`rpc.py`](https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/rpc/rpc.py)), so a
> bot with **zero losing trades** yields infinity. Pydantic serializes that as `null` in the
> JSON response, so the dashboard renders `∞ / sin pérdidas aún` rather than a blank `—`
> (which is reserved for "no data yet"). It is not an error — it means nothing has lost yet,
> and the value becomes finite as soon as the first losing trade closes.

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
- The public results page is the one deliberate exception to "everything needs a
  session". It is read-only, its payload is an explicit field allowlist
  (`backend/app/schemas/public.py` — no email, container name or credential ever), and
  it queries a fixed set of Freqtrade endpoints rather than proxying a caller-supplied
  path. It does publish per-account P&L and balances to anyone who visits, which is the
  point; `CP_PUBLIC_RESULTS_ENABLED=false` takes it down instantly.

See [`CLAUDE.md`](./CLAUDE.md) for the full developer guide and design invariants.
