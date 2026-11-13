"""Lectura de las nueve colecciones de MongoDB como entrada para la proyección.

Es la interfaz acordada entre la carga MongoDB (T05) y el grafo (T06): devuelve
los documentos agrupados por colección, con la misma forma que `leer_datos`,
para pasarlos a `preparar_proyeccion`.
"""
from src.utils.datos_csv import ENTIDADES


def leer_snapshot(client, db):
    """Lee todas las colecciones en un mismo instante lógico.

    Usa una sesión con lectura `snapshot` del replica set: una venta confirmada
    entre la lectura de `ventas` y la de `detalle_ventas` no aparece a medias.
    Los documentos se ordenan por ID de origen y no incluyen `_id`.
    """
    with client.start_session(snapshot=True) as sesion:
        return {
            nombre: list(db[nombre].find({}, {"_id": 0}, session=sesion).sort(clave, 1))
            for nombre, (_, clave, _) in ENTIDADES.items()
        }
