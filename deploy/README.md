# Deployment guide

How to run the Freqtrade Control Plane on a single VPS. You deploy **only this repo** —
Freqtrade itself is **not** uploaded or run by you: the control plane launches one
official `freqtradeorg/freqtrade` container per user, and Docker pulls that image
automatically.

## What runs on the VPS

```
internet ──TLS:443──> caddy ──> control-plane (FastAPI + React)
                                     │  talks to the host Docker daemon
                                     ▼
                       cp-bot-<userA>  cp-bot-<userB>  cp-bot-<userN>
                       (freqtradeorg/freqtrade, internal network, NO published ports)
```

Three things run, all as containers: **Caddy** (TLS, the only exposed service), your
**control plane**, and **N Freqtrade bot containers** (one per user, created on demand).

## Prerequisites

- A VPS with a public IP and a domain name pointing to it (for automatic TLS).
- **Docker Engine** + the **Compose plugin** (`docker compose version` should work).
- Ports **80** and **443** open (Caddy needs 80 for the ACME challenge, 443 for HTTPS).

## Step by step

### 1. Get the code

```bash
git clone https://github.com/<your-account>/<your-repo>.git
cd <your-repo>
```

### 2. Create the bot data directory

This is where each user's `config.json`, strategy, logs and `trades.sqlite` live. It must
match `CP_BOT_DATA_ROOT` and is bind-mounted at the **same path** into the control plane.

```bash
sudo mkdir -p /srv/control-plane/bots
sudo chown "$USER" /srv/control-plane/bots
```

### 3. Configure secrets

```bash
cp backend/.env.example backend/.env
# Generate strong values:
python3 -c "import secrets; print('CP_JWT_SECRET='+secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet; print('CP_FERNET_KEY='+Fernet.generate_key().decode())"
```

Edit `backend/.env` and set at minimum:

| Variable | Value |
| --- | --- |
| `CP_JWT_SECRET` | the generated token |
| `CP_FERNET_KEY` | the generated Fernet key (**back this up** — losing it makes stored exchange keys undecryptable) |
| `CP_BOOTSTRAP_ADMIN_EMAIL` / `CP_BOOTSTRAP_ADMIN_PASSWORD` | first admin login |
| `CP_PUBLIC_ORIGIN` | `https://your-domain` |
| `CP_DEFAULT_EXCHANGE` | `binance`, `kraken`, … (whatever is reachable from the VPS) |

> The compose file already overrides `CP_DATABASE_URL`, `CP_BOT_DATA_ROOT`,
> `CP_BOT_NETWORK` and `CP_BOT_ADDRESS_MODE` for the container environment, so you don't
> set those in `.env`.

### 4. Set your domain

Edit [`Caddyfile`](./Caddyfile) and replace `control-plane.example.com` with your domain.
Caddy obtains and renews the TLS certificate automatically.

### 5. (Recommended) pre-pull the Freqtrade image

Avoids a slow first provisioning request:

```bash
docker pull freqtradeorg/freqtrade:stable
```

### 6. Launch

```bash
cd deploy
docker compose up -d --build
```

Check it's up:

```bash
docker compose ps
docker compose logs -f control-plane
```

Open `https://your-domain`, log in as the bootstrap admin, and **change that password**.

## Using it

1. **Create a user** in the admin panel.
2. **Provision** their bot — this pulls/launches a `cp-bot-<username>` container in dry-run.
3. **Add exchange credentials** for the user (encrypted at rest, injected as env).
4. **Go LIVE** when ready (requires stored credentials; otherwise refused).

Each user logs in at the same URL and lands on their own dashboard (`/app`), which proxies
to *their* bot only.

## How it talks to Docker (important)

The control plane manages **sibling** containers via the host Docker daemon:

- `docker-compose.yml` mounts `/var/run/docker.sock` into the control plane.
- `/srv/control-plane/bots` is mounted at the **same path** in the control plane, because
  the bind-mount paths it requests are resolved by the **host** daemon.
- The `control-plane-bots` network is created with a fixed name (no compose prefix) so the
  Docker SDK attaches bot containers to the exact same network.

> Mounting the Docker socket grants control over the host's Docker. Keep the VPS locked
> down and the control plane behind TLS + auth (as configured).

## Operations

**Logs of a specific bot:**
```bash
docker logs -f cp-bot-<username>
```

**Backups** (config + `trades.sqlite` per user):
```bash
CP_BOT_DATA_ROOT=/srv/control-plane/bots ../scripts/backup_bots.sh /srv/control-plane/backups
# restore: tar -xzf <file> -C /srv/control-plane/bots
```

**Update the control plane** (after `git pull`):
```bash
cd deploy && docker compose up -d --build
```

**Update Freqtrade** to a newer release:
```bash
docker pull freqtradeorg/freqtrade:stable
# then Re-provision each user's bot from the admin panel to recreate on the new image
```

## Troubleshooting

- **Bot never becomes reachable / `/ping` fails:** check `docker logs cp-bot-<username>`.
  A common cause is the exchange being unreachable from the VPS (e.g. Binance HTTP 451 in
  some regions) — Freqtrade's REST API only starts after it loads markets. Switch
  `CP_DEFAULT_EXCHANGE` to one that works from your location.
- **`fiat_display_currency`** is disabled by default because it makes a blocking CoinGecko
  call at startup; re-enable it in `backend/app/services/config_builder.py` only if
  CoinGecko is reachable from the VPS.
- **Provisioning fails with a bind-mount/path error:** verify `/srv/control-plane/bots`
  exists on the host and is mounted at the same path in the control plane (step 2 + the
  compose volume).
- **TLS not issued:** ensure ports 80/443 are open and the domain's A record points at the
  VPS before `docker compose up`.
