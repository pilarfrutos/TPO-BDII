"""Verifica q02, q05 y q09 en una base temporal de MongoDB.

Uso: python tests/queries/verify_t10.py [--evidencia]
"""
from datetime import date
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.check_connections import conectar_mongo
from scripts.loaders.load_mongo import cargar
from scripts.run_query import a_json
from src.services.query_02_ventas_pendientes import q02
from src.services.query_05_ventas_por_farmaceutico import q05
from src.services.query_09_ventas_libres import q09
from src.utils.calendario import fecha_bson
from src.utils.datos_csv import leer_datos

HOY = date(2026, 11, 13)


def venta(id_venta, id_farmaceutico, dia, *, estado="Completada"):
    return {
        "id_venta": id_venta,
        "id_cliente": "DC001",
        "id_farmaceutico": id_farmaceutico,
        "id_receta": None,
        "fecha": fecha_bson(dia),
        "tipo": "Venta libre",
        "medio_pago": "Efectivo",
        "total": 6000,
        "estado": estado,
    }


def verificar(db):
    cargar(db, leer_datos())

    pendientes = q02(db)
    assert [v["id_venta"] for v in pendientes] == ["V012", "V011", "DV005", "DV008"]
    por_id = {v["id_venta"]: v for v in pendientes}
    assert por_id["DV005"]["farmaceutico"] == {
        "id_farmaceutico": "DF005", "nombre": "Paula",
        "apellido": "Domínguez", "matricula": "MN-29005",
    }
    assert por_id["DV005"]["sucursal"] == {
        "id_sucursal": "DS003", "nombre": "Farmacia Pichincha",
    }
    assert por_id["DV008"]["total"] == 4999

    # q02 no debe excluir por el estado actual del profesional.
    db.ventas.insert_one(venta("TEST-Q02-INACTIVO", "F004", HOY, estado="Pendiente"))
    assert "TEST-Q02-INACTIVO" in {v["id_venta"] for v in q02(db)}

    conteos = {f["id_farmaceutico"]: f["cantidad_ventas"] for f in q05(db, hoy=HOY)}
    assert conteos == {
        "DF001": 1, "DF002": 1, "DF003": 1, "DF004": 1, "DF005": 1,
        "DF006": 0, "DF007": 2, "DF008": 0, "DF010": 0,
        "F001": 1, "F002": 2, "F003": 1, "F005": 3, "F006": 1, "F007": 0,
    }
    assert "DF009" not in conteos and "F004" not in conteos

    # La ventana incluye 15/09 y 13/11, pero no 14/09 ni 14/11.
    db.ventas.insert_many([
        venta("TEST-Q05-ANTES", "DF001", date(2026, 9, 14)),
        venta("TEST-Q05-DESPUES", "DF001", date(2026, 11, 14)),
    ])
    despues_limites = {
        f["id_farmaceutico"]: f["cantidad_ventas"] for f in q05(db, hoy=HOY)
    }
    assert despues_limites["DF001"] == conteos["DF001"]

    libres = q09(db)
    assert [v["id_venta"] for v in libres] == ["DV007", "V013", "V014", "DV008"]
    libres_por_id = {v["id_venta"]: v for v in libres}
    assert libres_por_id["DV008"]["estado"] == "Pendiente"
    assert "DV009" not in libres_por_id and "DV010" not in libres_por_id

    return {
        "fecha_q05": HOY.isoformat(),
        "q02": pendientes,
        "q05": q05(db, hoy=HOY),
        "q09": libres,
    }


def main():
    cliente, _ = conectar_mongo()
    nombre = f"farmared_test_t10_{uuid4().hex}"
    with cliente:
        try:
            evidencia = verificar(cliente[nombre])
        finally:
            cliente.drop_database(nombre)
    if "--evidencia" in sys.argv:
        print(json.dumps(evidencia, ensure_ascii=False, indent=2, default=a_json))
    print("q02, q05 y q09: OK en MongoDB")


if __name__ == "__main__":
    main()
