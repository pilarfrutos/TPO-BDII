"""Carga inicial aditiva de los CSV en MongoDB. No descuenta stock histórico."""
import argparse
import os
from pathlib import Path
from datos_csv import ENTIDADES, leer_datos, para_mongo, resumen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validar sin conectar ni escribir")
    args = parser.parse_args()
    datos = leer_datos()
    resumen(datos)
    if args.dry_run:
        print("Validación completada; sin conexión a MongoDB.")
        return
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from pymongo import MongoClient, UpdateOne

    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/?directConnection=true")
    database = os.environ.get("MONGODB_DATABASE", "farmared_importacion")
    user = os.environ.get("MONGODB_USER")
    password = os.environ.get("MONGODB_PASSWORD")
    options = {"serverSelectionTimeoutMS": 5000}
    if user:
        if not password:
            raise ValueError("Definí MONGODB_PASSWORD en .env o en el entorno.")
        options.update(username=user, password=password)
    with MongoClient(uri, **options) as client:
        client.admin.command("ping")
        db = client[database]
        for nombre, filas in datos.items():
            clave = ENTIDADES[nombre][1]
            coleccion = db[nombre]
            coleccion.create_index(clave, unique=True)
            if nombre == "clientes":
                coleccion.create_index("dni", unique=True)
            if nombre == "farmaceuticos":
                coleccion.create_index("matricula", unique=True)
            operaciones = [UpdateOne({clave: f[clave]}, {"$setOnInsert": para_mongo(f)}, upsert=True) for f in filas]
            if operaciones:
                resultado = coleccion.bulk_write(operaciones)
                print(f"{nombre}: {resultado.upserted_count} nuevos; {resultado.matched_count} ya existentes")
    print(f"Carga finalizada en {database}. No se reemplazaron registros existentes.")


if __name__ == "__main__":
    main()
