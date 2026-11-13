"""Verifica q14 (registro de venta) en una base temporal que se elimina al final.

Uso: python tests/servicios/verify_q14.py [--evidencia]

Mientras q15 (T12) no esté disponible, el descuento de stock se reemplaza por
`descuento_de_prueba`: toma cada producto de un único lote de la sucursal con
unidades suficientes. Solo sirve para comprobar que q14 invoca el descuento en
su transacción y revierte todo si falla; el FEFO real se prueba en T12/T14.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
import sys
from threading import Barrier
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.check_connections import conectar_mongo
from scripts.loaders.load_mongo import cargar
from src.services.query_14_registro_venta import ErrorVenta, q14
from src.utils.calendario import fecha_bson, hoy_local
from src.utils.datos_csv import ORIGINALES_DIR, leer_datos

HOY = hoy_local()
COLECCIONES = ("ventas", "detalle_ventas", "recetas", "stock_lotes", "clientes")


class StockInsuficiente(Exception):
    pass


def descuento_de_prueba(db, id_venta, sesion):
    venta = db.ventas.find_one({"id_venta": id_venta}, session=sesion)
    reparto = []
    for detalle in db.detalle_ventas.find({"id_venta": id_venta}, session=sesion):
        lote = db.stock_lotes.find_one_and_update(
            {"id_sucursal": venta["id_sucursal"], "id_producto": detalle["id_producto"],
             "unidades": {"$gte": detalle["cantidad"]}},
            {"$inc": {"unidades": -detalle["cantidad"]}}, sort=[("id_lote", 1)], session=sesion)
        if lote is None:
            raise StockInsuficiente(f"Sin stock de {detalle['id_producto']} en {venta['id_sucursal']}")
        reparto.append({"id_producto": detalle["id_producto"], "id_lote": lote["id_lote"],
                        "unidades": detalle["cantidad"]})
    return reparto


def foto(db):
    return {c: list(db[c].find({}, {"_id": 0}).sort([("_id", 1)])) for c in COLECCIONES}


def venta(db, *args, **kwargs):
    kwargs.setdefault("hoy", HOY)
    kwargs.setdefault("descontar_stock", descuento_de_prueba)
    return q14(db, *args, **kwargs)


def rechazo(db, error, *args, **kwargs):
    """La llamada debe fallar con `error` (código o excepción) sin dejar cambios."""
    antes = foto(db)
    try:
        venta(db, *args, **kwargs)
    except Exception as exc:
        codigo = getattr(exc, "codigo", type(exc).__name__)
        assert error in (codigo, type(exc)), f"{args}: {codigo} ({exc}), se esperaba {error}"
        assert foto(db) == antes, f"{args}: el rechazo dejó cambios"
        return {"argumentos": [a for a in args], "codigo": codigo, "mensaje": str(exc)}
    raise AssertionError(f"{args}: se esperaba el rechazo {error}")


def unidades(db, id_lote):
    return db.stock_lotes.find_one({"id_lote": id_lote})["unidades"]


def receta(db, id_receta):
    return db.recetas.find_one({"id_receta": id_receta}, {"_id": 0})


def verificar(db):
    cargar(db, leer_datos([ORIGINALES_DIR]))
    evidencia = {"ventas": [], "rechazos": []}
    productos = {p["id_producto"]: p for p in db.productos.find()}

    # Venta libre: precio de lista vigente, total calculado, stock descontado.
    l001, l013 = unidades(db, "L001"), unidades(db, "L013")
    r = venta(db, "Q14-V01", "C001", "F001", "Efectivo",
              [{"id_producto": "PRD001", "cantidad": 2}, {"id_producto": "PRD011", "cantidad": 1}])
    assert r["total"] == 2 * productos["PRD001"]["precio_unit"] + productos["PRD011"]["precio_unit"]
    assert r["repetida"] is False and r["receta"] is None and r["fecha"] == fecha_bson(HOY)
    cabecera = db.ventas.find_one({"id_venta": "Q14-V01"})
    assert (cabecera["estado"], cabecera["tipo"], cabecera["id_sucursal"]) == (
        "Completada", "Venta libre", "S001")
    detalle = list(db.detalle_ventas.find({"id_venta": "Q14-V01"}).sort("id_detalle", 1))
    assert [(d["id_detalle"], d["precio_unit"]) for d in detalle] == [
        ("Q14-V01-01", 2800), ("Q14-V01-02", 2200)]
    assert (unidades(db, "L001"), unidades(db, "L013")) == (l001 - 2, l013 - 1)
    evidencia["ventas"].append({"resultado": r, "lotes": {"L001": [l001, l001 - 2],
                                                          "L013": [l013, l013 - 1]}})

    # Reintento con los mismos argumentos: mismo resultado, sin segundo descuento.
    antes = foto(db)
    repetida = venta(db, "Q14-V01", "C001", "F001", "Efectivo",
                     [{"id_producto": "PRD001", "cantidad": 2},
                      {"id_producto": "PRD011", "cantidad": 1}])
    assert repetida == dict(r, repetida=True) and foto(db) == antes
    evidencia["rechazos"].append(rechazo(db, "conflicto", "Q14-V01", "C001", "F001", "Débito",
                                         [{"id_producto": "PRD001", "cantidad": 2},
                                          {"id_producto": "PRD011", "cantidad": 1}]))
    rechazo(db, "conflicto", "V001", "C004", "F003", "Efectivo",
            [{"id_producto": "PRD001", "cantidad": 1}])  # ID de una venta histórica

    # Receta simple: se completa con su única dispensa.
    antes_rc006 = receta(db, "RC006")
    r = venta(db, "Q14-V02", "C007", "F006", "Obra social",
              [{"id_producto": "PRD007", "cantidad": 1}], id_receta="RC006")
    despues_rc006 = receta(db, "RC006")
    assert (despues_rc006["estado"], despues_rc006["dispensas_realizadas"],
            despues_rc006["proxima_dispensa"]) == ("Completada", 1, None)
    assert db.ventas.find_one({"id_venta": "Q14-V02"})["tipo"] == "Con receta"
    evidencia["ventas"].append({"resultado": r, "receta": [antes_rc006, despues_rc006]})

    # Tratamiento prolongado 1/3 con un producto de venta libre: 2/3 y próxima a 30 días.
    antes_rc004 = receta(db, "RC004")
    r = venta(db, "Q14-V03", "C006", "F002", "Obra social",
              [{"id_producto": "PRD006", "cantidad": 1}, {"id_producto": "PRD001", "cantidad": 1},
               {"id_producto": "PRD006", "cantidad": 1}], id_receta="RC004")
    despues_rc004 = receta(db, "RC004")
    assert (despues_rc004["estado"], despues_rc004["dispensas_realizadas"],
            despues_rc004["proxima_dispensa"].date()) == ("Vigente", 2, HOY + timedelta(30))
    assert db.detalle_ventas.count_documents({"id_venta": "Q14-V03"}) == 3
    evidencia["ventas"].append({"resultado": r, "receta": [antes_rc004, despues_rc004]})

    # Tratamiento prolongado en la última dispensa: se completa y se vacía la fecha.
    antes_rc003 = receta(db, "RC003")
    r = venta(db, "Q14-V04", "C006", "F003", "Obra social",
              [{"id_producto": "PRD005", "cantidad": 3}], id_receta="RC003")
    despues_rc003 = receta(db, "RC003")
    assert (despues_rc003["estado"], despues_rc003["dispensas_realizadas"],
            despues_rc003["proxima_dispensa"]) == ("Completada", 3, None)
    evidencia["ventas"].append({"resultado": r, "receta": [antes_rc003, despues_rc003]})

    # Rechazos de validación: ninguno deja venta, detalle, receta ni stock modificados.
    libre = [{"id_producto": "PRD001", "cantidad": 1}]
    casos = [
        ("cliente_inexistente", ("C999", "F001", "Efectivo", libre), {}),
        ("cliente_inactivo", ("C008", "F001", "Efectivo", libre), {}),
        ("farmaceutico_inexistente", ("C001", "F999", "Efectivo", libre), {}),
        ("farmaceutico_inactivo", ("C001", "F004", "Efectivo", libre), {}),
        ("sucursal_no_farmacia", ("C001", "F007", "Efectivo", libre), {}),
        ("producto_inexistente", ("C001", "F001", "Efectivo", [{"id_producto": "PRD999",
                                                                 "cantidad": 1}]), {}),
        ("producto_inactivo", ("C001", "F001", "Efectivo", [{"id_producto": "PRD012",
                                                              "cantidad": 1}]), {}),
        ("receta_requerida", ("C001", "F001", "Efectivo", [{"id_producto": "PRD003",
                                                             "cantidad": 1}]), {}),
        ("receta_ajena", ("C001", "F006", "Obra social", [{"id_producto": "PRD003",
                                                            "cantidad": 1}]),
         {"id_receta": "RC002"}),
        ("receta_no_vigente", ("C001", "F001", "Obra social", [{"id_producto": "PRD003",
                                                                 "cantidad": 1}]),
         {"id_receta": "RC001"}),  # Completada
        ("receta_no_vigente", ("C002", "F005", "Obra social", [{"id_producto": "PRD003",
                                                                 "cantidad": 1}]),
         {"id_receta": "RC009"}),  # Vencida
        ("receta_no_vigente", ("C006", "F003", "Obra social", [{"id_producto": "PRD005",
                                                                 "cantidad": 1}]),
         {"id_receta": "RC003"}),  # Completada por Q14-V04
        ("receta_inexistente", ("C001", "F001", "Obra social", [{"id_producto": "PRD003",
                                                                  "cantidad": 1}]),
         {"id_receta": "RC999"}),
        ("datos_invalidos", ("C003", "F006", "Obra social", libre), {"id_receta": "RC002"}),
        ("datos_invalidos", ("C001", "F001", "Bitcoin", libre), {}),
        ("datos_invalidos", ("C001", "F001", "Efectivo", []), {}),
    ] + [
        ("datos_invalidos", ("C001", "F001", "Efectivo", [{"id_producto": "PRD001",
                                                            "cantidad": c}]), {})
        for c in (0, -1, "2", True, 1.5)
    ]
    for n, (codigo, args, kwargs) in enumerate(casos):
        evidencia["rechazos"].append(rechazo(db, codigo, f"Q14-R{n:02d}", *args, **kwargs))

    # Stock insuficiente con receta: se revierten venta, detalle y receta.
    antes_rc002 = receta(db, "RC002")
    evidencia["rechazos"].append(rechazo(
        db, StockInsuficiente, "Q14-V05", "C003", "F006", "Obra social",
        [{"id_producto": "PRD004", "cantidad": 1}, {"id_producto": "PRD003", "cantidad": 10_000}],
        id_receta="RC002"))
    assert receta(db, "RC002") == antes_rc002
    assert db.ventas.count_documents({"id_venta": "Q14-V05"}) == 0

    # Fallo inyectado después de descontar un lote: el lote vuelve a su valor.
    def descuento_que_falla(db, id_venta, sesion):
        descuento_de_prueba(db, id_venta, sesion)
        raise RuntimeError("fallo inyectado después de modificar lotes")

    rechazo(db, RuntimeError, "Q14-V06", "C003", "F006", "Obra social",
            [{"id_producto": "PRD004", "cantidad": 1}], id_receta="RC002",
            descontar_stock=descuento_que_falla)
    assert receta(db, "RC002") == antes_rc002

    # Competencia por la última dispensa de RC002 (2/3): solo una venta prospera.
    hilos = 4
    barrera = Barrier(hilos)

    def competir(n):
        barrera.wait()
        try:
            venta(db, f"Q14-K{n}", "C003", "F006", "Obra social",
                  [{"id_producto": "PRD003", "cantidad": 1}], id_receta="RC002")
            return "ok"
        except ErrorVenta as exc:
            return exc.codigo

    with ThreadPoolExecutor(hilos) as ejecutor:
        resultados = sorted(ejecutor.map(competir, range(hilos)))
    assert resultados == ["ok"] + ["receta_no_vigente"] * (hilos - 1), resultados
    assert receta(db, "RC002")["dispensas_realizadas"] == 3

    # Reintentos simultáneos de la misma venta: se registra y descuenta una sola vez.
    l001 = unidades(db, "L001")
    barrera = Barrier(hilos)

    def reintentar(_):
        barrera.wait()
        return venta(db, "Q14-V07", "C002", "F001", "Débito", libre)["repetida"]

    with ThreadPoolExecutor(hilos) as ejecutor:
        repetidas = sorted(ejecutor.map(reintentar, range(hilos)))
    assert repetidas == [False] + [True] * (hilos - 1), repetidas
    assert unidades(db, "L001") == l001 - 1
    assert db.detalle_ventas.count_documents({"id_venta": "Q14-V07"}) == 1
    return evidencia


def a_json(valor):
    return valor.date().isoformat() if hasattr(valor, "date") else str(valor)


def main():
    cliente, _ = conectar_mongo()
    nombre = f"farmared_test_q14_{uuid4().hex}"
    with cliente:
        try:
            evidencia = verificar(cliente[nombre])
        finally:
            cliente.drop_database(nombre)
    if "--evidencia" in sys.argv:
        print(json.dumps(evidencia, ensure_ascii=False, indent=2, default=a_json))
    print("q14: OK en MongoDB (con descuento de stock de prueba)")


if __name__ == "__main__":
    main()
