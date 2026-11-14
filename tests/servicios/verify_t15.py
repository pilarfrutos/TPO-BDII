"""Verifica concurrencia, fallos parciales y recuperación del grafo (T15).

Uso: python tests/servicios/verify_t15.py [--evidencia]
"""
import json
from pathlib import Path
import sys
from uuid import uuid4

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.check_connections import conectar_mongo
from scripts.loaders.load_mongo import cargar
from src.services.query_02_ventas_pendientes import q02
from src.services.query_10_clientes_por_sucursal import q10
from src.services.sincronizacion_neo4j import ErrorSincronizacion, sincronizar_grafo
from src.utils.datos_csv import leer_datos
from neo4j_pruebas import sesion_grafo_pruebas
from verify_q14 import verificar as verificar_q14
from verify_q15 import verificar as verificar_q15


def telefono_cliente(sesion, id_cliente):
    fila = sesion.run(
        "MATCH (c:Cliente {id_cliente: $id_cliente}) RETURN c.telefono AS telefono",
        id_cliente=id_cliente,
    ).single()
    return None if fila is None else fila["telefono"]


def verificar_indisponibilidad_grafo(db, sesion):
    """Comprueba la recuperación de la proyección en el grafo de pruebas."""
    datos = leer_datos()
    id_cliente = "DC001"
    telefono_nuevo = "1151999999"
    cargar(db, datos)
    sincronizar_grafo(db, sesion)
    telefono_anterior = telefono_cliente(sesion, id_cliente)
    assert telefono_anterior == db.clientes.find_one({"id_cliente": id_cliente})["telefono"]
    db.clientes.update_one({"id_cliente": id_cliente}, {"$set": {"telefono": telefono_nuevo}})

    with GraphDatabase.driver("bolt://127.0.0.1:1", connection_timeout=1) as driver_caido:
        with driver_caido.session(database="farmared-test") as sesion_caida:
            try:
                sincronizar_grafo(db, sesion_caida)
            except ErrorSincronizacion as exc:
                error = str(exc)
            else:
                raise AssertionError("La sincronización debía fallar con Neo4j inaccesible")

    assert telefono_cliente(sesion, id_cliente) == telefono_anterior
    publicados = sincronizar_grafo(db, sesion)
    assert publicados == sum(map(len, datos.values())) == 193
    assert telefono_cliente(sesion, id_cliente) == telefono_nuevo

    return {
        "id_cliente": id_cliente,
        "telefono_antes": telefono_anterior,
        "telefono_pendiente": telefono_nuevo,
        "error_con_grafo_inaccesible": error,
        "grafo_conservo_estado_anterior": True,
        "registros_publicados_al_recuperar": publicados,
        "cambio_visible_despues_de_recuperar": True,
    }


def ejecutar_en_base_temporal(client, prefijo, verificador):
    nombre = f"farmared_test_{prefijo}_{uuid4().hex}"
    try:
        return verificador(client[nombre])
    finally:
        client.drop_database(nombre)


def verificar_sucursal_historica(db, sesion):
    datos = leer_datos()
    cargar(db, datos)
    assert "DC007" in {fila["id_cliente"] for fila in q10(db, sesion, "DS006")}

    db.farmaceuticos.update_many({"id_farmaceutico": {"$in": ["DF009", "DF005"]}},
                                 {"$set": {"id_sucursal": "DS007"}})
    assert "DC007" in {fila["id_cliente"] for fila in q10(db, sesion, "DS006")}
    assert "DC007" not in {fila["id_cliente"] for fila in q10(db, sesion, "DS007")}

    # Una carga previa puede carecer de la sucursal, incluso tras una reasignación.
    db.ventas.update_one({"id_venta": "DV007"}, {"$unset": {"id_sucursal": ""}})
    assert cargar(db, datos)["ventas"] == (0, len(datos["ventas"]))
    assert db.ventas.find_one({"id_venta": "DV007"})["id_sucursal"] == "DS006"
    assert "DC007" in {fila["id_cliente"] for fila in q10(db, sesion, "DS006")}
    assert "DC007" not in {fila["id_cliente"] for fila in q10(db, sesion, "DS007")}
    pendiente = next(fila for fila in q02(db) if fila["id_venta"] == "DV005")
    assert pendiente["sucursal"]["id_sucursal"] == "DS003"

    # Si ya se conoce una sucursal específica de la venta, se conserva.
    db.ventas.update_one({"id_venta": "DV007"}, {"$set": {"id_sucursal": "DS002"}})
    cargar(db, datos)
    assert db.ventas.find_one({"id_venta": "DV007"})["id_sucursal"] == "DS002"


def main():
    client, _ = conectar_mongo()
    with client, sesion_grafo_pruebas() as sesion:
        evidencia_q14 = ejecutar_en_base_temporal(client, "t15_q14", verificar_q14)
        evidencia_q15 = ejecutar_en_base_temporal(client, "t15_q15", verificar_q15)
        ejecutar_en_base_temporal(client, "t15_sucursal",
                                  lambda db: verificar_sucursal_historica(db, sesion))
        evidencia_grafo = ejecutar_en_base_temporal(
            client, "t15_grafo", lambda db: verificar_indisponibilidad_grafo(db, sesion))

    fallos = [
        rechazo for rechazo in evidencia_q14["rechazos"]
        if rechazo["codigo"] == "FalloInyectado"
    ]
    evidencia = {
        "fallos_intermedios_revertidos": len(fallos),
        "receta_y_reintentos": evidencia_q14["concurrencia"],
        "stock": evidencia_q15["concurrencia"],
        "grafo": evidencia_grafo,
    }
    assert evidencia["fallos_intermedios_revertidos"] == 2
    if "--evidencia" in sys.argv:
        print(json.dumps(evidencia, ensure_ascii=False, indent=2, default=str))
    print("T15 OK: concurrencia, reintentos, rollback y recuperación de Neo4j")


if __name__ == "__main__":
    main()
