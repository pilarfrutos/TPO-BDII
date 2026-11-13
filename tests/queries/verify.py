from datetime import date
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.check_connections import conectar_mongo
from scripts.loaders.load_mongo import cargar
from scripts.run_query import a_json
from src.services.query_01_productos_activos import q01
from src.services.query_07_productos_mas_vendidos import q07
from src.services.query_08_stock_bajo import q08
from src.services.query_11_ingresos_por_farmaceutico import q11
from src.utils.datos_csv import ORIGINALES_DIR, leer_datos, para_mongo


def verificar(db):
    # Los resultados esperados se basan en los CSV originales y los casos de prueba.
    datos = leer_datos([ORIGINALES_DIR])
    cargar(db, datos)
    cargar(db, datos)

    productos = {p["id_producto"]: p for p in datos["productos"] if p["activo"]}
    proveedores = {p["id_proveedor"]: p for p in datos["proveedores"]}
    id_proveedor = productos["PRD001"]["id_proveedor"]
    db.proveedores.update_one({"id_proveedor": id_proveedor}, {"$set": {"activo": False}})
    proveedores[id_proveedor]["activo"] = False
    activos = q01(db)
    assert activos == [
        dict(p, proveedor=proveedores[p["id_proveedor"]])
        for p in sorted(productos.values(), key=lambda p: p["id_producto"])
    ], "q01 debe incluir al proveedor completo, aun si está inactivo"

    ranking = q07(db)
    assert [(p["id_producto"], p["unidades"]) for p in ranking] == [
        ("PRD005", 6), ("PRD011", 5), ("PRD001", 4), ("PRD004", 3), ("PRD009", 2)
    ], "q07 debe contar solo las unidades de ventas completadas"

    lote = datos["stock_lotes"][0]
    db.stock_lotes.insert_many([para_mongo(dict(lote, id_lote=f"TEST-{n}", unidades=n))
                                for n in (49, 50)])
    lotes = {l["id_lote"]: l for l in q08(db)}
    assert "TEST-49" in lotes and "TEST-50" not in lotes
    assert "L018" in lotes, "q08 incluye lotes vencidos y productos inactivos"
    assert lotes["TEST-49"]["producto"]["id_producto"] == lote["id_producto"]
    assert lotes["TEST-49"]["sucursal"]["id_sucursal"] == lote["id_sucursal"]
    assert lotes["TEST-49"]["proveedor"]["id_proveedor"] == id_proveedor

    producto = productos["PRD003"]
    precio = producto["precio_unit"]
    for dia in (date(2026, 10, 1), date(2026, 11, 1)):
        id_venta = f"TEST-{dia.isoformat()}"
        db.ventas.insert_one(para_mongo(dict(
            id_venta=id_venta, id_cliente="C001", id_farmaceutico="F001", id_receta=None,
            fecha=dia, tipo="Venta libre", medio_pago="Efectivo", total=precio, estado="Completada",
        )))
        db.detalle_ventas.insert_one(dict(
            id_detalle=id_venta, id_venta=id_venta, id_producto="PRD003", cantidad=1, precio_unit=precio,
        ))
    assert [(p["id_producto"], p["unidades"]) for p in q07(db)] == [
        ("PRD005", 6), ("PRD011", 5), ("PRD001", 4), ("PRD003", 3), ("PRD004", 3)
    ], "q07 debe desempatar por ID y limitar a cinco"
    dia_de_prueba = date(2026, 10, 20)
    ingresos = q11(db, hoy=dia_de_prueba)
    assert {p["id_farmaceutico"]: p["ingresos"] for p in ingresos} == {
        "F001": 4400 + precio, "F002": 7800, "F003": 7100, "F005": 4600,
    }, "q11 incluye el primer día del mes y excluye ventas pendientes y del mes siguiente"
    assert q11(db, hoy=date(2026, 12, 15)) == []
    return {
        "q01": {"cantidad": len(activos), "ejemplo": activos[0]},
        "q07": ranking,
        "q08": {"lote_vencido": lotes["L018"], "lote_con_49": lotes["TEST-49"],
                "incluye_lote_con_50": "TEST-50" in lotes},
        "q11": {"hoy_de_prueba": dia_de_prueba.isoformat(), "ingresos": ingresos},
    }


def main():
    cliente, _ = conectar_mongo()
    nombre = f"farmared_test_consultas_{uuid4().hex}"
    with cliente:
        try:
            evidencia = verificar(cliente[nombre])
        finally:
            cliente.drop_database(nombre)
    if "--evidencia" in sys.argv:
        print(json.dumps(evidencia, ensure_ascii=False, indent=2, default=a_json))
    print("q01, q07, q08 y q11: OK en MongoDB")


if __name__ == "__main__":
    main()
