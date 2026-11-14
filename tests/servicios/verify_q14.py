"""Verifica q14 con el descuento real de q15 en una base temporal de MongoDB.

Uso: python tests/servicios/verify_q14.py [--evidencia]
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import json
from pathlib import Path
import sys
from threading import Barrier
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.check_connections import conectar_mongo
from scripts.loaders.load_mongo import cargar
from src.services.query_14_registro_venta import ErrorVenta, q14
from src.services.query_15_descuento_stock import q15
from src.utils.calendario import fecha_bson
from src.utils.datos_csv import ORIGINALES_DIR, leer_datos
from src.utils.reglas_negocio import MAX_ENTERO_BSON

# Día del escenario original, para que los lotes de los CSV sigan siendo utilizables.
HOY = date(2026, 11, 13)
COLECCIONES = ("ventas", "detalle_ventas", "recetas", "stock_lotes", "clientes")


class FalloInyectado(RuntimeError):
    pass


def foto(db):
    return {c: list(db[c].find({}, {"_id": 0}).sort([("_id", 1)])) for c in COLECCIONES}


def venta(db, *args, **kwargs):
    return q14(db, *args, hoy=HOY, **kwargs)


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

    antes = foto(db)
    try:
        q14(db, "Q14-ANTES-EMISION", "C003", "F006", "Efectivo",
            [{"id_producto": "PRD004", "cantidad": 1}], "RC002", hoy=date(2026, 7, 1))
    except ErrorVenta as exc:
        assert exc.codigo == "receta_no_emitida" and foto(db) == antes
        evidencia["rechazos"].append({"codigo": exc.codigo, "mensaje": str(exc)})
    else:
        raise AssertionError("q14 aceptó una venta anterior a la emisión")

    for id_venta, cantidades in (
        ("Q14-SUBTOTAL-GRANDE", [MAX_ENTERO_BSON // 2800 + 1]),
        ("Q14-SUMA-GRANDE", [MAX_ENTERO_BSON // 2800, 1]),
    ):
        evidencia["rechazos"].append(rechazo(
            db, "importe_fuera_de_rango", id_venta, "C001", "F001", "Efectivo",
            [{"id_producto": "PRD001", "cantidad": cantidad} for cantidad in cantidades]))

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

    # Receta simple: se confirman cabecera, detalle, dispensa y descuento real.
    antes_rc006 = receta(db, "RC006")
    antes_l014 = unidades(db, "L014")
    args = ("Q14-V02", "C007", "F006", "Obra social", [{"id_producto": "PRD007", "cantidad": 1}])
    r = venta(db, *args, id_receta="RC006")
    despues_rc006 = receta(db, "RC006")
    assert (despues_rc006["estado"], despues_rc006["dispensas_realizadas"],
            despues_rc006["proxima_dispensa"]) == ("Completada", 1, None)
    cabecera = db.ventas.find_one({"id_venta": "Q14-V02"})
    assert (cabecera["estado"], cabecera["tipo"], cabecera["id_receta"]) == ("Completada", "Con receta", "RC006")
    assert r["descuento"] == cabecera["registro"]["descuento"] == [
        {"id_producto": "PRD007", "id_lote": "L014", "unidades": 1}]
    assert db.detalle_ventas.count_documents({"id_venta": "Q14-V02", "cantidad": 1, "id_producto": "PRD007"}) == 1
    assert unidades(db, "L014") == antes_l014 - 1
    despues = foto(db)
    assert venta(db, *args, id_receta="RC006") == dict(r, repetida=True)
    assert foto(db) == despues
    evidencia["ventas"].append({"resultado": r, "receta": [antes_rc006, despues_rc006],
                                "lotes": {"L014": [antes_l014, unidades(db, "L014")]}})

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
        for c in (0, -1, "2", True, 1.5, MAX_ENTERO_BSON + 1)
    ]
    for n, (codigo, args, kwargs) in enumerate(casos):
        evidencia["rechazos"].append(rechazo(db, codigo, f"Q14-R{n:02d}", *args, **kwargs))

    # Stock insuficiente con receta: se revierten venta, detalle y receta.
    antes_rc002 = receta(db, "RC002")
    evidencia["rechazos"].append(rechazo(
        db, "stock_insuficiente", "Q14-V05", "C003", "F006", "Obra social",
        [{"id_producto": "PRD003", "cantidad": 1}, {"id_producto": "PRD004", "cantidad": 10_000}],
        id_receta="RC002"))
    assert receta(db, "RC002") == antes_rc002
    assert db.ventas.count_documents({"id_venta": "Q14-V05"}) == 0

    # Inyectar fallos en el límite entre q14 y q15, con escrituras reales en la sesión.
    antes_l007 = unidades(db, "L007")

    def fallar_despues_de_receta(db, id_venta, sesion):
        actual = db.recetas.find_one({"id_receta": "RC002"}, session=sesion)
        assert (actual["estado"], actual["dispensas_realizadas"]) == ("Completada", 3)
        assert db.ventas.find_one({"id_venta": id_venta}, session=sesion) is not None
        assert db.detalle_ventas.count_documents({"id_venta": id_venta}, session=sesion) == 1
        raise FalloInyectado("después de actualizar la receta")

    def fallar_despues_de_stock(db, id_venta, sesion):
        assert q15(db, id_venta, sesion) == [
            {"id_producto": "PRD004", "id_lote": "L007", "unidades": 1}]
        assert db.stock_lotes.find_one({"id_lote": "L007"}, session=sesion)["unidades"] == antes_l007 - 1
        raise FalloInyectado("después de descontar el lote con q15")

    for id_venta, fallar in (("Q14-F-RECETA", fallar_despues_de_receta), ("Q14-F-STOCK", fallar_despues_de_stock)):
        error = rechazo(db, FalloInyectado, id_venta, "C003", "F006", "Obra social",
                        [{"id_producto": "PRD004", "cantidad": 1}], id_receta="RC002",
                        descontar_stock=fallar)
        error["receta"] = [antes_rc002, receta(db, "RC002")]
        error["lotes"] = {"L007": [antes_l007, unidades(db, "L007")]}
        evidencia["rechazos"].append(error)

    # Competencia por la última dispensa de RC002 (2/3): solo una venta prospera.
    hilos = 4
    barrera = Barrier(hilos, timeout=10)
    antes_l006 = unidades(db, "L006")

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
    assert unidades(db, "L006") == antes_l006 - 1
    ventas_competidoras = {"id_venta": {"$in": [f"Q14-K{n}" for n in range(hilos)]}}
    assert db.ventas.count_documents(ventas_competidoras) == 1
    assert db.detalle_ventas.count_documents(ventas_competidoras) == 1

    # Reintentos simultáneos de la misma venta: se registra y descuenta una sola vez.
    l001 = unidades(db, "L001")
    barrera = Barrier(hilos, timeout=10)

    def reintentar(_):
        barrera.wait()
        return venta(db, "Q14-V07", "C002", "F001", "Débito", libre)["repetida"]

    with ThreadPoolExecutor(hilos) as ejecutor:
        repetidas = sorted(ejecutor.map(reintentar, range(hilos)))
    assert repetidas == [False] + [True] * (hilos - 1), repetidas
    assert unidades(db, "L001") == l001 - 1
    assert db.detalle_ventas.count_documents({"id_venta": "Q14-V07"}) == 1
    evidencia["concurrencia"] = {
        "ultima_dispensa": {
            "resultados": resultados,
            "dispensas_finales": receta(db, "RC002")["dispensas_realizadas"],
            "ventas_confirmadas": db.ventas.count_documents(ventas_competidoras),
        },
        "reintento_misma_venta": {
            "repetidas": repetidas,
            "detalles_confirmados": db.detalle_ventas.count_documents({"id_venta": "Q14-V07"}),
            "unidades_descontadas": l001 - unidades(db, "L001"),
        },
    }
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
    print("q14 y q15: OK en MongoDB (transacción de venta, receta y stock)")


if __name__ == "__main__":
    main()
