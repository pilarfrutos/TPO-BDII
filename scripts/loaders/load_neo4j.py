"""Carga y reconciliación de nodos y relaciones de los CSV en Neo4j."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.utils.datos_csv import ENTIDADES, RELACIONES, leer_datos, resumen
from src.utils.proyeccion_neo4j import preparar_proyeccion


def cargar(tx, datos):
    """Aplica las filas normalizadas al grafo dentro de la transacción recibida."""
    # Etiquetas, propiedades y relaciones provienen de constantes; valores parametrizados.
    for nombre, filas in datos.items():
        etiqueta, clave, _ = ENTIDADES[nombre]
        tx.run(f"UNWIND $filas AS fila MERGE (n:{etiqueta} {{{clave}: fila.{clave}}}) "
               "SET n += fila", filas=filas).consume()
    for origen, campo, destino, relacion in RELACIONES:
        etiqueta_a, clave_a, _ = ENTIDADES[origen]
        etiqueta_b, clave_b, _ = ENTIDADES[destino]
        referencias = [
            {"origen": fila[clave_a], "destino": fila[campo]} for fila in datos[origen]
        ]
        tx.run(
            f"""
            UNWIND $referencias AS ref
            MATCH (a:{etiqueta_a} {{{clave_a}: ref.origen}})
            WITH a, ref, [(a)-[r:{relacion}]->() | r] AS existentes,
                 head([(a)-[r:{relacion}]->(anterior:{etiqueta_b})
                       WHERE anterior.{clave_b} = ref.destino | r]) AS vigente
            FOREACH (obsoleto IN [r IN existentes WHERE vigente IS NULL OR r <> vigente] |
                DELETE obsoleto
            )
            WITH a, ref
            WHERE ref.destino IS NOT NULL
            MATCH (b:{etiqueta_b} {{{clave_b}: ref.destino}})
            MERGE (a)-[:{relacion}]->(b)
            """,
            referencias=referencias,
        ).consume()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validar sin conectar ni escribir")
    args = parser.parse_args()
    datos = preparar_proyeccion(leer_datos())
    resumen(datos)
    if args.dry_run:
        print("Validación completada; sin conexión a Neo4j.")
        return
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise ValueError("Definí NEO4J_PASSWORD en el entorno antes de ejecutar el loader.")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    with GraphDatabase.driver(uri, auth=(user, password), connection_timeout=5) as driver:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            for etiqueta, clave, _ in ENTIDADES.values():
                session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{etiqueta}) "
                            f"REQUIRE n.{clave} IS UNIQUE").consume()
            for etiqueta, campo in [("Cliente", "dni"), ("Farmaceutico", "matricula")]:
                session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{etiqueta}) "
                            f"REQUIRE n.{campo} IS UNIQUE").consume()
            session.execute_write(cargar, datos)
    print("Carga finalizada: propiedades y relaciones reconciliadas por identificador.")


if __name__ == "__main__":
    main()
