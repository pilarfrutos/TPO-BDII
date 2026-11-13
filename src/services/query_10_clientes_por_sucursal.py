from src.services.sincronizacion_neo4j import sincronizar_grafo


CLIENTES_POR_SUCURSAL = """
MATCH (s:Sucursal {id_sucursal: $id_sucursal})
CALL (s) {
    MATCH (v:Venta)-[:REALIZADA_POR]->(c:Cliente)
    WHERE v.id_sucursal = s.id_sucursal
    RETURN c
    UNION
    MATCH (s)<-[:TRABAJA_EN]-(:Farmaceutico)<-[:ATENDIDA_POR]-(v:Venta)
          -[:REALIZADA_POR]->(c:Cliente)
    WHERE v.id_sucursal IS NULL
    RETURN c
}
RETURN c.id_cliente AS id_cliente, c.nombre AS nombre, c.apellido AS apellido
ORDER BY id_cliente ASC
"""


def q10(db_mongo, sesion_neo4j, id_sucursal):
    """Lista clientes atendidos en una sucursal mediante la proyección de Neo4j.

    Recibe la base fuente de MongoDB, una sesión de Neo4j y el ID de sucursal.
    Devuelve una fila por cliente con ID, nombre y apellido, por ID ascendente.
    Una sucursal sin atenciones o inexistente devuelve una lista vacía.
    """
    if not isinstance(id_sucursal, str) or not id_sucursal.strip():
        raise ValueError("Indicá un ID de sucursal no vacío.")

    def consultar(tx):
        return tx.run(CLIENTES_POR_SUCURSAL, id_sucursal=id_sucursal).data()

    return sincronizar_grafo(db_mongo, sesion_neo4j, consulta=consultar)
