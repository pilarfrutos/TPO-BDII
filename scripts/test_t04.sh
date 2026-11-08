#!/bin/sh
# Conversión con datos, transacciones y persistencia en volúmenes exclusivos.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
. "$root/scripts/docker-env.sh"
project="farmared-t04-$(date -u +%Y%m%d%H%M%S)-$$"
directory="$root/.t04/$project"
mkdir -p "$directory"
chmod 700 "$root/.t04" "$directory"
sh .devcontainer/initialize.sh "$directory/.env"
unset MONGODB_USER MONGODB_PASSWORD NEO4J_PASSWORD COMPOSE_FILE COMPOSE_PROJECT_NAME
compose() {
    docker compose --env-file "$directory/.env" -p "$project" -f "$root/docker-compose.yml" \
        -f "$root/tests/t03/compose.yml" -f "$root/tests/t04/compose.yml" "$@"
}
legacy() {
    docker compose --env-file "$directory/.env" -p "$project" -f "$root/tests/t04/standalone.yml" "$@"
}
verify() {
    compose run --rm --no-deps validator python tests/t04/verify.py "$@"
}
key_identity() {
    compose exec -T mongo sh -c 'test "$(stat -c %a /data/keyfile/internal.key)" = 400 && test "$(stat -c %U /data/keyfile/internal.key)" = mongodb && sha256sum /data/keyfile/internal.key'
}
cleanup() {
    echo "Prueba: $project. Evidencia y credenciales privadas: .t04/$project." >&2
    if compose stop mongo neo4j >/dev/null 2>&1; then
        echo "Motores detenidos; datos y keyfile conservados en sus volúmenes." >&2
    else
        echo "No se pudo confirmar la detención; revisar ese proyecto Docker." >&2
        return 1
    fi
}
trap cleanup EXIT
compose config --quiet
compose build validator mongo
legacy up -d --wait mongo
verify seed > "$directory/standalone.json"
legacy stop mongo
sh scripts/start.sh --env-file "$directory/.env" -p "$project" -f "$root/docker-compose.yml" \
    -f "$root/tests/t03/compose.yml" -f "$root/tests/t04/compose.yml"
verify snapshot > "$directory/migrated.json"
cmp "$directory/standalone.json" "$directory/migrated.json"
verify identity > "$directory/identity-before.json"
key_identity > "$directory/key-before.private"
compose run --rm --no-deps mongo-init
verify identity > "$directory/identity-repeated.json"
cmp "$directory/identity-before.json" "$directory/identity-repeated.json"
verify transactions > "$directory/committed.json"
verify loaders > "$directory/loaders.json"
cmp "$directory/committed.json" "$directory/loaders.json"
compose stop mongo neo4j
sh scripts/start.sh --env-file "$directory/.env" -p "$project" -f "$root/docker-compose.yml" \
    -f "$root/tests/t03/compose.yml" -f "$root/tests/t04/compose.yml"
verify snapshot > "$directory/restarted.json"
verify identity > "$directory/identity-after.json"
key_identity > "$directory/key-after.private"
cmp "$directory/committed.json" "$directory/restarted.json"
cmp "$directory/identity-before.json" "$directory/identity-after.json"
cmp "$directory/key-before.private" "$directory/key-after.private"
echo "T04 OK: migración sin pérdida, PRIMARY, commit, rollback, inicialización repetible y persistencia."
