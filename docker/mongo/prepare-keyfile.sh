#!/bin/bash
set -euo pipefail
key=/data/keyfile/internal.key
mkdir -p /data/keyfile
if [ ! -e "$key" ]; then
    umask 077
    temporary=$(mktemp /data/keyfile/.internal.XXXXXX)
    trap 'rm -f "$temporary"' EXIT
    openssl rand -base64 756 > "$temporary"
    chown mongodb:mongodb "$temporary"
    chmod 400 "$temporary"
    # Publicar un archivo completo sin reemplazar una clave existente.
    ln "$temporary" "$key" || test -s "$key"
    rm -f "$temporary"
    trap - EXIT
fi
if [ ! -s "$key" ]; then
    echo 'Keyfile vacío: revisar el volumen mongo-keyfile sin borrar datos.' >&2
    exit 1
fi
chown mongodb:mongodb /data/keyfile "$key"
chmod 700 /data/keyfile
chmod 400 "$key"
# Conserva el bootstrap oficial y los usuarios de un volumen ya inicializado.
exec /usr/local/bin/docker-entrypoint.sh "$@"
