#!/bin/sh
# Usar desde Mac o devcontainer. Acepta opciones globales de docker compose.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
docker compose "$@" config --quiet
docker compose "$@" up -d --build mongo neo4j
docker compose "$@" run --rm --no-deps mongo-init
docker compose "$@" up -d --wait mongo neo4j
