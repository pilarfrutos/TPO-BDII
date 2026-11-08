import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_connections import clients
from datos_csv import ENTIDADES, RELACIONES, leer_datos


def snapshot():
    datos = leer_datos()
    mongo, neo = clients()
    with mongo, neo:
        assert mongo.admin.command("connectionStatus")["authInfo"]["authenticatedUsers"]
        database = mongo[os.environ["MONGODB_DATABASE"]]
        documents = {}
        for name, (_, key, _) in ENTIDADES.items():
            rows = list(database[name].find({}, {"_id": 0}).sort(key, 1))
            assert len(rows) == len(datos[name]), f"Conteo MongoDB: {name}"
            documents[name] = rows
        with neo.session(database=os.environ["NEO4J_DATABASE"]) as session:
            nodes = [dict(r) for r in session.run("MATCH (n) RETURN labels(n) AS labels, properties(n) AS props")]
            edges = [dict(r) for r in session.run(
                "MATCH (a)-[r]->(b) RETURN labels(a) AS source_labels, properties(a) AS source, "
                "type(r) AS type, properties(r) AS props, labels(b) AS target_labels, properties(b) AS target")]
            for name, (label, _, _) in ENTIDADES.items():
                assert sum(label in n["labels"] for n in nodes) == len(datos[name]), f"Conteo Neo4j: {label}"
            expected_edges = sum(sum(row[field] is not None for row in datos[source])
                                 for source, field, _, _ in RELACIONES)
            assert len(nodes) == sum(map(len, datos.values()))
            assert len(edges) == expected_edges
        # Orden canónico, sin IDs internos ni datos personales en el informe.
        encode = lambda value: json.dumps(value, sort_keys=True, default=str, ensure_ascii=True)
        content = encode({"mongo": documents, "nodes": sorted(map(encode, nodes)), "edges": sorted(map(encode, edges))})
        return {"mongo_documents": sum(map(len, documents.values())), "neo4j_nodes": len(nodes),
                "neo4j_relationships": len(edges), "sha256": hashlib.sha256(content.encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load", action="store_true")
    args = parser.parse_args()
    if args.load:
        mongo, neo = clients()
        with mongo, neo:
            db = mongo[os.environ["MONGODB_DATABASE"]]
            assert not db.list_collection_names(), "MongoDB de prueba debe estar vacía"
            with neo.session(database=os.environ["NEO4J_DATABASE"]) as session:
                assert session.run("MATCH (n) RETURN count(n) AS n").single()["n"] == 0, "Grafo de prueba debe estar vacío"
        for iteration in range(2):
            for loader in ("loader_mongo.py", "loader_neo4j.py"):
                result = subprocess.run([sys.executable, f"scripts/{loader}"], capture_output=True, text=True)
                if result.returncode:
                    # Evitar propagar tracebacks/URIs potencialmente sensibles.
                    raise RuntimeError(f"{loader} falló en carga {iteration + 1}")
            current = snapshot()
            if iteration == 0:
                previous = current
            else:
                assert current == previous, "Repetir los loaders cambió los datos"
        print("Autenticación y dos cargas: OK", file=sys.stderr)
    print(json.dumps(snapshot(), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Validación T03 fallida ({type(exc).__name__}); revisar configuración y datos de prueba.", file=sys.stderr)
        sys.exit(1)
