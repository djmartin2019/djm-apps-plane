# VPS deployment (Apache + Docker)

Plane runs behind its own Caddy proxy inside Docker. On a VPS that already uses Apache on ports 80/443, bind Plane to a **high host port** (e.g. `8090`) and let Apache reverse-proxy to it.

## Prerequisites

- Docker and Docker Compose on the VPS
- Apache with TLS for your domain
- ~6–8 GB RAM recommended if other apps run on the same host
- DNS A record pointing your domain (e.g. `projects.djm-apps.com`) → VPS IP

## One-time server setup

```bash
git clone <your-fork-url> /opt/plane
cd /opt/plane
chmod +x setup.sh deploy/env-sync.sh
./setup.sh   # optional: creates default .env templates (will be overwritten by sync)
docker compose up --build -d
```

Configure Apache using `deploy/apache-plane.conf.example`.

## URL configuration (important)

Plane uses **two** URL config layers:

| Layer                     | File                      | When applied           | Controls                                              |
| ------------------------- | ------------------------- | ---------------------- | ----------------------------------------------------- |
| **Runtime (API)**         | `apps/api/.env`           | Container recreate     | Auth redirects, CORS, emails, `admin_base_url` in API |
| **Build-time (frontend)** | Root `.env` `VITE_*` vars | `docker compose build` | Links in web/admin/space bundles (`/god-mode`, etc.)  |

For a single Apache domain (e.g. `https://projects.djm-apps.com`):

- Set full URLs in **`apps/api/.env.vps`**: `WEB_URL`, `ADMIN_BASE_URL`, `CORS_ALLOWED_ORIGINS`, etc.
- Leave **`VITE_*_BASE_URL` empty** in **`.env.vps`** so frontend uses same-origin relative paths (`/god-mode`, `/api`, `/spaces`).

After changing `VITE_*` in `.env.vps`, you must **rebuild** frontend images:

```bash
docker compose build web admin space
docker compose up -d --force-recreate web admin space
```

After changing API URLs only, sync and recreate API services:

```bash
docker compose up -d --force-recreate api worker beat-worker
```

## Local env workflow (secrets stay off GitHub)

```bash
# 1. SSH/deploy target
cp deploy/config.example deploy/config
# edit VPS_SSH, VPS_PATH, and VPS_SSH_KEY (if not using ~/.ssh/config)

# 2. Production env files (gitignored)
cp .env.vps.example .env.vps
cp apps/api/.env.vps.example apps/api/.env.vps
# edit: domain, passwords, SECRET_KEY, LIVE_SERVER_SECRET_KEY

# 3. Push code
git push

# 4. Sync secrets to server
./deploy/env-sync.sh

# 5. On VPS: pull, rebuild frontends if VITE_* changed, restart
ssh deploy@your-vps 'cd /opt/plane && git pull && docker compose build web admin space && docker compose up -d --force-recreate api worker beat-worker web admin space proxy'
```

Use `./deploy/env-sync.sh --dry-run` to preview transfers.

## First-time Plane setup

1. Open `https://projects.djm-apps.com/god-mode/` and register as instance admin
2. Sign in at `https://projects.djm-apps.com`

## Troubleshooting

| Symptom                                                 | Check                                                                  |
| ------------------------------------------------------- | ---------------------------------------------------------------------- |
| Redirects go to wrong domain (e.g. `plane.example.com`) | API `.env` URLs + rebuild frontends if old `VITE_*` baked in           |
| Maintenance / startup error                             | `curl -i https://projects.djm-apps.com/api/instances/` → should be 200 |
| 502 Bad Gateway                                         | `docker logs api --tail 50`, `docker logs proxy --tail 30`             |
| CORS errors                                             | `CORS_ALLOWED_ORIGINS` must match public URL exactly                   |
| Upload failures                                         | `USE_MINIO=1`, `AWS_S3_ENDPOINT_URL=http://plane-minio:9000`           |
| `rsync: --chmod=F600` error                             | Fixed in env-sync.sh; use latest script                                |

Verify no stale domain in web bundle:

```bash
docker exec web grep -r "plane.example.com" /usr/share/nginx/html/ | head
# should return nothing after rebuild
```

## Port reference

| Where                   | Port    | Notes                                |
| ----------------------- | ------- | ------------------------------------ |
| Apache                  | 80, 443 | Public                               |
| Plane proxy (host)      | 8090    | `LISTEN_HTTP_PORT` in `.env.vps`     |
| Plane proxy (container) | 80      | `SITE_ADDRESS=:80`                   |
| web/api/etc.            | —       | Docker network only; no host publish |
