"""Invariantes compartidas por la carga, la proyección y los servicios."""
from collections import defaultdict


COBERTURAS = frozenset({"OSDE", "Swiss Medical", "PAMI", "IOMA", "Galeno", "Sin cobertura"})
MEDIOS_PAGO = frozenset({"Efectivo", "Débito", "Crédito", "Transferencia", "Obra social"})
BAJO_RECETA = frozenset({"Bajo receta", "Bajo receta archivada"})
CONDICIONES_VENTA = BAJO_RECETA | {"Venta libre"}
TRATAMIENTO_PROLONGADO = "Tratamiento prolongado"
MAX_DISPENSAS = 3
MAX_ENTERO_BSON = (1 << 63) - 1

DOMINIOS = {
    "clientes": {"obra_social": COBERTURAS},
    "sucursales": {"tipo": {"Farmacia", "Droguería"}},
    "farmaceuticos": {"cargo": {"Director Técnico", "Farmacéutico"}},
    "proveedores": {"tipo": {"Laboratorio", "Droguería"}},
    "productos": {"condicion_venta": CONDICIONES_VENTA},
    "recetas": {"tipo": {"Simple", "Archivada", TRATAMIENTO_PROLONGADO},
                "estado": {"Vigente", "Completada", "Vencida"}},
    "ventas": {"tipo": {"Venta libre", "Con receta"}, "medio_pago": MEDIOS_PAGO,
               "estado": {"Completada", "Pendiente", "Anulada"}},
}
MINIMOS = {"cantidad": 1, "dispensas_autorizadas": 1}


def validar_producto_para_venta(producto):
    """Comprueba los campos del catálogo que determinan receta e importe."""
    condicion = producto.get("condicion_venta")
    if not isinstance(condicion, str) or condicion not in CONDICIONES_VENTA:
        raise ValueError("condicion_venta desconocida")
    precio = producto.get("precio_unit")
    if not isinstance(precio, int) or isinstance(precio, bool) or not 0 <= precio <= MAX_ENTERO_BSON:
        raise ValueError(f"precio_unit debe ser un entero entre 0 y {MAX_ENTERO_BSON}")


def validar_dispensas(receta):
    tipo = receta.get("tipo")
    estado = receta.get("estado")
    autorizadas = receta.get("dispensas_autorizadas")
    realizadas = receta.get("dispensas_realizadas")
    if not isinstance(tipo, str) or tipo not in DOMINIOS["recetas"]["tipo"]:
        raise ValueError("tipo de receta desconocido")
    if not isinstance(estado, str) or estado not in DOMINIOS["recetas"]["estado"]:
        raise ValueError("estado de receta desconocido")
    limite = MAX_DISPENSAS if tipo == TRATAMIENTO_PROLONGADO else 1
    if (not isinstance(autorizadas, int) or isinstance(autorizadas, bool)
            or not 1 <= autorizadas <= limite):
        raise ValueError(f"dispensas_autorizadas debe estar entre 1 y {limite}")
    if (not isinstance(realizadas, int) or isinstance(realizadas, bool)
            or not 0 <= realizadas <= autorizadas):
        raise ValueError("dispensas_realizadas debe estar entre 0 y las autorizadas")
    if estado == "Vigente" and realizadas == autorizadas:
        raise ValueError("una receta Vigente debe tener dispensas disponibles")
    if estado == "Completada":
        if realizadas != autorizadas:
            raise ValueError("una receta Completada debe haber agotado sus dispensas")
        if receta.get("proxima_dispensa") not in (None, ""):
            raise ValueError("una receta Completada debe tener proxima_dispensa vacía")


def validar_negocio(datos, entidades, enteros):
    """Comprueba filas tipadas y coherencia entre documentos referenciados."""
    errores = []
    for nombre, filas in datos.items():
        _, clave, _ = entidades[nombre]
        dominios = {} if nombre == "recetas" else DOMINIOS.get(nombre, {})
        for fila in filas:
            prefijo = f"{nombre}[{fila[clave]}]"
            for campo, valores in dominios.items():
                if fila[campo] not in valores:
                    errores.append(f"{prefijo}.{campo}: valor fuera del dominio ({fila[campo]!r})")
            for campo in enteros.intersection(fila):
                minimo = MINIMOS.get(campo, 0)
                if fila[campo] < minimo:
                    errores.append(f"{prefijo}.{campo}: mínimo {minimo}")
                elif fila[campo] > MAX_ENTERO_BSON:
                    errores.append(f"{prefijo}.{campo}: máximo {MAX_ENTERO_BSON}")
            if nombre == "recetas":
                try:
                    validar_dispensas(fila)
                except ValueError as exc:
                    errores.append(f"{prefijo}: {exc}")

    totales = defaultdict(int)
    bajo_receta = defaultdict(set)
    productos = {p["id_producto"]: p for p in datos["productos"]}
    for detalle in datos["detalle_ventas"]:
        id_venta = detalle["id_venta"]
        id_producto = detalle["id_producto"]
        totales[id_venta] += detalle["cantidad"] * detalle["precio_unit"]
        if productos[id_producto]["condicion_venta"] in BAJO_RECETA:
            bajo_receta[id_venta].add(id_producto)
    recetas = {r["id_receta"]: r for r in datos["recetas"]}
    sucursales = {s["id_sucursal"]: s for s in datos["sucursales"]}
    asignaciones = {f["id_farmaceutico"]: f["id_sucursal"] for f in datos["farmaceuticos"]}
    for venta in datos["ventas"]:
        id_venta = venta["id_venta"]
        id_receta = venta["id_receta"]
        id_sucursal = venta.get("id_sucursal")
        if id_sucursal is None:
            id_sucursal = asignaciones[venta["id_farmaceutico"]]
        sede = sucursales.get(id_sucursal)
        if sede is None:
            errores.append(f"ventas[{id_venta}].id_sucursal: referencia inexistente "
                           f"en sucursales ({id_sucursal!r})")
        elif sede["tipo"] != "Farmacia":
            errores.append(f"ventas[{id_venta}].id_sucursal: {id_sucursal} no es una Farmacia")
        if totales.get(id_venta) != venta["total"]:
            errores.append(f"{id_venta}: total inconsistente con el detalle")
        if (venta["tipo"] == "Con receta") != (id_receta is not None):
            errores.append(f"ventas[{id_venta}].id_receta: no coincide con el tipo de venta")
        if id_receta is None and bajo_receta[id_venta]:
            productos_requeridos = ", ".join(sorted(bajo_receta[id_venta]))
            errores.append(f"ventas[{id_venta}].id_receta: falta receta para {productos_requeridos}")
        elif id_receta is not None and recetas[id_receta]["id_cliente"] != venta["id_cliente"]:
            errores.append(f"ventas[{id_venta}].id_receta: {id_receta} pertenece a otro cliente")
    if errores:
        raise ValueError("; ".join(errores))
