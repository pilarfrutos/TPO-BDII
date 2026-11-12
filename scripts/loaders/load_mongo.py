import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.datos_csv import ENTIDADES, leer_datos, para_mongo, resumen

INDICES_CONSULTAS = {
    "productos": [[("activo", 1), ("id_producto", 1)]],
    "stock_lotes": ["unidades", [("id_sucursal", 1), ("id_producto", 1),
                                 ("vencimiento", 1), ("id_lote", 1)]],
    "ventas": [[("estado", 1), ("fecha", 1)]],
    "detalle_ventas": ["id_venta"],
}


def cargar(db, datos):
    from pymongo import UpdateOne

    for nombre, filas in datos.items():
        clave = ENTIDADES[nombre][1]
        coleccion = db[nombre]
        coleccion.create_index(clave, unique=True)
        if nombre == "clientes":
            coleccion.create_index("dni", unique=True)
        if nombre == "farmaceuticos":
            coleccion.create_index("matricula", unique=True)
        for indice in INDICES_CONSULTAS.get(nombre, ()):
            coleccion.create_index(indice)
        operaciones = [UpdateOne({clave: f[clave]}, {"$setOnInsert": para_mongo(f)}, upsert=True)
                       for f in filas]
        if operaciones:
            resultado = coleccion.bulk_write(operaciones)
            print(f"{nombre}: {resultado.upserted_count} nuevos; {resultado.matched_count} ya existentes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validar sin conectar ni escribir")
    args = parser.parse_args()
    datos = leer_datos()
    resumen(datos)
    if args.dry_run:
        print("Validación completada; sin conexión a MongoDB.")
        return
    from scripts.check_connections import conectar_mongo

    client, db = conectar_mongo()
    with client:
        client.admin.command("ping")
        cargar(db, datos)
    print(f"Carga finalizada en {db.name}. No se reemplazaron registros existentes.")


if __name__ == "__main__":
    main()
