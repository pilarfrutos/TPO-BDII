from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
import sys
from threading import Barrier
from unittest import TestCase
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.check_connections import conectar_mongo
from scripts.loaders.load_mongo import cargar
from src.services.query_14_registro_venta import q14
from src.services.query_15_descuento_stock import ErrorStock, q15
from src.utils.calendario import fecha_bson, hoy_local
from src.utils.datos_csv import ORIGINALES_DIR, leer_datos


def item(producto, cantidad):
    return {"id_producto": producto, "cantidad": cantidad}


def saldos(db, ids):
    return {lote["id_lote"]: lote["unidades"] for lote in db.stock_lotes.find(
        {"id_lote": {"$in": ids}}).sort("id_lote", 1)}


def estado_venta(db, id_venta):
    filtro = {"id_venta": id_venta}
    return {"venta": db.ventas.find_one(filtro, {"_id": 0}),
            "detalles": list(db.detalle_ventas.find(filtro, {"_id": 0}).sort("id_detalle", 1))}


def verificar(db):
    hoy = hoy_local()
    cargar(db, leer_datos([ORIGINALES_DIR]))

    # Los CSV ya incluyen el efecto de las ventas históricas en el stock.
    with db.client.start_session() as sesion:
        with TestCase().assertRaises(ErrorStock) as rechazo:
            q15(db, "V001", sesion)
        assert rechazo.exception.codigo == "transaccion_requerida"
        with sesion.start_transaction():
            with TestCase().assertRaises(ErrorStock) as rechazo:
                q15(db, "V001", sesion)
            assert rechazo.exception.codigo == "venta_invalida"

    # Aislar las existencias que se usan en los escenarios, solo en la base temporal.
    db.stock_lotes.update_many({"$or": [
        {"id_sucursal": "S001", "id_producto": "PRD001"},
        {"id_sucursal": "S004", "id_producto": {"$in": ["PRD004", "PRD007"]}},
    ]}, {"$set": {"unidades": 0}})
    lotes = [
        ("FEFO-B", "PRD001", "S001", 3, 0),
        ("FEFO-A", "PRD001", "S001", 2, 0),
        ("FEFO-00-POSTERIOR", "PRD001", "S001", 8, 3),
        ("FEFO-VENCIDO", "PRD001", "S001", 20, -1),
        ("FEFO-OTRA", "PRD001", "S002", 20, 0),
        ("FEFO-PRIMERO", "PRD004", "S004", 4, 3),
        ("FEFO-SEGUNDO", "PRD007", "S004", 1, 3),
    ]
    db.stock_lotes.insert_many([
        {"id_lote": id_lote, "nro_lote": id_lote, "id_producto": producto,
         "id_sucursal": sucursal, "unidades": unidades, "vencimiento": fecha_bson(hoy + timedelta(dias))}
        for id_lote, producto, sucursal, unidades, dias in lotes
    ])

    ids_fefo = [lote[0] for lote in lotes[:5]] + ["L001"]
    antes = saldos(db, ids_fefo)
    args = ("Q15-OK", "C001", "F001", "Efectivo", [item("PRD001", 1), item("PRD001", 4)])
    resultado = q14(db, *args, hoy=hoy)
    reparto = [{"id_producto": "PRD001", "id_lote": "FEFO-A", "unidades": 2},
               {"id_producto": "PRD001", "id_lote": "FEFO-B", "unidades": 3}]
    despues = saldos(db, ids_fefo)
    assert resultado["descuento"] == reparto and resultado["repetida"] is False
    assert despues == {**antes, "FEFO-A": 0, "FEFO-B": 0}
    registrada = estado_venta(db, args[0])
    assert registrada["venta"]["registro"]["descuento"] == reparto
    assert len(registrada["detalles"]) == 2

    assert q14(db, *args, hoy=hoy) == dict(resultado, repetida=True)
    with db.client.start_session() as sesion:
        with sesion.start_transaction():
            assert q15(db, args[0], sesion) == reparto
    assert saldos(db, ids_fefo) == despues and estado_venta(db, args[0]) == registrada

    ids_rechazo = ["FEFO-PRIMERO", "FEFO-SEGUNDO", "L007", "L014"]
    filtro_receta = {"id_receta": "RC006"}

    def foto_rechazo():
        return {**estado_venta(db, "Q15-SIN-STOCK"), "lotes": saldos(db, ids_rechazo),
                "receta": db.recetas.find_one(filtro_receta, {"_id": 0})}

    antes_rechazo = foto_rechazo()
    try:
        q14(db, "Q15-SIN-STOCK", "C007", "F006", "Efectivo",
            [item("PRD004", 2), item("PRD007", 2)], id_receta="RC006", hoy=hoy)
    except ErrorStock as exc:
        assert exc.codigo == "stock_insuficiente"
        assert str(exc) == "Stock insuficiente de PRD007 en S004: requeridas 2, disponibles 1"
        error = {"codigo": exc.codigo, "mensaje": str(exc)}
    else:
        raise AssertionError("La venta debió fallar por stock insuficiente del segundo producto")
    despues_rechazo = foto_rechazo()
    assert despues_rechazo == antes_rechazo

    # Dos ventas por 5 unidades compiten por las 8 del lote restante.
    barrera = Barrier(2, timeout=10)

    def competir(id_venta):
        barrera.wait()
        try:
            q14(db, id_venta, "C001", "F001", "Efectivo", [item("PRD001", 5)], hoy=hoy)
            return id_venta, "ok"
        except ErrorStock as exc:
            return id_venta, exc.codigo

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = dict(ejecutor.map(competir, ("Q15-C1", "Q15-C2")))
    assert sorted(resultados.values()) == ["ok", "stock_insuficiente"], resultados
    assert saldos(db, ids_fefo) == {**despues, "FEFO-00-POSTERIOR": 3}
    for id_venta, estado in resultados.items():
        guardada = estado_venta(db, id_venta)
        prospero = estado == "ok"
        assert (guardada["venta"] is not None) == prospero
        assert len(guardada["detalles"]) == int(prospero)

    return {"fecha": hoy.isoformat(),
            "exito": {"descuento": reparto, "antes": antes, "despues": despues},
            "rechazo": {**error, "antes": antes_rechazo, "despues": despues_rechazo},
            "concurrencia": {"resultados": resultados, "saldo_final": 3}}


def main():
    cliente, _ = conectar_mongo()
    nombre = f"farmared_test_q15_{uuid4().hex}"
    with cliente:
        try:
            evidencia = verificar(cliente[nombre])
        finally:
            cliente.drop_database(nombre)
    if "--evidencia" in sys.argv:
        print(json.dumps(evidencia, ensure_ascii=False, indent=2, default=lambda fecha: fecha.date().isoformat()))
    print("q15: OK en MongoDB (descuento real desde q14)")


if __name__ == "__main__":
    main()
