#!/usr/bin/env bash
# Sync local VPS env files to the server (never commit .env.vps to git).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Sync .env.vps and apps/api/.env.vps to the VPS as .env files.

Options:
  -n, --dry-run    Show what would be transferred without copying
  -h, --help       Show this help

Setup:
  1. cp deploy/config.example deploy/config
  2. cp .env.vps.example .env.vps && edit secrets
  3. cp apps/api/.env.vps.example apps/api/.env.vps && edit secrets
  4. ./deploy/env-sync.sh
EOF
}

DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n | --dry-run) DRY_RUN=1; shift ;;
    -h | --help) usage; exit 0 ;;
    *) echo -e "${RED}Unknown option: $1${NC}" >&2; usage >&2; exit 1 ;;
  esac
done

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo -e "${RED}Missing ${CONFIG_FILE}${NC}" >&2
  echo "Copy deploy/config.example to deploy/config and set VPS_SSH and VPS_PATH." >&2
  exit 1
fi

# shellcheck source=/dev/null
source "${CONFIG_FILE}"

if [[ -z "${VPS_SSH:-}" || -z "${VPS_PATH:-}" ]]; then
  echo -e "${RED}VPS_SSH and VPS_PATH must be set in deploy/config${NC}" >&2
  exit 1
fi

ROOT_ENV="${REPO_ROOT}/.env.vps"
API_ENV="${REPO_ROOT}/apps/api/.env.vps"

missing=0
for f in "${ROOT_ENV}" "${API_ENV}"; do
  if [[ ! -f "${f}" ]]; then
    echo -e "${RED}Missing ${f}${NC}" >&2
    missing=1
  fi
done
if [[ "${missing}" -eq 1 ]]; then
  echo "Create them from the .env.vps.example templates." >&2
  exit 1
fi

RSYNC_FLAGS=(-avz --chmod=F600)
if [[ "${DRY_RUN}" -eq 1 ]]; then
  RSYNC_FLAGS+=(--dry-run -v)
  echo -e "${YELLOW}Dry run — no files will be changed on the server.${NC}"
fi

echo -e "${GREEN}Syncing env files to ${VPS_SSH}:${VPS_PATH}${NC}"

rsync "${RSYNC_FLAGS[@]}" "${ROOT_ENV}" "${VPS_SSH}:${VPS_PATH}/.env"
rsync "${RSYNC_FLAGS[@]}" "${API_ENV}" "${VPS_SSH}:${VPS_PATH}/apps/api/.env"

echo -e "${GREEN}Done.${NC} On the VPS, restart if needed:"
echo "  ssh ${VPS_SSH} 'cd ${VPS_PATH} && docker compose up -d --force-recreate api worker beat-worker proxy'"
