"""Sincroniza Neo4j con las colecciones de MongoDB."""
import argparse
import os
from pathlib import Path
import sys

from neo4j.exceptions import DriverError
from pymongo.errors import PyMongoError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.check_connections import conectar_mongo, conectar_neo4j
from src.services.sincronizacion_neo4j import (
    ErrorSincronizacion, leer_proyeccion, sincronizar_grafo,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Leer y validar el snapshot de MongoDB sin conectar a Neo4j")
    args = parser.parse_args()

    try:
        cliente, db = conectar_mongo()
    except (PyMongoError, ValueError):
        print("ERROR: No se pudo configurar la conexión a MongoDB. Revisá .env.", file=sys.stderr)
        return 1

    try:
        with cliente:
            if args.dry_run:
                total = sum(map(len, leer_proyeccion(db).values()))
                print(f"Snapshot válido: {total} registros. Sin conexión a Neo4j.")
                return 0

            with conectar_neo4j() as driver:
                with driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as sesion:
                    total = sincronizar_grafo(db, sesion)
    except ErrorSincronizacion as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (DriverError, ValueError):
        print("ERROR: No se pudo configurar la conexión a Neo4j. Revisá .env.", file=sys.stderr)
        return 1

    print(f"Sincronización finalizada: {total} registros proyectados desde MongoDB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
