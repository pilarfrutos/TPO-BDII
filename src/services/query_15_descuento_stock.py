from collections import Counter
from datetime import datetime


class ErrorStock(ValueError):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo


def q15(db, id_venta, sesion):
    """Devuelve el reparto por producto y lote dentro de la transacción de q14.

    Usa la fecha y sucursal de la venta. Un lote es utilizable hasta el día de
    su vencimiento inclusive. Si falla, el llamador debe abortar la transacción.
    """
    if sesion is None or not sesion.in_transaction:
        raise ErrorStock("transaccion_requerida", "q15 requiere la transacción activa de q14")
    if not isinstance(id_venta, str) or not id_venta.strip():
        raise ErrorStock("venta_invalida", "id_venta debe ser texto no vacío")

    venta = db.ventas.find_one({"id_venta": id_venta}, session=sesion)
    if venta is None:
        raise ErrorStock("venta_inexistente", f"No existe la venta {id_venta}")
    sucursal = venta.get("id_sucursal")
    fecha = venta.get("fecha")
    if (venta.get("estado") != "Completada" or not isinstance(sucursal, str)
            or not sucursal.strip() or not isinstance(fecha, datetime)):
        raise ErrorStock("venta_invalida",
                         f"La venta {id_venta} debe estar completada y tener sucursal y fecha")

    registro = venta.get("registro", {})
    if "descuento" in registro:
        return registro["descuento"]

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

    reparto = []
    for producto, requerida in sorted(cantidades.items()):
        restante = requerida
        filtro = {"id_sucursal": sucursal, "id_producto": producto,
                  "vencimiento": {"$gte": fecha}, "unidades": {"$gt": 0}}
        lotes = db.stock_lotes.find(filtro, session=sesion).sort([("vencimiento", 1), ("id_lote", 1)])
        with lotes:
            for lote in lotes:
                unidades = min(restante, lote["unidades"])
                cambio = db.stock_lotes.update_one(
                    {"_id": lote["_id"], "unidades": {"$gte": unidades}},
                    {"$inc": {"unidades": -unidades}}, session=sesion)
                if cambio.matched_count != 1:
                    raise ErrorStock("conflicto_stock", f"El lote {lote['id_lote']} cambió durante la venta")
                reparto.append({"id_producto": producto, "id_lote": lote["id_lote"],
                                "unidades": unidades})
                restante -= unidades
                if restante == 0:
                    break
        if restante:
            raise ErrorStock("stock_insuficiente",
                             f"Stock insuficiente de {producto} en {sucursal}: "
                             f"requeridas {requerida}, disponibles {requerida - restante}")

    db.ventas.update_one({"_id": venta["_id"]}, {"$set": {"registro.descuento": reparto}},
                         session=sesion)
    return reparto
