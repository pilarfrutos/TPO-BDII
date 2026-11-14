import csv
from datetime import date
from pathlib import Path

from src.utils.calendario import fecha_bson
from src.utils.reglas_negocio import validar_negocio

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
# CSV de la cátedra: nunca se modifican.
ORIGINALES_DIR = DATA_DIR / "original"
# Registros propios (T07): mismos encabezados; cada archivo es opcional.
ADICIONALES_DIR = DATA_DIR / "adicionales"
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


def _leer_csv(ruta, nombre):
    """Devuelve (origen, fila tipada) por cada línea del CSV de la colección."""
    encabezado = ENTIDADES[nombre][2]
    with ruta.open(encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo, strict=True)
        if lector.fieldnames != encabezado.split():
            raise ValueError(f"{ruta.parent.name}/{ruta.name}: encabezado inesperado")
        filas = []
        for linea, fila in enumerate(lector, 2):
            origen = f"{ruta.parent.name}/{ruta.name}:{linea}"
            if None in fila or any(v is None for v in fila.values()):
                raise ValueError(f"{origen}: cantidad incorrecta de columnas")
            tipada = {}
            for campo, valor in fila.items():
                if valor == "":
                    if (nombre, campo) not in NULOS:
                        raise ValueError(f"{origen}:{campo}: vacío inesperado")
                    tipada[campo] = None
                elif campo in ENTEROS:
                    tipada[campo] = int(valor)
                elif campo in FECHAS:
                    tipada[campo] = date.fromisoformat(valor)
                    if tipada[campo].isoformat() != valor:
                        raise ValueError(f"{origen}:{campo}: fecha no ISO")
                elif campo == "activo":
                    if valor not in {"True", "False"}:
                        raise ValueError(f"{origen}: booleano inválido")
                    tipada[campo] = valor == "True"
                else:
                    tipada[campo] = valor
            filas.append((origen, tipada))
        return filas


def leer_datos(directorios=(ORIGINALES_DIR, ADICIONALES_DIR)):
    """Lee y valida los CSV de los originales y, si existen, de los adicionales.

    El primer directorio debe contener los nueve archivos. Los siguientes son
    opcionales y pueden omitir archivos. La unicidad de IDs, DNI y matrículas,
    las referencias y los totales se validan sobre el conjunto unido.
    """
    principal, *extra = [Path(d) for d in directorios]
    datos = {}
    for nombre, (_, clave, _) in ENTIDADES.items():
        rutas = [principal / f"{nombre}.csv"]
        rutas += [d / f"{nombre}.csv" for d in extra if (d / f"{nombre}.csv").is_file()]
        filas = []
        vistos = {}
        for ruta in rutas:
            for origen, fila in _leer_csv(ruta, nombre):
                if fila[clave] in vistos:
                    raise ValueError(f"{origen}: identificador repetido {fila[clave]} "
                                     f"(ya definido en {vistos[fila[clave]]})")
                vistos[fila[clave]] = origen
                filas.append(fila)
        datos[nombre] = filas
    for nombre, campo in [("clientes", "dni"), ("farmaceuticos", "matricula")]:
        valores = [f[campo] for f in datos[nombre]]
        if len(valores) != len(set(valores)):
            raise ValueError(f"{nombre}: {campo} repetido")
    validar_referencias(datos)
    validar_negocio(datos, ENTIDADES, ENTEROS)
    return datos


def para_mongo(fila):
    return {k: fecha_bson(v) if isinstance(v, date) else v for k, v in fila.items()}


def resumen(datos):
    for nombre, filas in datos.items():
        print(f"{nombre}: {len(filas)} registros")
    print(f"Total: {sum(map(len, datos.values()))} registros")
    print("Aviso: RC002 conserva la fecha original 2026-09-15; última dispensa +30 días sería 2026-09-14.")
