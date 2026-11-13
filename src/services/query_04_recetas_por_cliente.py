from src.services.sincronizacion_neo4j import sincronizar_grafo


RECETAS_POR_CLIENTE = """
MATCH (r:Receta)-[:PRESCRIPTA_A]->(c:Cliente)
WITH c, count(DISTINCT r.id_receta) AS cantidad_recetas
WHERE cantidad_recetas > 1
RETURN c.id_cliente AS id_cliente, c.nombre AS nombre,
       c.apellido AS apellido, cantidad_recetas
ORDER BY id_cliente ASC
"""


def _consultar(tx):
    return tx.run(RECETAS_POR_CLIENTE).data()


def q04(db_mongo, sesion_neo4j):
    """Lista clientes con más de una receta registrada en Neo4j.

    Recibe la base fuente de MongoDB y la sesión de Neo4j. Devuelve filas
    con ID, nombre, apellido y cantidad de recetas únicas, por ID ascendente.
    Incluye todos los estados de receta y devuelve [] si no hay coincidencias.
    """
    return sincronizar_grafo(db_mongo, sesion_neo4j, consulta=_consultar)
