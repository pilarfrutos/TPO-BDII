"""q14 · Registro de una venta 'Completada' validada, en una transacción MongoDB.

    q14(db, id_venta, id_cliente, id_farmaceutico, medio_pago, items, id_receta=None)

`items` es una lista de {"id_producto", "cantidad"}. En una misma transacción:
1. Valida cliente existente y activo; farmacéutico existente y activo, de una
   sucursal activa de tipo 'Farmacia'; productos existentes y activos;
   cantidades enteras positivas.
2. Si algún producto es 'Bajo receta' o 'Bajo receta archivada', exige una
   receta del mismo cliente en estado 'Vigente' con dispensas disponibles.
3. Inserta la cabecera y el detalle con el precio de lista vigente; el total es
   la suma de cantidad × precio.
4. Registra una dispensa en la receta (una por venta, no por ítem). Simple y
   Archivada se completan; Tratamiento prolongado fija la próxima dispensa a
   30 días, o se completa y la vacía al llegar al límite.
5. Invoca q15 con la misma sesión para descontar el stock (FEFO). Si q15 o
   cualquier paso falla, la transacción aborta: no queda venta, detalle,
   receta ni lote modificado.

Reintentos: `id_venta` es la clave de idempotencia. Repetir la llamada con los
mismos argumentos devuelve el resultado ya registrado, sin otro descuento;
repetirla con otros argumentos se rechaza con `conflicto`.

Devuelve {"id_venta", "fecha", "total", "id_receta", "receta", "descuento",
"repetida"}. Los rechazos de validación lanzan ErrorVenta con un `codigo`; los
de stock los lanza q15 y se propagan sin cambios.
"""
from datetime import timedelta

from src.utils.calendario import fecha_bson, hoy_local

MEDIOS_PAGO = {"Efectivo", "Débito", "Crédito", "Transferencia", "Obra social"}
BAJO_RECETA = {"Bajo receta", "Bajo receta archivada"}
DIAS_ENTRE_DISPENSAS = 30


class ErrorVenta(ValueError):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo


def _descuento_q15():
    # q15 (T12) vive en su propio módulo; se importa al usarse para no acoplar la carga.
    from src.services.query_15_descuento_stock import q15
    return q15


def _texto(campo, valor):
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorVenta("datos_invalidos", f"{campo}: se esperaba texto no vacío")
    return valor.strip()


def _normalizar(id_venta, id_cliente, id_farmaceutico, medio_pago, items, id_receta):
    solicitud = {
        "id_venta": _texto("id_venta", id_venta),
        "id_cliente": _texto("id_cliente", id_cliente),
        "id_farmaceutico": _texto("id_farmaceutico", id_farmaceutico),
        "medio_pago": _texto("medio_pago", medio_pago),
        "id_receta": None if id_receta in (None, "") else _texto("id_receta", id_receta),
    }
    if solicitud["medio_pago"] not in MEDIOS_PAGO:
        raise ErrorVenta("datos_invalidos",
                         f"medio_pago: debe ser uno de {', '.join(sorted(MEDIOS_PAGO))}")
    if not isinstance(items, (list, tuple)) or not items:
        raise ErrorVenta("datos_invalidos", "items: se esperaba al menos un ítem")
    normalizados = []
    for n, item in enumerate(items, 1):
        if not isinstance(item, dict) or set(item) != {"id_producto", "cantidad"}:
            raise ErrorVenta("datos_invalidos",
                             f"items[{n}]: se esperaba {{'id_producto', 'cantidad'}}")
        cantidad = item["cantidad"]
        if not isinstance(cantidad, int) or isinstance(cantidad, bool) or cantidad <= 0:
            raise ErrorVenta("datos_invalidos", f"items[{n}].cantidad: se esperaba un entero positivo")
        normalizados.append({"id_producto": _texto(f"items[{n}].id_producto", item["id_producto"]),
                             "cantidad": cantidad})
    solicitud["items"] = normalizados
    return solicitud


