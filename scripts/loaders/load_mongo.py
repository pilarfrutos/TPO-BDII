"""Carga en MongoDB los CSV originales y los adicionales de data/adicionales.

Modos:
  (por defecto)        Carga aditiva: inserta los registros que faltan y conserva
                       los existentes, aunque hayan cambiado por operaciones de
                       negocio (ABM, ventas, dispensas, descuentos de stock).
  --verificar          Compara la base con los CSV sin escribir nada.
  --reiniciar NOMBRE   Borra las nueve colecciones de la base NOMBRE y la vuelve
                       a cargar. Es destructivo: NOMBRE debe coincidir con la base
                       configurada en MONGODB_DATABASE.

La carga nunca deriva stock de las ventas: stock_lotes.csv ya es el stock
posterior a las ventas históricas y se inserta tal cual. Repetir la carga
tampoco repone stock ni revierte recetas modificadas por q14/q15.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.utils.datos_csv import ENTIDADES, leer_datos, para_mongo, resumen
from src.utils.datos_mongo import leer_snapshot
from src.utils.proyeccion_neo4j import preparar_proyeccion

INDICES_UNICOS = {"clientes": ["dni"], "farmaceuticos": ["matricula"]}
INDICES_CONSULTAS = {
    "productos": [[("activo", 1), ("id_producto", 1)]],
    "stock_lotes": ["unidades", [("id_sucursal", 1), ("id_producto", 1),
                                 ("vencimiento", 1), ("id_lote", 1)]],
    "ventas": [[("estado", 1), ("fecha", 1)]],
    "detalle_ventas": ["id_venta"],
}
# IndexOptionsConflict, IndexKeySpecsConflict y DuplicateKey.
CONFLICTOS_INDICE = {85, 86, 11000}


def crear_indices(db):
    from pymongo.errors import OperationFailure

    for nombre, (_, clave, _) in ENTIDADES.items():
        coleccion = db[nombre]
        try:
            for campo in [clave, *INDICES_UNICOS.get(nombre, ())]:
                coleccion.create_index(campo, unique=True)
            for indice in INDICES_CONSULTAS.get(nombre, ()):
                coleccion.create_index(indice)
        except OperationFailure as exc:
            if exc.code not in CONFLICTOS_INDICE:
                raise
            raise RuntimeError(
                f"{nombre}: no se pudo crear un índice ({exc.code}). La base tiene datos o "
                "índices de una carga anterior incompatibles con el modelo; revisalos con "
                "--verificar o usá --reiniciar."
            ) from exc


def cargar(db, datos):
    """Inserta los registros ausentes por ID de origen; no modifica los existentes.

    Devuelve {colección: (nuevos, ya_existentes)}.
    """
    from pymongo import UpdateOne

    crear_indices(db)
    conteos = {}
    for nombre, filas in datos.items():
        clave = ENTIDADES[nombre][1]
        operaciones = [UpdateOne({clave: f[clave]}, {"$setOnInsert": para_mongo(f)}, upsert=True)
                       for f in filas]
        nuevos = existentes = 0
        if operaciones:
            resultado = db[nombre].bulk_write(operaciones)
            nuevos, existentes = resultado.upserted_count, resultado.matched_count
        conteos[nombre] = (nuevos, existentes)
        print(f"{nombre}: {nuevos} nuevos; {existentes} ya existentes")
    return conteos


def reiniciar(db):
    """Borra solo las nueve colecciones del modelo; el resto de la base no se toca."""
    for nombre in ENTIDADES:
        db[nombre].drop()


def _canonico(valor):
    if isinstance(valor, datetime):
        return valor.astimezone(timezone.utc) if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    return valor


def verificar(client, db, datos):
    """Compara la base con los CSV a partir de un snapshot consistente.

    Devuelve (informe, problemas). Para cada colección, el informe lista:
    - faltantes: IDs de los CSV ausentes en la base (problema).
    - modificados: {ID: campos distintos}; esperables tras operaciones de negocio.
    - propios: IDs de la base que no vienen de los CSV (altas de q13/q14).
    Los problemas incluyen faltantes, IDs repetidos y documentos que no cumplen
    el contrato de tipos y referencias (por ejemplo, restos de otra carga).
    """
    snapshot = leer_snapshot(client, db)
    informe = {}
    problemas = []
    for nombre, (_, clave, _) in ENTIDADES.items():
        documentos = snapshot[nombre]
        en_base = {d.get(clave): d for d in documentos}
        if len(en_base) != len(documentos):
            problemas.append(f"{nombre}: hay documentos con {clave} repetido o ausente")
        esperados = {f[clave]: para_mongo(f) for f in datos[nombre]}
        modificados = {}
        for identificador in sorted(esperados.keys() & en_base.keys()):
            esperado, actual = esperados[identificador], en_base[identificador]
            campos = sorted(campo for campo in esperado.keys() | actual.keys()
                            if _canonico(esperado.get(campo)) != _canonico(actual.get(campo)))
            if campos:
                modificados[identificador] = campos
        informe[nombre] = {
            "esperados": len(esperados),
            "en_base": len(documentos),
            "faltantes": sorted(esperados.keys() - en_base.keys()),
            "modificados": modificados,
            "propios": sorted(en_base.keys() - esperados.keys(), key=str),
        }
        if informe[nombre]["faltantes"]:
            problemas.append(f"{nombre}: faltan {', '.join(informe[nombre]['faltantes'])}")
    try:
        preparar_proyeccion(snapshot)
    except ValueError as exc:
        problemas.append(f"contrato de datos: {exc}")
    return informe, problemas


def imprimir_verificacion(informe, problemas):
    print("Verificación de la base contra los CSV:")
    for nombre, datos in informe.items():
        linea = (f"  {nombre}: {datos['en_base']} en la base, {datos['esperados']} en los CSV; "
                 f"{len(datos['faltantes'])} faltantes")
        if datos["modificados"]:
            detalle = "; ".join(f"{i} ({', '.join(c)})" for i, c in datos["modificados"].items())
            linea += f"; modificados por operaciones: {detalle}"
        if datos["propios"]:
            linea += f"; propios de la base: {', '.join(map(str, datos['propios']))}"
        print(linea)
    for problema in problemas:
        print(f"ERROR: {problema}", file=sys.stderr)
    print("Verificación OK." if not problemas else f"Verificación con {len(problemas)} problema(s).")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Validar los CSV sin conectar")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--verificar", action="store_true",
                      help="Comparar la base con los CSV sin escribir")
    modo.add_argument("--reiniciar", metavar="NOMBRE_BASE",
                      help="Borrar las nueve colecciones de esa base y volver a cargar")
    args = parser.parse_args()
    datos = leer_datos()
    resumen(datos)
    if args.dry_run:
        print("Validación completada; sin conexión a MongoDB.")
        return 0
    from scripts.check_connections import conectar_mongo

    client, db = conectar_mongo()
    with client:
        client.admin.command("ping")
        if args.reiniciar is not None and args.reiniciar != db.name:
            print(f"Para reiniciar, indicá el nombre de la base configurada: {db.name}.",
                  file=sys.stderr)
            return 2
        try:
            if args.reiniciar:
                reiniciar(db)
                print(f"Colecciones de {db.name} eliminadas; se cargan desde cero.")
            if not args.verificar:
                cargar(db, datos)
                print(f"Carga finalizada en {db.name}. No se reemplazaron registros existentes.")
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        informe, problemas = verificar(client, db, datos)
    imprimir_verificacion(informe, problemas)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
