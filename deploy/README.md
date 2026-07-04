# VPS deployment (Apache + Docker)

Plane runs behind its own Caddy proxy inside Docker. On a VPS that already uses Apache on ports 80/443, bind Plane to a **high host port** (e.g. `8090`) and let Apache reverse-proxy to it.

## Prerequisites

- Docker and Docker Compose on the VPS
- Apache with TLS for your domain
- ~6–8 GB RAM recommended if other apps run on the same host
- DNS A record pointing `plane.example.com` → VPS IP

## One-time server setup

```bash
git clone <your-fork-url> /opt/plane
cd /opt/plane
chmod +x setup.sh deploy/env-sync.sh
./setup.sh   # optional: creates default .env templates (will be overwritten by sync)
docker compose up --build -d
```

Configure Apache using `deploy/apache-plane.conf.example`.

## Local env workflow (secrets stay off GitHub)

```bash
# 1. SSH/deploy target
cp deploy/config.example deploy/config
# edit VPS_SSH and VPS_PATH

# 2. Production env files (gitignored)
cp .env.vps.example .env.vps
cp apps/api/.env.vps.example apps/api/.env.vps
# edit: domain, passwords, SECRET_KEY, LIVE_SERVER_SECRET_KEY

# 3. Push code
git push

# 4. Sync secrets to server
./deploy/env-sync.sh

# 5. On VPS: pull and restart
ssh deploy@your-vps 'cd /opt/plane && git pull && docker compose up --build -d'
```

Use `./deploy/env-sync.sh --dry-run` to preview transfers.

## First-time Plane setup

1. Open `https://plane.example.com/god-mode/` and register as instance admin
2. Sign in at `https://plane.example.com`

## Troubleshooting

| Symptom                     | Check                                                              |
| --------------------------- | ------------------------------------------------------------------ |
| Maintenance / startup error | `curl -i https://plane.example.com/api/instances/` → should be 200 |
| 502 Bad Gateway             | `docker logs api --tail 50`, `docker logs proxy --tail 30`         |
| CORS errors                 | `CORS_ALLOWED_ORIGINS` must match public URL exactly               |
| Upload failures             | `USE_MINIO=1`, `AWS_S3_ENDPOINT_URL=http://plane-minio:9000`       |

## Port reference

| Where                   | Port    | Notes                                |
| ----------------------- | ------- | ------------------------------------ |
| Apache                  | 80, 443 | Public                               |
| Plane proxy (host)      | 8090    | `LISTEN_HTTP_PORT` in `.env.vps`     |
| Plane proxy (container) | 80      | `SITE_ADDRESS=:80`                   |
| web/api/etc.            | —       | Docker network only; no host publish |
