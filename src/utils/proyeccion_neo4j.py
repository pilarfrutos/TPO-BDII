"""Contrato de entrada para la proyección de FarmaRed en Neo4j."""
from datetime import date, datetime, timezone

from src.utils.datos_csv import ENTIDADES, ENTEROS, FECHAS, NULOS, validar_referencias
from src.utils.reglas_negocio import validar_negocio


def _normalizar_valor(nombre, identificador, campo, valor):
    if (nombre, campo) in NULOS and (valor is None or valor == ""):
        return None

    if campo in FECHAS:
        if isinstance(valor, datetime):
            # BSON guarda fechas de negocio en UTC, incluso cuando el driver
            # devuelve un datetime sin información de zona horaria.
            if valor.tzinfo is not None:
                valor = valor.astimezone(timezone.utc)
            valor = valor.date()
        esperado = "una fecha de negocio"
        valido = isinstance(valor, date)
    elif campo in ENTEROS:
        esperado = "un entero"
        valido = isinstance(valor, int) and not isinstance(valor, bool)
    elif campo == "activo":
        esperado = "un booleano"
        valido = isinstance(valor, bool)
    else:
        esperado = "texto no vacío"
        valido = isinstance(valor, str) and bool(valor.strip())

    if not valido:
        raise ValueError(f"{nombre}[{identificador}].{campo}: se esperaba {esperado}")
    return valor


def preparar_proyeccion(datos):
    """Prepara filas tipadas de los CSV o documentos BSON agrupados por colección.

    Proyecta los campos de negocio y comprueba IDs y referencias sobre el
    conjunto completo antes de que el cargador escriba en Neo4j.
    """
    proyeccion = {}
    for nombre, (_, clave, encabezado) in ENTIDADES.items():
        if nombre not in datos:
            raise ValueError(f"{nombre}: falta la colección en los datos de la proyección")

        campos = encabezado.split()
        filas = []
        ids = set()
        for fila in datos[nombre]:
            identificador = fila.get(clave, "sin ID")
            propiedades = {
                campo: _normalizar_valor(nombre, identificador, campo, fila.get(campo))
                for campo in campos
            }
            identificador = propiedades[clave]
            if nombre == "ventas":
                id_sucursal = fila.get("id_sucursal")
                propiedades["id_sucursal"] = (
                    None if id_sucursal is None else
                    _normalizar_valor(nombre, identificador, "id_sucursal", id_sucursal)
                )
            if identificador in ids:
                raise ValueError(f"{nombre}[{identificador}]: identificador repetido")
            ids.add(identificador)
            filas.append(propiedades)
        proyeccion[nombre] = filas

    validar_referencias(proyeccion)
    validar_negocio(proyeccion, ENTIDADES, ENTEROS)
    return proyeccion
