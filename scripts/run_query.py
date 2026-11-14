"""Ejecuta q01-q15 desde terminal con una salida JSON uniforme."""

import argparse
from datetime import date, datetime
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
from src.services.query_13_abm_clientes import COBERTURAS, q13
from src.services.query_14_registro_venta import MEDIOS_PAGO, q14
from src.services.query_15_descuento_stock import q15
from src.services.sincronizacion_neo4j import ErrorSincronizacion

CONSULTAS = {
    consulta.__name__: consulta
    for consulta in (q01, q02, q03, q04, q05, q06, q07, q08, q09, q10, q11, q12)
}
CONSULTAS_NEO4J = {"q03", "q04", "q06", "q10", "q12"}


def a_json(valor):
    """Representa fechas BSON y fechas de Neo4j sin exponer tipos internos."""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if hasattr(valor, "iso_format"):
        return valor.iso_format()
    raise TypeError(f"No se puede serializar {type(valor).__name__}")


def item_venta(valor):
    """Convierte PRODUCTO:CANTIDAD al contrato de ítems de q14."""
    try:
        producto, cantidad_texto = valor.rsplit(":", 1)
        cantidad = int(cantidad_texto)
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError(
            "usá PRODUCTO:CANTIDAD, por ejemplo PRD001:2") from None
    if not producto.strip() or cantidad <= 0:
        raise argparse.ArgumentTypeError(
            "el producto no puede estar vacío y la cantidad debe ser positiva")
    return {"id_producto": producto.strip(), "cantidad": cantidad}


def _consulta(subparsers, numero, descripcion):
    codigo = f"q{numero:02d}"
    aliases = [str(numero)]
    if numero < 10:
        aliases.append(f"{numero:02d}")
    parser = subparsers.add_parser(codigo, aliases=aliases, help=descripcion)
    parser.set_defaults(consulta=codigo)
    return parser


def crear_parser():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="seleccion", title="consultas", required=True)

    descripciones = (
        "productos activos y proveedor",
        "ventas pendientes",
        "historial de un cliente",
        "clientes con más de una receta",
        "ventas recientes por farmacéutico",
        "dispensas atrasadas",
        "productos más vendidos",
        "stock bajo",
        "ventas libres menores a $5000",
        "clientes atendidos por sucursal",
        "ingresos por farmacéutico",
        "clientes sin ventas en el último año",
    )
    parsers = {numero: _consulta(subparsers, numero, descripcion)
               for numero, descripcion in enumerate(descripciones, 1)}
    parsers[3].add_argument("--id-cliente", required=True, help="ID del cliente.")
    parsers[10].add_argument("--id-sucursal", required=True, help="ID de la sucursal.")

    p13 = _consulta(subparsers, 13, "alta, modificación y baja lógica de clientes")
    operaciones = p13.add_subparsers(dest="operacion", title="operaciones", required=True)
    alta = operaciones.add_parser("alta", help="Crear un cliente activo.")
    for campo in ("id-cliente", "nombre", "apellido", "dni", "email", "telefono",
                  "ciudad", "provincia"):
        alta.add_argument(f"--{campo}", required=True)
    alta.add_argument("--obra-social", required=True, choices=sorted(COBERTURAS))
    alta.add_argument("--nro-afiliado")

    modificar = operaciones.add_parser("modificar", help="Cambiar contacto o cobertura.")
    modificar.add_argument("--id-cliente", required=True)
    modificar.add_argument("--email")
    modificar.add_argument("--telefono")
    modificar.add_argument("--obra-social", choices=sorted(COBERTURAS))
    modificar.add_argument("--nro-afiliado")
    for operacion, ayuda in (("baja", "Dar de baja lógicamente."),
                             ("reactivar", "Reactivar un cliente.")):
        accion = operaciones.add_parser(operacion, help=ayuda)
        accion.add_argument("--id-cliente", required=True)

    p14 = _consulta(subparsers, 14, "registrar una venta y descontar stock")
    p14.add_argument("--id-venta", required=True)
    p14.add_argument("--id-cliente", required=True)
    p14.add_argument("--id-farmaceutico", required=True)
    p14.add_argument("--medio-pago", required=True, choices=sorted(MEDIOS_PAGO))
    p14.add_argument("--item", action="append", required=True, type=item_venta,
                     metavar="PRODUCTO:CANTIDAD",
                     help="Ítem de venta; se puede repetir.")
    p14.add_argument("--id-receta", help="Obligatoria si algún producto requiere receta.")

    p15 = _consulta(subparsers, 15, "aplicar o consultar el descuento FEFO de una venta")
    p15.add_argument("--id-venta", required=True,
                     help="Venta completada con descuento pendiente o reparto ya aplicado.")
    return parser


def _argumentos_q13(args):
    if args.operacion == "alta":
        campos = ("id_cliente", "nombre", "apellido", "dni", "email", "telefono",
                  "ciudad", "provincia", "obra_social", "nro_afiliado")
    elif args.operacion == "modificar":
        campos = ("id_cliente", "email", "telefono", "obra_social", "nro_afiliado")
    else:
        campos = ("id_cliente",)
    return {campo: getattr(args, campo) for campo in campos
            if campo == "id_cliente" or getattr(args, campo) is not None}


def ejecutar_mongo(db, args):
    """Ejecuta una consulta que solo necesita MongoDB."""
    if args.consulta == "q13":
        return q13(db, args.operacion, **_argumentos_q13(args))
    if args.consulta == "q14":
        return q14(db, args.id_venta, args.id_cliente, args.id_farmaceutico,
                   args.medio_pago, args.item, id_receta=args.id_receta)
    if args.consulta == "q15":
        return q15(db, args.id_venta)
    return CONSULTAS[args.consulta](db)


def ejecutar(args):
    cliente, db = conectar_mongo()
    with cliente:
        if args.consulta in CONSULTAS_NEO4J:
            with conectar_neo4j() as driver:
                with driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as sesion:
                    parametros = {}
                    if args.consulta == "q03":
                        parametros["id_cliente"] = args.id_cliente
                    elif args.consulta == "q10":
                        parametros["id_sucursal"] = args.id_sucursal
                    return CONSULTAS[args.consulta](db, sesion, **parametros)
        return ejecutar_mongo(db, args)


def _error(consulta, codigo, mensaje):
    print(f"ERROR {consulta} [{codigo}]: {mensaje}", file=sys.stderr)


def main(argv=None):
    parser = crear_parser()
    args = parser.parse_args(argv)
    try:
        resultado = ejecutar(args)
    except ErrorSincronizacion as exc:
        _error(args.consulta, "sincronizacion", str(exc))
        return 1
    except DriverError:
        _error(args.consulta, "conexion_neo4j",
               "No se pudo conectar a Neo4j. Revisá su configuración y estado.")
        return 1
    except PyMongoError:
        _error(args.consulta, "conexion_mongodb",
               "MongoDB rechazó la operación. Revisá su configuración y estado.")
        return 1
    except ValueError as exc:
        _error(args.consulta, getattr(exc, "codigo", type(exc).__name__), str(exc))
        return 1
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=a_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
