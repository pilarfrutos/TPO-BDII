"""Carga inicial de nodos y referencias de los CSV en Neo4j, sin duplicarlos."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.utils.datos_csv import ENTIDADES, RELACIONES, leer_datos, resumen
from src.utils.proyeccion_neo4j import preparar_proyeccion


def cargar(tx, datos):
    # Etiquetas, propiedades y relaciones provienen de constantes; valores parametrizados.
    for nombre, filas in datos.items():
        etiqueta, clave, _ = ENTIDADES[nombre]
        tx.run(f"UNWIND $filas AS fila MERGE (n:{etiqueta} {{{clave}: fila.{clave}}}) "
               "ON CREATE SET n += fila", filas=filas).consume()
    for origen, campo, destino, relacion in RELACIONES:
        etiqueta_a, clave_a, _ = ENTIDADES[origen]
        etiqueta_b, clave_b, _ = ENTIDADES[destino]
        # Usar la referencia persistida: no recrear una relación vieja si el nodo cambió.
        tx.run(f"MATCH (a:{etiqueta_a}) WHERE a.{clave_a} IN $ids "
               f"MATCH (b:{etiqueta_b} {{{clave_b}: a.{campo}}}) "
               f"MERGE (a)-[:{relacion}]->(b)",
               ids=[f[clave_a] for f in datos[origen] if f[campo] is not None]).consume()


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
    print("Carga finalizada: nodos existentes conservados y relaciones sin duplicados.")


if __name__ == "__main__":
    main()
