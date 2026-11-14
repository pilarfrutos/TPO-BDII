"""Conexión exclusiva a la instancia de Neo4j de los verificadores."""
from contextlib import contextmanager
import os

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError


@contextmanager
def sesion_grafo_pruebas():
    # conectar_mongo ya cargó el .env del proyecto.
    uri = os.environ.get("NEO4J_TEST_URI", "bolt://127.0.0.1:17687")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise ValueError("Definí NEO4J_PASSWORD en .env o en el entorno.")
    with GraphDatabase.driver(uri, auth=("neo4j", password), connection_timeout=5) as driver:
        with driver.session(database="farmared-test") as sesion:
            try:
                sesion.run("RETURN 1").consume()
            except (DriverError, Neo4jError) as exc:
                raise RuntimeError(
                    "No se pudo abrir farmared-test. Ejecutá docker compose up -d --wait neo4j-test."
                ) from exc
            yield sesion