def _validar_y_preparar(db, sesion, solicitud):
    """Lee las entidades dentro de la transacción y devuelve los productos por ID."""
    cliente = db.clientes.find_one({"id_cliente": solicitud["id_cliente"]}, session=sesion)
    if cliente is None:
        raise ErrorVenta("cliente_inexistente", f"No existe el cliente {solicitud['id_cliente']}")
    if not cliente["activo"]:
        raise ErrorVenta("cliente_inactivo", f"El cliente {solicitud['id_cliente']} está dado de baja")

    farmaceutico = db.farmaceuticos.find_one({"id_farmaceutico": solicitud["id_farmaceutico"]},
                                             session=sesion)
    if farmaceutico is None:
        raise ErrorVenta("farmaceutico_inexistente",
                         f"No existe el farmacéutico {solicitud['id_farmaceutico']}")
    if not farmaceutico["activo"]:
        raise ErrorVenta("farmaceutico_inactivo",
                         f"El farmacéutico {solicitud['id_farmaceutico']} no está activo")
    sucursal = db.sucursales.find_one({"id_sucursal": farmaceutico["id_sucursal"]}, session=sesion)
    if sucursal is None or sucursal["tipo"] != "Farmacia":
        raise ErrorVenta("sucursal_no_farmacia",
                         f"El farmacéutico {solicitud['id_farmaceutico']} trabaja en "
                         f"{farmaceutico['id_sucursal']}, que no es una Farmacia")
    if not sucursal["activo"]:
        raise ErrorVenta("sucursal_inactiva", f"La sucursal {sucursal['id_sucursal']} no está activa")

    ids = sorted({i["id_producto"] for i in solicitud["items"]})
    productos = {p["id_producto"]: p for p in db.productos.find(
        {"id_producto": {"$in": ids}}, session=sesion)}
    for id_producto in ids:
        if id_producto not in productos:
            raise ErrorVenta("producto_inexistente", f"No existe el producto {id_producto}")
        if not productos[id_producto]["activo"]:
            raise ErrorVenta("producto_inactivo", f"El producto {id_producto} está discontinuado")

    con_receta = sorted(i for i in ids if productos[i]["condicion_venta"] in BAJO_RECETA)
    receta = None
    if con_receta and solicitud["id_receta"] is None:
        raise ErrorVenta("receta_requerida",
                         f"{', '.join(con_receta)} requiere(n) una receta vigente del cliente")
    if solicitud["id_receta"] is not None:
        if not con_receta:
            raise ErrorVenta("datos_invalidos",
                             "id_receta: la venta no incluye productos bajo receta")
        receta = db.recetas.find_one({"id_receta": solicitud["id_receta"]}, session=sesion)
        if receta is None:
            raise ErrorVenta("receta_inexistente", f"No existe la receta {solicitud['id_receta']}")
        if receta["id_cliente"] != solicitud["id_cliente"]:
            raise ErrorVenta("receta_ajena",
                             f"La receta {receta['id_receta']} es de otro cliente")
        if receta["estado"] != "Vigente":
            raise ErrorVenta("receta_no_vigente",
                             f"La receta {receta['id_receta']} está {receta['estado']}")
        if receta["dispensas_realizadas"] >= receta["dispensas_autorizadas"]:
            raise ErrorVenta("receta_no_vigente",
                             f"La receta {receta['id_receta']} no tiene dispensas disponibles")
    return farmaceutico, productos, receta


def _dispensar(db, sesion, receta, hoy):
    """Registra una dispensa; el filtro evita aplicarla sobre un estado distinto al leído."""
    realizadas = receta["dispensas_realizadas"] + 1
    prolongado = receta["tipo"] == "Tratamiento prolongado"
    completa = not prolongado or realizadas >= receta["dispensas_autorizadas"]
    cambios = {
        "dispensas_realizadas": realizadas,
        "estado": "Completada" if completa else "Vigente",
        "proxima_dispensa": None if completa else fecha_bson(hoy + timedelta(DIAS_ENTRE_DISPENSAS)),
    }
    resultado = db.recetas.update_one(
        {"id_receta": receta["id_receta"], "estado": "Vigente",
         "dispensas_realizadas": receta["dispensas_realizadas"]},
        {"$set": cambios}, session=sesion)
    if resultado.matched_count != 1:
        raise ErrorVenta("conflicto", f"La receta {receta['id_receta']} cambió durante la venta")
    return {"id_receta": receta["id_receta"], **cambios}


