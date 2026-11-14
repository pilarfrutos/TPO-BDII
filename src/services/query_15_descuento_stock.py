from collections import Counter
from datetime import datetime

from src.utils.calendario import fecha_bson, hoy_local


class ErrorStock(ValueError):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo


def q15(db, id_venta, sesion=None):
    """Aplica FEFO en MongoDB a una venta completada con stock pendiente.

    Recibe la base, el ID y, opcionalmente, la transacción activa de q14.
    Devuelve el reparto por producto y lote y lo reutiliza en los reintentos.
    Una venta por procesar debe tener `registro.stock_pendiente = True`, su
    sucursal histórica, su fecha y sus detalles. Los lotes son utilizables
    hasta el día de su vencimiento inclusive.

    En modo autónomo abre una transacción y verifica la vigencia al día de
    aplicación. Con la sesión de q14 usa la fecha de la operación y propaga
    cualquier fallo al dueño de la transacción para que la revierta.
    """
    if not isinstance(id_venta, str) or not id_venta.strip():
        raise ErrorStock("venta_invalida", "id_venta debe ser texto no vacío")
    if sesion is None:
        fecha_aplicacion = fecha_bson(hoy_local())
        with db.client.start_session() as propia:
            return propia.with_transaction(
                lambda activa: _descontar(activa, db, id_venta, fecha_aplicacion))
    if not sesion.in_transaction:
        raise ErrorStock("transaccion_requerida", "La sesión recibida debe tener una transacción activa")
    return _descontar(sesion, db, id_venta, None)


def _descontar(sesion, db, id_venta, fecha_aplicacion):
    venta = db.ventas.find_one({"id_venta": id_venta}, session=sesion)
    if venta is None:
        raise ErrorStock("venta_inexistente", f"No existe la venta {id_venta}")
    if venta.get("estado") != "Completada":
        raise ErrorStock("venta_invalida", f"La venta {id_venta} debe estar completada")
    registro = venta.get("registro", {})
    if "descuento" in registro:
        return registro["descuento"]
    if registro.get("stock_pendiente") is not True:
        raise ErrorStock("descuento_no_pendiente",
                         f"La venta {id_venta} no está marcada para descontar stock")

    sucursal = venta.get("id_sucursal")
    fecha = venta.get("fecha")
    if not isinstance(sucursal, str) or not sucursal.strip() or not isinstance(fecha, datetime):
        raise ErrorStock("venta_invalida",
                         f"La venta {id_venta} debe tener sucursal y fecha")
    # Un cliente PyMongo puede devolver la fecha BSON con o sin información UTC.
    if fecha_aplicacion is not None and fecha_aplicacion.date() > fecha.date():
        fecha = fecha_aplicacion

    cantidades = Counter()
    for detalle in db.detalle_ventas.find({"id_venta": id_venta}, session=sesion):
        producto = detalle.get("id_producto")
        cantidad = detalle.get("cantidad")
        if (not isinstance(producto, str) or not producto.strip()
                or not isinstance(cantidad, int) or isinstance(cantidad, bool) or cantidad <= 0):
            raise ErrorStock("venta_invalida", f"La venta {id_venta} tiene un detalle inválido")
        cantidades[producto] += cantidad
    if not cantidades:
        raise ErrorStock("venta_invalida", f"La venta {id_venta} no tiene detalles")

    asignaciones = []
    for producto, requerida in sorted(cantidades.items()):
        restante = requerida
        filtro = {"id_sucursal": sucursal, "id_producto": producto,
                  "vencimiento": {"$gte": fecha}, "unidades": {"$gt": 0}}
        lotes = db.stock_lotes.find(filtro, session=sesion).sort([("vencimiento", 1), ("id_lote", 1)])
        with lotes:
            for lote in lotes:
                unidades = min(restante, lote["unidades"])
                asignaciones.append((lote["_id"], {"id_producto": producto,
                                                    "id_lote": lote["id_lote"],
                                                    "unidades": unidades}))
                restante -= unidades
                if restante == 0:
                    break
        if restante:
            raise ErrorStock("stock_insuficiente",
                             f"Stock insuficiente de {producto} en {sucursal}: "
                             f"requeridas {requerida}, disponibles {requerida - restante}")

    for id_lote, item in asignaciones:
        unidades = item["unidades"]
        cambio = db.stock_lotes.update_one(
            {"_id": id_lote, "unidades": {"$gte": unidades}},
            {"$inc": {"unidades": -unidades}}, session=sesion)
        if cambio.matched_count != 1:
            raise ErrorStock("conflicto_stock", f"El lote {item['id_lote']} cambió durante la venta")
    reparto = [item for _, item in asignaciones]
    db.ventas.update_one(
        {"_id": venta["_id"]},
        {"$set": {"registro.descuento": reparto}, "$unset": {"registro.stock_pendiente": ""}},
        session=sesion)
    return reparto
