"""Publica en Neo4j una proyección consistente de las colecciones de MongoDB."""
from neo4j.exceptions import DriverError, IncompleteCommit, Neo4jError
from pymongo.errors import PyMongoError

from src.utils.datos_csv import ENTIDADES, RELACIONES
from src.utils.datos_mongo import leer_snapshot
from src.utils.proyeccion_neo4j import preparar_proyeccion


class ErrorSincronizacion(RuntimeError):
    """Falló el refresco y el llamador debe descartar la lectura del grafo."""


def leer_proyeccion(db_mongo):
    """Lee y valida las filas que se van a publicar."""
    try:
        datos = leer_snapshot(db_mongo.client, db_mongo)
    except PyMongoError as exc:
        raise ErrorSincronizacion("No se pudo leer el snapshot de MongoDB.") from exc

    try:
        proyeccion = preparar_proyeccion(datos)
    except ValueError as exc:
        raise ErrorSincronizacion(f"Datos de MongoDB inválidos para el grafo. {exc}") from exc
    if not any(proyeccion.values()):
        raise ErrorSincronizacion("El snapshot de MongoDB está vacío. Ejecutá load_mongo.py primero.")
    return proyeccion


def cargar(tx, datos):
    """Aplica las filas normalizadas al grafo dentro de la transacción recibida."""
    # Etiquetas, propiedades y relaciones provienen de constantes; valores parametrizados.
    for nombre, filas in datos.items():
        etiqueta, clave, _ = ENTIDADES[nombre]
        tx.run(f"UNWIND $filas AS fila MERGE (n:{etiqueta} {{{clave}: fila.{clave}}}) "
               "SET n += fila", filas=filas).consume()
    for origen, campo, destino, relacion in RELACIONES:
        etiqueta_a, clave_a, _ = ENTIDADES[origen]
        etiqueta_b, clave_b, _ = ENTIDADES[destino]
        referencias = [
            {"origen": fila[clave_a], "destino": fila[campo]} for fila in datos[origen]
        ]
        tx.run(
            f"""
            UNWIND $referencias AS ref
            MATCH (a:{etiqueta_a} {{{clave_a}: ref.origen}})
            WITH a, ref, [(a)-[r:{relacion}]->() | r] AS existentes,
                 head([(a)-[r:{relacion}]->(anterior:{etiqueta_b})
                       WHERE anterior.{clave_b} = ref.destino | r]) AS vigente
            FOREACH (obsoleto IN [r IN existentes WHERE vigente IS NULL OR r <> vigente] |
                DELETE obsoleto
            )
            WITH a, ref
            WHERE ref.destino IS NOT NULL
            MATCH (b:{etiqueta_b} {{{clave_b}: ref.destino}})
            MERGE (a)-[:{relacion}]->(b)
            """,
            referencias=referencias,
        ).consume()


def _preparar_esquema(sesion):
    restricciones = [(etiqueta, clave) for etiqueta, clave, _ in ENTIDADES.values()]
    restricciones.extend([
        ("Cliente", "dni"), ("Farmaceutico", "matricula"), ("ControlProyeccion", "id"),
    ])
    for etiqueta, clave in restricciones:
        sesion.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{etiqueta}) "
                   f"REQUIRE n.{clave} IS UNIQUE").consume()


def _refrescar(tx, db_mongo, consulta):
    # El bloqueo de escritura se conserva hasta que se confirma o revierte la
    # transacción, incluso después de quitar la propiedad usada para adquirirlo.
    tx.run("""
        MERGE (control:ControlProyeccion {id: 'farmared'})
        SET control.bloqueado = true
        REMOVE control.bloqueado
    """).consume()
    datos = leer_proyeccion(db_mongo)
    # Una reconstrucción de la fuente puede retirar IDs que todavía están en
    # la proyección. Se limpian acá, sin tocar los documentos de MongoDB.
    for nombre, (etiqueta, clave, _) in ENTIDADES.items():
        tx.run(f"MATCH (n:{etiqueta}) WHERE n.{clave} IS NOT NULL "
               f"AND NOT n.{clave} IN $ids DETACH DELETE n",
               ids=[fila[clave] for fila in datos[nombre]]).consume()
    cargar(tx, datos)
    if consulta is not None:
        return consulta(tx)
    return sum(map(len, datos.values()))


def sincronizar_grafo(db_mongo, sesion_neo4j, consulta=None):
    """Refresca el grafo y devuelve la cantidad de registros publicados.

    Si se pasa consulta(tx), devuelve su resultado materializado después del
    commit. La consulta debe ser de lectura y puede repetirse si el driver
    reintenta la transacción. Cada intento adquiere el bloqueo y lee un
    snapshot nuevo antes de reconciliar y consultar.
    """
    try:
        _preparar_esquema(sesion_neo4j)
        return sesion_neo4j.execute_write(_refrescar, db_mongo, consulta)
    except IncompleteCommit as exc:
        raise ErrorSincronizacion(
            "Se perdió la conexión al confirmar en Neo4j. El resultado del commit "
            "quedó indeterminado. Volvé a sincronizar."
        ) from exc
    except (DriverError, Neo4jError) as exc:
        raise ErrorSincronizacion(
            "No se pudo publicar la proyección o completar la lectura en Neo4j."
        ) from exc
