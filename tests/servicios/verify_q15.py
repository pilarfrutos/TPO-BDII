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
from scripts.run_query import crear_parser, ejecutar_mongo
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


def verificar_autonoma(db, hoy, ids_rechazo):
    id_venta = "Q15-AUTONOMA"
    fecha_venta = fecha_bson(hoy - timedelta(days=2))
    receta = db.recetas.find_one({"id_receta": "RC006"}, {"_id": 0})
    receta.update(id_receta="Q15-AUT-RECETA", fecha_emision=fecha_venta,
                  estado="Completada", dispensas_realizadas=1)
    db.recetas.insert_one(dict(receta))
    db.ventas.insert_one({
        "id_venta": id_venta, "id_cliente": "C007", "id_farmaceutico": "F006",
        "id_sucursal": "S004", "fecha": fecha_venta,
        "id_receta": receta["id_receta"], "tipo": "Con receta", "medio_pago": "Efectivo",
        "estado": "Completada", "total": 15800, "registro": {"stock_pendiente": True},
    })
    # Preparar los ítems y un lote que estaba vigente en la fecha de la
    # venta, pero ya venció antes de la aplicación autónoma.
    db.detalle_ventas.insert_many([
        {"id_venta": id_venta, "id_detalle": f"{id_venta}-01", "id_producto": "PRD004",
         "cantidad": 1, "precio_unit": 6200},
        {"id_venta": id_venta, "id_detalle": f"{id_venta}-02", "id_producto": "PRD007",
         "cantidad": 2, "precio_unit": 4800},
    ])
    db.stock_lotes.insert_one({
        "id_lote": "AUT-VENCIDO", "nro_lote": "AUT-VENCIDO", "id_sucursal": "S004",
        "id_producto": "PRD007", "unidades": 10,
        "vencimiento": fecha_bson(hoy - timedelta(days=1)),
    })
    ids = [*ids_rechazo, "AUT-VENCIDO"]
    args = crear_parser().parse_args(["q15", "--id-venta", id_venta])
    antes = saldos(db, ids)
    pendiente = estado_venta(db, id_venta)
    with TestCase().assertRaises(ErrorStock) as rechazo:
        ejecutar_mongo(db, args)
    assert rechazo.exception.codigo == "stock_insuficiente"
    assert saldos(db, ids) == antes and estado_venta(db, id_venta) == pendiente

    db.stock_lotes.update_one({"id_lote": "FEFO-SEGUNDO"}, {"$inc": {"unidades": 1}})
    barrera = Barrier(2, timeout=10)

    def aplicar():
        barrera.wait()
        return ejecutar_mongo(db, args)

    reparto = [{"id_producto": "PRD004", "id_lote": "FEFO-PRIMERO", "unidades": 1},
               {"id_producto": "PRD007", "id_lote": "FEFO-SEGUNDO", "unidades": 2}]
    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        llamadas = [ejecutor.submit(aplicar) for _ in range(2)]
        assert [llamada.result() for llamada in llamadas] == [reparto, reparto]
    assert ejecutar_mongo(db, args) == reparto
    despues = saldos(db, ids)
    assert despues == {**antes, "FEFO-PRIMERO": 3, "FEFO-SEGUNDO": 0}
    assert estado_venta(db, id_venta) == {
        **pendiente, "venta": {**pendiente["venta"], "registro": {"descuento": reparto}},
    }
    assert db.recetas.find_one({"id_receta": receta["id_receta"]}, {"_id": 0}) == receta
    return {"id_venta": id_venta, "rechazo": rechazo.exception.codigo,
            "descuento": reparto, "saldos_tras_reintentos": despues}


def verificar(db):
    hoy = hoy_local()
    cargar(db, leer_datos([ORIGINALES_DIR]))

    # Los CSV ya incluyen el efecto de las ventas históricas en el stock.
    with db.client.start_session() as sesion:
        with TestCase().assertRaises(ErrorStock) as rechazo:
            q15(db, "V001", sesion)
        assert rechazo.exception.codigo == "transaccion_requerida"
    for id_venta, codigo in (("V001", "descuento_no_pendiente"), ("V002", "descuento_no_pendiente"),
                             ("V011", "venta_invalida"), ("Q15-AUSENTE", "venta_inexistente")):
        with TestCase().assertRaises(ErrorStock) as rechazo:
            q15(db, id_venta)
        assert rechazo.exception.codigo == codigo

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

    autonoma = verificar_autonoma(db, hoy, ids_rechazo)
    return {"fecha": hoy.isoformat(),
            "exito": {"descuento": reparto, "antes": antes, "despues": despues},
            "rechazo": {**error, "antes": antes_rechazo, "despues": despues_rechazo},
            "concurrencia": {"resultados": resultados, "saldo_final": 3},
            "autonoma": autonoma}


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
    print("q15: OK en MongoDB (descuento integrado y autónomo)")


if __name__ == "__main__":
    main()
