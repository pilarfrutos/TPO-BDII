#!/bin/sh
# Se ejecuta en el host antes de que Compose interpole las credenciales.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
destination=${1:-"$root/.env"}
if [ -e "$destination" ]; then
    echo "Configuración existente conservada."
    exit 0
fi
umask 077
# Hexadecimal: compatible con dotenv, Compose y NEO4J_AUTH; nunca se imprime.
mongo_secret=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
neo4j_secret=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
# noclobber protege también frente a una inicialización simultánea.
set -C
sed -e "s/^MONGODB_PASSWORD=$/MONGODB_PASSWORD=$mongo_secret/" \
    -e "s/^NEO4J_PASSWORD=$/NEO4J_PASSWORD=$neo4j_secret/" \
    "$root/.env.example" > "$destination"
echo "Configuración privada creada; no se mostraron credenciales."
