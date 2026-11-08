import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from pymongo import MongoClient, ReadPreference
from pymongo.errors import DuplicateKeyError, OperationFailure
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from datos_csv import ENTIDADES, leer_datos


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def client(password=None):
    return MongoClient(os.environ["MONGODB_URI"], username=os.environ["MONGODB_USER"],
                       password=password if password is not None else os.environ["MONGODB_PASSWORD"],
                       serverSelectionTimeoutMS=10000)


def primary(connection):
    require(bool(connection.admin.command("connectionStatus")["authInfo"]["authenticatedUsers"]),
            "Se requiere autenticación")
    hello = connection.admin.command("hello")
    require(hello.get("setName") == "rs0" and hello.get("isWritablePrimary"), "Se requiere PRIMARY de rs0")


def snapshot(database):
    content = {}
    for name in sorted(database.list_collection_names()):
        rows = list(database[name].find().sort("_id", 1))
        indexes = sorted(database[name].list_indexes(), key=lambda index: index["name"])
        content[name] = {"rows": rows, "indexes": indexes}
    payload = json.dumps(content, sort_keys=True, default=str)
    return {"sha256": hashlib.sha256(payload.encode()).hexdigest(),
            "counts": {name: len(data["rows"]) for name, data in content.items()}}


def loader(name):
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / name)], capture_output=True, text=True)
    require(result.returncode == 0, f"Falló {name}")


def identity(connection):
    config = connection.admin.command("replSetGetConfig")["config"]
    result = {key: config[key] for key in ("_id", "version", "members")}
    result["replicaSetId"] = str(config["settings"]["replicaSetId"])
    return result


def transactions(connection, database):
    primary(connection)
    # Probar que credenciales incorrectas no permiten leer los datos.
    with client(password="invalid-" + os.urandom(16).hex()) as rejected:
        try:
            rejected[database.name].t04_left.find_one()
        except OperationFailure as error:
            require(error.code == 18, "Se esperaba rechazo por autenticación")
        else:
            raise AssertionError("Se aceptó una contraseña incorrecta")

    require(database.t04_left.find_one({"_id": "left"})["value"] == 100, "Fixture inicial inesperada")
    require(database.t04_right.find_one({"_id": "right"})["value"] == 200, "Fixture inicial inesperada")
    options = {"read_concern": ReadConcern("snapshot"), "write_concern": WriteConcern("majority"),
               "read_preference": ReadPreference.PRIMARY}
    with connection.start_session() as session:
        with session.start_transaction(**options):
            database.t04_left.update_one({"_id": "left"}, {"$inc": {"value": -10}}, session=session)
            database.t04_right.update_one({"_id": "right"}, {"$inc": {"value": 10}}, session=session)
            # Dentro de la transacción se ven ambas escrituras.
            require(database.t04_left.find_one({"_id": "left"}, session=session)["value"] == 90,
                    "Escritura no visible dentro de la transacción")
            # Otra sesión todavía ve los valores confirmados anteriormente.
            require(database.t04_left.find_one({"_id": "left"})["value"] == 100,
                    "Escritura no confirmada visible externamente")
    require(database.t04_left.find_one({"_id": "left"})["value"] == 90, "Commit incompleto")
    require(database.t04_right.find_one({"_id": "right"})["value"] == 210, "Commit incompleto")
    committed = snapshot(database)

    class InjectedFailure(Exception):
        pass

    try:
        with connection.start_session() as session:
            with session.start_transaction(**options):
                database.t04_left.update_one({"_id": "left"}, {"$inc": {"value": -5}}, session=session)
                raise InjectedFailure()
    except InjectedFailure:
        pass
    require(snapshot(database) == committed, "Rollback tras primera escritura incompleto")

    try:
        with connection.start_session() as session:
            with session.start_transaction(**options):
                database.t04_left.update_one({"_id": "left"}, {"$inc": {"value": -5}}, session=session)
                database.t04_right.update_one({"_id": "right"}, {"$inc": {"value": 5}}, session=session)
                # Error real del servidor después de modificar dos documentos.
                database.t04_right.insert_one({"_id": "right", "value": 999}, session=session)
    except DuplicateKeyError:
        pass
    else:
        raise AssertionError("No se produjo el error de unicidad esperado")
    require(snapshot(database) == committed, "Rollback tras error del servidor incompleto")
    print("PRIMARY, autenticación, commit y ambos rollback: OK", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("seed", "snapshot", "identity", "transactions", "loaders"))
    args = parser.parse_args()
    require(os.environ.get("FARMARED_T04_TEST") == "1" and
            os.environ.get("MONGODB_DATABASE") == "farmared_t04_test", "Usar únicamente el Compose de pruebas T04")
    with client() as connection:
        database = connection[os.environ["MONGODB_DATABASE"]]
        if args.phase == "seed":
            require(not connection.admin.command("hello").get("setName"), "La fixture debe ser standalone")
            require(not database.list_collection_names(), "La fixture debe estar vacía")
            loader("loader_mongo.py")
            database.t04_left.insert_one({"_id": "left", "value": 100})
            database.t04_right.insert_one({"_id": "right", "value": 200})
        else:
            primary(connection)
            if args.phase == "identity":
                print(json.dumps(identity(connection), sort_keys=True))
                return
            if args.phase == "transactions":
                transactions(connection, database)
            elif args.phase == "loaders":
                before = snapshot(database)
                for _ in range(2):
                    loader("loader_mongo.py")
                    loader("loader_neo4j.py")
                require(before == snapshot(database), "Los loaders modificaron datos MongoDB existentes")
                # También comparar contenido del grafo usando el verificador de T03.
                import importlib.util
                spec = importlib.util.spec_from_file_location("verify_t03", ROOT / "tests/t03/verify.py")
                verify_t03 = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(verify_t03)
                first = verify_t03.snapshot()
                loader("loader_neo4j.py")
                require(verify_t03.snapshot() == first, "Neo4j dejó de ser idempotente")
                print("Loaders existentes e idempotencia: OK", file=sys.stderr)
        expected = leer_datos()
        for name in ENTIDADES:
            require(database[name].count_documents({}) == len(expected[name]), f"Conteo inesperado: {name}")
        print(json.dumps(snapshot(database), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"T04: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Los drivers pueden incluir URIs o credenciales en sus excepciones.
        print(f"T04 falló ({type(error).__name__}); revisar el entorno aislado.", file=sys.stderr)
        sys.exit(1)
