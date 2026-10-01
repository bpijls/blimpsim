#!/usr/bin/env bash
# Sync sim/ to the GPU host and (re)start the simulator and gateway there.
#   ./deploy.sh            # host and directory come from ../.env (SIM_HOST, SIM_REMOTE_DIR)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

env_value() { grep -E "^$1=" ../.env | cut -d= -f2- || true; }
SIM_HOST="$(env_value SIM_HOST)"
SIM_REMOTE_DIR="$(env_value SIM_REMOTE_DIR)"
SIM_SECRET="$(env_value SIM_SECRET)"
for var in SIM_HOST SIM_REMOTE_DIR SIM_SECRET; do
  [ -n "${!var}" ] || { echo "$var is blank in ../.env"; exit 1; }
done

rsync -az --delete \
  --exclude '.env' --exclude 'spike/' --exclude '.godot/' \
  --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude '.ruff_cache/' \
  ./ "$SIM_HOST:$SIM_REMOTE_DIR/"

# First deploy: create the remote .env with the shared secret.
ssh "$SIM_HOST" "cd '$SIM_REMOTE_DIR' && [ -f .env ] || sed 's|^SIM_SECRET=.*|SIM_SECRET=$SIM_SECRET|' .env.example > .env"

ssh "$SIM_HOST" "cd '$SIM_REMOTE_DIR' && docker compose up -d --build"
