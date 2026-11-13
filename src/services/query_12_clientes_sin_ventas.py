from src.services.sincronizacion_neo4j import sincronizar_grafo
from src.utils.calendario import hoy_local, inicio_ultimo_anio


CLIENTES_SIN_VENTAS = """
MATCH (c:Cliente)
WHERE NOT EXISTS {
    MATCH (c)<-[:REALIZADA_POR]-(v:Venta)
    WHERE v.fecha >= $inicio AND v.fecha <= $hoy
}
RETURN c.id_cliente AS id_cliente, c.nombre AS nombre, c.apellido AS apellido
ORDER BY id_cliente ASC
"""


def q12(db_mongo, sesion_neo4j, *, hoy=None):
    """Lista clientes sin ventas registradas durante el último año calendario.

    Recibe la base fuente de MongoDB y una sesión de Neo4j. Usa la fecha
    actual de Buenos Aires o una fecha de negocio inyectada para pruebas.
    Cuenta ventas de todos los estados entre el aniversario anterior y hoy,
    ambos inclusive. Devuelve ID, nombre y apellido por cliente, por ID.
    """
    dia = hoy if hoy is not None else hoy_local()
    inicio = inicio_ultimo_anio(dia)

    def consultar(tx):
        return tx.run(CLIENTES_SIN_VENTAS, inicio=inicio, hoy=dia).data()

    return sincronizar_grafo(db_mongo, sesion_neo4j, consulta=consultar)
