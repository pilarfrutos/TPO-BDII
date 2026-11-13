"""q13 · ABM de clientes en MongoDB (fuente de verdad).

Operaciones:
- alta(db, id_cliente, nombre, apellido, dni, email, telefono, ciudad, provincia,
       obra_social, nro_afiliado=None)
- modificar(db, id_cliente, *, email=..., telefono=..., obra_social=..., nro_afiliado=...)
  Solo datos de contacto (email, teléfono) y cobertura (obra social, afiliado).
- baja(db, id_cliente): baja lógica con activo=False; el documento y su
  historial (ventas, recetas) se conservan.
- reactivar(db, id_cliente): vuelve a activo=True (D11).

Todas devuelven {"operacion", "antes", "despues"} con los documentos sin `_id`
(`antes` es None en el alta). Los rechazos lanzan ErrorCliente con un `codigo`:
datos_invalidos, id_duplicado, dni_duplicado, inexistente, inactivo, activo,
conflicto.

La unicidad de id_cliente y DNI la garantizan los índices únicos de MongoDB,
no una consulta previa: entre dos altas concurrentes con el mismo DNI solo una
prospera. El grafo no se escribe aquí; toma los cambios en la siguiente
proyección desde MongoDB (T06).
"""
import re

COBERTURAS = {"OSDE", "Swiss Medical", "PAMI", "IOMA", "Galeno", "Sin cobertura"}
SIN_COBERTURA = "Sin cobertura"
CAMPOS_MODIFICABLES = ("email", "telefono", "obra_social", "nro_afiliado")
_NO_INFORMADO = object()
_FORMATOS = {
    "id_cliente": (re.compile(r"[A-Za-z0-9_-]{1,20}"), "letras, dígitos, '-' o '_' (máx. 20)"),
    "dni": (re.compile(r"\d{7,8}"), "7 u 8 dígitos, sin puntos"),
    "email": (re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+"), "una dirección de email"),
    "telefono": (re.compile(r"\d{8,15}"), "entre 8 y 15 dígitos, sin espacios ni guiones"),
}
_INTENTOS = 3


class ErrorCliente(ValueError):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo


def _texto(campo, valor):
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorCliente("datos_invalidos", f"{campo}: se esperaba texto no vacío")
    valor = valor.strip()
    if campo in _FORMATOS:
        patron, descripcion = _FORMATOS[campo]
        if not patron.fullmatch(valor):
            raise ErrorCliente("datos_invalidos", f"{campo}: se esperaba {descripcion}")
    return valor


def _cobertura(obra_social, nro_afiliado):
    """Valida la combinación; un afiliado vacío equivale a None."""
    obra_social = _texto("obra_social", obra_social)
    if obra_social not in COBERTURAS:
        raise ErrorCliente("datos_invalidos",
                           f"obra_social: debe ser una de {', '.join(sorted(COBERTURAS))}")
    if nro_afiliado is not None:
        if not isinstance(nro_afiliado, str):
            raise ErrorCliente("datos_invalidos", "nro_afiliado: se esperaba texto")
        nro_afiliado = nro_afiliado.strip() or None
    if obra_social == SIN_COBERTURA and nro_afiliado is not None:
        raise ErrorCliente("datos_invalidos", "nro_afiliado: debe quedar vacío sin cobertura")
    if obra_social != SIN_COBERTURA and nro_afiliado is None:
        raise ErrorCliente("datos_invalidos", f"nro_afiliado: obligatorio con {obra_social}")
    return obra_social, nro_afiliado


def _buscar(db, id_cliente):
    documento = db.clientes.find_one({"id_cliente": id_cliente}, {"_id": 0})
    if documento is None:
        raise ErrorCliente("inexistente", f"No existe el cliente {id_cliente}")
    return documento


def alta(db, id_cliente, nombre, apellido, dni, email, telefono, ciudad, provincia,
         obra_social, nro_afiliado=None):
    from pymongo.errors import DuplicateKeyError

    cliente = {campo: _texto(campo, valor) for campo, valor in (
        ("id_cliente", id_cliente), ("nombre", nombre), ("apellido", apellido), ("dni", dni),
        ("email", email), ("telefono", telefono), ("ciudad", ciudad), ("provincia", provincia),
    )}
    cliente["obra_social"], cliente["nro_afiliado"] = _cobertura(obra_social, nro_afiliado)
    cliente["activo"] = True
    # Idempotente si la carga ya los creó; sin ellos no habría garantía ante concurrencia.
    db.clientes.create_index("id_cliente", unique=True)
    db.clientes.create_index("dni", unique=True)
    try:
        db.clientes.insert_one(dict(cliente))
    except DuplicateKeyError as exc:
        if "dni" in (exc.details or {}).get("keyPattern", {}):
            raise ErrorCliente("dni_duplicado", f"Ya existe un cliente con DNI {cliente['dni']} "
                                                "(si está dado de baja, usá reactivar)") from exc
        raise ErrorCliente("id_duplicado", f"Ya existe el cliente {cliente['id_cliente']}") from exc
    return {"operacion": "alta", "antes": None, "despues": cliente}


def modificar(db, id_cliente, *, email=_NO_INFORMADO, telefono=_NO_INFORMADO,
              obra_social=_NO_INFORMADO, nro_afiliado=_NO_INFORMADO):
    """Modifica contacto y cobertura de un cliente activo.

    Al pasar a 'Sin cobertura' el afiliado se vacía si no se informa. Al cambiar
    a otra obra social hay que informar el nuevo número de afiliado.
    """
    from pymongo import ReturnDocument

    informados = {campo: valor for campo, valor in (
        ("email", email), ("telefono", telefono),
        ("obra_social", obra_social), ("nro_afiliado", nro_afiliado),
    ) if valor is not _NO_INFORMADO}
    if not informados:
        raise ErrorCliente("datos_invalidos",
                           f"Indicá al menos un campo: {', '.join(CAMPOS_MODIFICABLES)}")
    cambios = {campo: _texto(campo, informados[campo])
               for campo in ("email", "telefono") if campo in informados}

    for _ in range(_INTENTOS):
        antes = _buscar(db, id_cliente)
        if not antes["activo"]:
            raise ErrorCliente("inactivo", f"El cliente {id_cliente} está dado de baja; "
                                           "reactivalo antes de modificarlo")
        if "obra_social" in informados or "nro_afiliado" in informados:
            nueva_obra = informados.get("obra_social", antes["obra_social"])
            if "nro_afiliado" in informados:
                nuevo_nro = informados["nro_afiliado"]
            elif nueva_obra == antes["obra_social"]:
                nuevo_nro = antes["nro_afiliado"]
            else:
                # El número anterior pertenece a otra obra social: no se arrastra.
                nuevo_nro = None
            cambios["obra_social"], cambios["nro_afiliado"] = _cobertura(nueva_obra, nuevo_nro)
        # La cobertura se valida contra el estado leído: si otro proceso lo cambió
        # entre la lectura y la escritura, el filtro no coincide y se reintenta.
        filtro = {"id_cliente": id_cliente, "activo": True,
                  "obra_social": antes["obra_social"], "nro_afiliado": antes["nro_afiliado"]}
        despues = db.clientes.find_one_and_update(filtro, {"$set": cambios}, projection={"_id": 0},
                                                  return_document=ReturnDocument.AFTER)
        if despues is not None:
            return {"operacion": "modificacion", "antes": antes, "despues": despues}
    raise ErrorCliente("conflicto", f"El cliente {id_cliente} cambió durante la modificación; "
                                    "reintentá la operación")


def _cambiar_estado(db, id_cliente, activo, operacion):
    from pymongo import ReturnDocument

    antes = db.clientes.find_one_and_update(
        {"id_cliente": id_cliente, "activo": not activo}, {"$set": {"activo": activo}},
        projection={"_id": 0}, return_document=ReturnDocument.BEFORE)
    if antes is None:
        actual = _buscar(db, id_cliente)
        estado = "activo" if actual["activo"] else "inactivo"
        raise ErrorCliente(estado, f"El cliente {id_cliente} ya está {estado}")
    return {"operacion": operacion, "antes": antes, "despues": dict(antes, activo=activo)}


def baja(db, id_cliente):
    """Baja lógica: activo=False. Nunca se borra el documento (N7)."""
    return _cambiar_estado(db, id_cliente, False, "baja")


def reactivar(db, id_cliente):
    return _cambiar_estado(db, id_cliente, True, "reactivacion")


OPERACIONES = {"alta": alta, "modificar": modificar, "baja": baja, "reactivar": reactivar}


def q13(db, operacion, **argumentos):
    """Punto de entrada único: q13(db, "alta" | "modificar" | "baja" | "reactivar", ...)."""
    if operacion not in OPERACIONES:
        raise ErrorCliente("datos_invalidos",
                           f"Operación desconocida {operacion!r}; usá {', '.join(OPERACIONES)}")
    return OPERACIONES[operacion](db, **argumentos)
