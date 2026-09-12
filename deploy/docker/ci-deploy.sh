#!/bin/bash
# Runs ON THE SERVER, invoked over SSH by the deploy job in
# .github/workflows/main.yml — replaces Watchtower's poll-and-swap with an
# explicit step at the end of a green CI run.
#
# The SSH key CI uses for this is restricted in authorized_keys to only ever
# run this exact command (see docs/deploy-ssh.md) — so even a leaked key
# can't do anything beyond "redeploy from origin/main", not arbitrary shell.
set -euo pipefail

REPO_DIR="$HOME/Documents/projects/quests"
COMPOSE="docker compose --env-file .env -f deploy/docker/docker-compose.yml"

cd "$REPO_DIR"
git fetch origin main
git reset --hard origin/main

# shellcheck disable=SC2086
$COMPOSE pull
# shellcheck disable=SC2086
$COMPOSE up -d --remove-orphans

$COMPOSE ps
