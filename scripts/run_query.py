import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys

from neo4j.exceptions import DriverError
from pymongo.errors import PyMongoError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.check_connections import conectar_mongo, conectar_neo4j
from src.services.query_01_productos_activos import q01
from src.services.query_02_ventas_pendientes import q02
from src.services.query_03_historial_cliente import q03
from src.services.query_04_recetas_por_cliente import q04
from src.services.query_05_ventas_por_farmaceutico import q05
from src.services.query_06_dispensas_atrasadas import q06
from src.services.query_07_productos_mas_vendidos import q07
from src.services.query_08_stock_bajo import q08
from src.services.query_09_ventas_libres import q09
from src.services.query_10_clientes_por_sucursal import q10
from src.services.query_11_ingresos_por_farmaceutico import q11
from src.services.query_12_clientes_sin_ventas import q12
from src.services.sincronizacion_neo4j import ErrorSincronizacion

CONSULTAS = {
    consulta.__name__: consulta
    for consulta in (q01, q02, q03, q04, q05, q06, q07, q08, q09, q10, q11, q12)
}
CONSULTAS_NEO4J = {"q03", "q04", "q06", "q10", "q12"}


def a_json(valor):
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    raise TypeError(f"No se puede serializar {type(valor).__name__}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("consulta", choices=CONSULTAS,
                        type=lambda valor: "q" + valor.lower().removeprefix("q").zfill(2),
                        help="Código o número de consulta, por ejemplo q08 u 8.")
    parser.add_argument("--id-cliente", help="ID del cliente para q03.")
    parser.add_argument("--id-sucursal", help="ID de la sucursal para q10.")
    args = parser.parse_args()
    parametros = {}
    for codigo, campo in (("q03", "id_cliente"), ("q10", "id_sucursal")):
        valor = getattr(args, campo)
        opcion = "--" + campo.replace("_", "-")
        if args.consulta == codigo:
            if valor is None or not valor.strip():
                parser.error(f"{codigo} requiere {opcion} con un ID no vacío.")
            parametros[campo] = valor
        elif valor is not None:
            parser.error(f"{opcion} se usa con {codigo}.")

    consulta = CONSULTAS[args.consulta]
    usa_neo4j = args.consulta in CONSULTAS_NEO4J
    try:
        cliente, db = conectar_mongo()
        with cliente:
            if usa_neo4j:
                with conectar_neo4j() as driver:
                    with driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as sesion:
                        resultado = consulta(db, sesion, **parametros)
            else:
                resultado = consulta(db)
    except ErrorSincronizacion as exc:
        print(f"No se pudo ejecutar {args.consulta}. {exc}", file=sys.stderr)
        return 1
    except DriverError:
        print(f"No se pudo conectar a Neo4j para ejecutar {args.consulta}. "
              "Revisá la configuración y el estado de Neo4j.", file=sys.stderr)
        return 1
    except (ValueError, PyMongoError) as exc:
        motores = "MongoDB y Neo4j" if usa_neo4j else "MongoDB"
        print(f"No se pudo ejecutar {args.consulta} ({type(exc).__name__}). "
              f"Revisá la configuración y el estado de {motores}.", file=sys.stderr)
        return 1
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=a_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
