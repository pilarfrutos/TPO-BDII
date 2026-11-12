import csv
from datetime import date
from pathlib import Path

from src.utils.calendario import fecha_bson

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "original"
# Archivo: (etiqueta de grafo, clave de origen, encabezado esperado).
ENTIDADES = {
    "clientes": ("Cliente", "id_cliente", "id_cliente nombre apellido dni email telefono ciudad provincia obra_social nro_afiliado activo"),
    "sucursales": ("Sucursal", "id_sucursal", "id_sucursal nombre tipo direccion ciudad provincia telefono activo"),
    "farmaceuticos": ("Farmaceutico", "id_farmaceutico", "id_farmaceutico nombre apellido matricula cargo id_sucursal activo"),
    "proveedores": ("Proveedor", "id_proveedor", "id_proveedor razon_social cuit tipo ciudad provincia telefono activo"),
    "productos": ("Producto", "id_producto", "id_producto nombre principio_activo categoria presentacion condicion_venta precio_unit id_proveedor activo"),
    "stock_lotes": ("Lote", "id_lote", "id_lote id_producto id_sucursal nro_lote unidades vencimiento"),
    "recetas": ("Receta", "id_receta", "id_receta id_cliente medico matricula_medico fecha_emision tipo dispensas_autorizadas dispensas_realizadas proxima_dispensa estado"),
    "ventas": ("Venta", "id_venta", "id_venta id_cliente id_farmaceutico id_receta fecha tipo medio_pago total estado"),
    "detalle_ventas": ("DetalleVenta", "id_detalle", "id_detalle id_venta id_producto cantidad precio_unit"),
}
ENTEROS = {"precio_unit", "unidades", "dispensas_autorizadas", "dispensas_realizadas", "cantidad", "total"}
FECHAS = {"vencimiento", "fecha_emision", "proxima_dispensa", "fecha"}
NULOS = {("clientes", "nro_afiliado"), ("recetas", "proxima_dispensa"), ("ventas", "id_receta")}
# Origen, campo FK, destino y nombre de relación en el grafo.
RELACIONES = [
    ("farmaceuticos", "id_sucursal", "sucursales", "TRABAJA_EN"),
    ("productos", "id_proveedor", "proveedores", "PROVISTO_POR"),
    ("stock_lotes", "id_producto", "productos", "DE_PRODUCTO"),
    ("stock_lotes", "id_sucursal", "sucursales", "UBICADO_EN"),
    ("recetas", "id_cliente", "clientes", "PRESCRIPTA_A"),
    ("ventas", "id_cliente", "clientes", "REALIZADA_POR"),
    ("ventas", "id_farmaceutico", "farmaceuticos", "ATENDIDA_POR"),
    ("ventas", "id_receta", "recetas", "CON_RECETA"),
    ("detalle_ventas", "id_venta", "ventas", "PERTENECE_A"),
    ("detalle_ventas", "id_producto", "productos", "DE_PRODUCTO"),
]


def validar_referencias(datos):
    ids_por_entidad = {
        nombre: {fila[clave] for fila in datos[nombre]}
        for nombre, (_, clave, _) in ENTIDADES.items()
    }
    for origen, campo, destino, _ in RELACIONES:
        clave = ENTIDADES[origen][1]
        for fila in datos[origen]:
            referencia = fila[campo]
            if referencia is None and (origen, campo) in NULOS:
                continue
            if referencia not in ids_por_entidad[destino]:
                raise ValueError(
                    f"{origen}[{fila[clave]}].{campo}: referencia inexistente "
                    f"en {destino} ({referencia!r})"
                )


def leer_datos():
    datos = {}
    for nombre, (_, clave, encabezado) in ENTIDADES.items():
        with (DATA_DIR / f"{nombre}.csv").open(encoding="utf-8", newline="") as archivo:
            lector = csv.DictReader(archivo, strict=True)
            if lector.fieldnames != encabezado.split():
                raise ValueError(f"{nombre}: encabezado inesperado")
            filas = []
            ids = set()
            for linea, fila in enumerate(lector, 2):
                if None in fila or any(v is None for v in fila.values()):
                    raise ValueError(f"{nombre}:{linea}: cantidad incorrecta de columnas")
                tipada = {}
                for campo, valor in fila.items():
                    if valor == "":
                        if (nombre, campo) not in NULOS:
                            raise ValueError(f"{nombre}:{linea}:{campo}: vacío inesperado")
                        tipada[campo] = None
                    elif campo in ENTEROS:
                        tipada[campo] = int(valor)
                        if tipada[campo] < 0 or (campo == "cantidad" and tipada[campo] == 0):
                            raise ValueError(f"{nombre}:{linea}:{campo}: cantidad inválida")
                    elif campo in FECHAS:
                        tipada[campo] = date.fromisoformat(valor)
                        if tipada[campo].isoformat() != valor:
                            raise ValueError(f"{nombre}:{linea}:{campo}: fecha no ISO")
                    elif campo == "activo":
                        if valor not in {"True", "False"}:
                            raise ValueError(f"{nombre}:{linea}: booleano inválido")
                        tipada[campo] = valor == "True"
                    else:
                        tipada[campo] = valor
                if tipada[clave] in ids:
                    raise ValueError(f"{nombre}: identificador repetido {tipada[clave]}")
                ids.add(tipada[clave])
                filas.append(tipada)
            datos[nombre] = filas
    for nombre, campo in [("clientes", "dni"), ("farmaceuticos", "matricula")]:
        valores = [f[campo] for f in datos[nombre]]
        if len(valores) != len(set(valores)):
            raise ValueError(f"{nombre}: {campo} repetido")
    validar_referencias(datos)
    for venta in datos["ventas"]:
        items = [f for f in datos["detalle_ventas"] if f["id_venta"] == venta["id_venta"]]
        if not items or sum(f["cantidad"] * f["precio_unit"] for f in items) != venta["total"]:
            raise ValueError(f"{venta['id_venta']}: total inconsistente")
    return datos


def para_mongo(fila):
    return {k: fecha_bson(v) if isinstance(v, date) else v for k, v in fila.items()}


def resumen(datos):
    for nombre, filas in datos.items():
        print(f"{nombre}: {len(filas)} registros")
    print(f"Total: {sum(map(len, datos.values()))} registros")
    print("Aviso: RC002 conserva la fecha original 2026-09-15; última dispensa +30 días sería 2026-09-14.")
