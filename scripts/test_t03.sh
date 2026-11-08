#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
project="farmared-t03-$(date -u +%Y%m%d%H%M%S)-$$"
directory="$root/.t03/$project"
mkdir -p "$directory"
chmod 700 "$root/.t03" "$directory"
sh .devcontainer/initialize.sh "$directory/.env"
compose() {
    docker compose --env-file "$directory/.env" -p "$project" \
        -f "$root/docker-compose.yml" -f "$root/tests/t03/compose.yml" "$@"
}
# No filtrar secretos de variables previamente exportadas hacia el proyecto test.
unset MONGODB_USER MONGODB_PASSWORD NEO4J_PASSWORD COMPOSE_FILE COMPOSE_PROJECT_NAME
cleanup() {
    echo "Prueba: $project. Credenciales y evidencia: .t03/$project (privado)." >&2
    if compose stop mongo neo4j >/dev/null 2>&1; then
        echo "Motores detenidos; volúmenes conservados." >&2
    else
        echo "No se pudo confirmar la detención; revisar ese proyecto Docker. Volúmenes conservados." >&2
        return 1
    fi
}
trap cleanup EXIT
compose config --quiet
compose build validator
sh scripts/start.sh --env-file "$directory/.env" -p "$project" \
    -f "$root/docker-compose.yml" -f "$root/tests/t03/compose.yml"
compose run --rm --no-deps validator python tests/t03/verify.py --load > "$directory/before.json"
compose stop mongo neo4j
compose up -d mongo neo4j
compose run --rm --no-deps mongo-init
compose up -d --wait mongo neo4j
compose run --rm --no-deps validator python tests/t03/verify.py > "$directory/after.json"
cmp "$directory/before.json" "$directory/after.json"
echo "T03 OK: autenticación, dos cargas iguales y persistencia tras stop/up."