def _resultado(venta, repetida):
    return {"id_venta": venta["id_venta"], "fecha": venta["fecha"], "total": venta["total"],
            "id_receta": venta["id_receta"], "receta": venta["registro"]["receta"],
            "descuento": venta["registro"]["descuento"], "repetida": repetida}


def _repetida(db, sesion, solicitud):
    """Devuelve el resultado previo si la venta ya existe con la misma solicitud."""
    venta = db.ventas.find_one({"id_venta": solicitud["id_venta"]}, session=sesion)
    if venta is None:
        return None
    if venta.get("registro", {}).get("solicitud") != solicitud:
        raise ErrorVenta("conflicto",
                         f"La venta {solicitud['id_venta']} ya existe con otros datos")
    return _resultado(venta, repetida=True)


def q14(db, id_venta, id_cliente, id_farmaceutico, medio_pago, items, id_receta=None, *,
        hoy=None, descontar_stock=None):
    """Registra la venta y devuelve su resultado (ver docstring del módulo).

    `hoy` permite fijar el día de negocio en pruebas; por defecto es el día
    actual en Buenos Aires, calculado una sola vez aunque el driver reintente.
    `descontar_stock` reemplaza a q15 en pruebas; recibe (db, id_venta, sesion).
    """
    from pymongo.errors import DuplicateKeyError

    solicitud = _normalizar(id_venta, id_cliente, id_farmaceutico, medio_pago, items, id_receta)
    hoy = hoy if hoy is not None else hoy_local()
    descontar_stock = descontar_stock or _descuento_q15()

    def registrar(sesion):
        previa = _repetida(db, sesion, solicitud)
        if previa is not None:
            return previa
        farmaceutico, productos, receta = _validar_y_preparar(db, sesion, solicitud)
        detalle = [
            {"id_detalle": f"{solicitud['id_venta']}-{n:02d}", "id_venta": solicitud["id_venta"],
             "id_producto": item["id_producto"], "cantidad": item["cantidad"],
             "precio_unit": productos[item["id_producto"]]["precio_unit"]}
            for n, item in enumerate(solicitud["items"], 1)
        ]
        venta = {
            "id_venta": solicitud["id_venta"], "id_cliente": solicitud["id_cliente"],
            "id_farmaceutico": solicitud["id_farmaceutico"], "id_receta": solicitud["id_receta"],
            "fecha": fecha_bson(hoy), "tipo": "Con receta" if receta else "Venta libre",
            "medio_pago": solicitud["medio_pago"],
            "total": sum(d["cantidad"] * d["precio_unit"] for d in detalle),
            "estado": "Completada",
            # Sucursal de la operación, para no depender de la asignación futura (q10).
            "id_sucursal": farmaceutico["id_sucursal"],
        }
        db.ventas.insert_one(dict(venta), session=sesion)
        db.detalle_ventas.insert_many([dict(d) for d in detalle], session=sesion)
        receta_actualizada = _dispensar(db, sesion, receta, hoy) if receta else None
        descuento = descontar_stock(db, solicitud["id_venta"], sesion)
        # La protección contra reintentos se confirma junto con la venta y el descuento.
        registro = {"solicitud": solicitud, "receta": receta_actualizada, "descuento": descuento}
        db.ventas.update_one({"id_venta": solicitud["id_venta"]},
                             {"$set": {"registro": registro}}, session=sesion)
        return _resultado(dict(venta, registro=registro), repetida=False)

    with db.client.start_session() as sesion:
        try:
            return sesion.with_transaction(registrar)
        except DuplicateKeyError:
            # Otra llamada con el mismo id_venta se confirmó en paralelo.
            return sesion.with_transaction(lambda s: _repetida(db, s, solicitud)
                                           or _fallar_duplicado(solicitud))


def _fallar_duplicado(solicitud):
    raise ErrorVenta("conflicto", f"No se pudo registrar {solicitud['id_venta']}: ID duplicado")
