import os
import sys
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from pymongo import MongoClient


def conectar_mongo():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/?directConnection=true")
    options = {"serverSelectionTimeoutMS": 5000, "tz_aware": True}
    user = os.environ.get("MONGODB_USER")
    if user:
        password = os.environ.get("MONGODB_PASSWORD")
        if not password:
            raise ValueError("Definí MONGODB_PASSWORD en .env o en el entorno.")
        options.update(username=user, password=password)
    client = MongoClient(uri, **options)
    return client, client[os.environ.get("MONGODB_DATABASE", "farmared_importacion")]


def conectar_neo4j():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise ValueError("Definí NEO4J_PASSWORD en .env o en el entorno.")
    return GraphDatabase.driver(uri, auth=(user, password), connection_timeout=5)


def clients():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    mongo = MongoClient(
        os.environ["MONGODB_URI"],
        username=os.environ["MONGODB_USER"],
        password=os.environ["MONGODB_PASSWORD"],
        serverSelectionTimeoutMS=10000,
    )
    neo = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
        connection_timeout=10,
    )
    return mongo, neo


def main():
    try:
        mongo, neo = clients()
        with mongo, neo:
            mongo.admin.command("ping")
            # ping solo no prueba autenticación: connectionStatus debe tener usuario.
            assert mongo.admin.command("connectionStatus")["authInfo"]["authenticatedUsers"]
            print("MongoDB: autenticación OK; servidor", mongo.server_info()["version"])
            hello = mongo.admin.command("hello")
            if hello.get("setName") != "rs0" or not hello.get("isWritablePrimary"):
                raise RuntimeError("MongoDB requiere rs0 con un PRIMARY")
            print("MongoDB: replica set rs0; PRIMARY disponible")
            assert neo.verify_authentication(), "Neo4j rechazó la autenticación"
            with neo.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session:
                assert session.run("RETURN 1 AS ok").single()["ok"] == 1
                server = session.run("CALL dbms.components() YIELD versions RETURN versions[0] AS version").single()
                print("Neo4j: autenticación OK; servidor", server["version"])
        for package in ("pymongo", "dnspython", "neo4j", "pytz", "python-dotenv"):
            print(f"{package}=={version(package)}")
    except Exception as exc:
        # Los errores de drivers pueden incluir URIs: evitar imprimirlos.
        print(f"Conexión fallida ({type(exc).__name__}). Revisar .env, hosts, credenciales y servicios.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
