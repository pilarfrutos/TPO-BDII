from src.services.sincronizacion_neo4j import sincronizar_grafo
from src.utils.calendario import hoy_local


DISPENSAS_ATRASADAS = """
MATCH (r:Receta)-[:PRESCRIPTA_A]->(c:Cliente)
WHERE r.tipo = 'Tratamiento prolongado'
  AND r.estado = 'Vigente'
  AND r.proxima_dispensa < $hoy
WITH r, c ORDER BY r.proxima_dispensa ASC, r.id_receta ASC
RETURN r{.*, fecha_emision: toString(r.fecha_emision),
         proxima_dispensa: toString(r.proxima_dispensa)} AS receta,
       c{.*, nro_afiliado: c.nro_afiliado} AS cliente
"""


def q06(db_mongo, sesion_neo4j, *, hoy=None):
    """Lista las dispensas atrasadas de tratamientos prolongados vigentes en Neo4j.

    Recibe la base fuente de MongoDB y la sesión de Neo4j. El corte opcional
    `hoy` es una fecha de negocio para pruebas. Por defecto usa el día actual
    en Buenos Aires. Devuelve una lista con la receta y su cliente por fila,
    ordenada por próxima dispensa e ID. Las fechas salen en formato ISO.
    """
    dia = hoy if hoy is not None else hoy_local()

    def consultar(tx):
        return tx.run(DISPENSAS_ATRASADAS, hoy=dia).data()

    return sincronizar_grafo(db_mongo, sesion_neo4j, consulta=consultar)
