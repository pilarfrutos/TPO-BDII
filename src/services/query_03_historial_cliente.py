from src.services.sincronizacion_neo4j import sincronizar_grafo


HISTORIAL_CLIENTE = """
MATCH (c:Cliente {id_cliente: $id_cliente})
WITH c,
    [(c)<-[:REALIZADA_POR]-(v:Venta) | {
        tipo: 'venta', id: v.id_venta, fecha: v.fecha,
        datos: {
            tipo: v.tipo, estado: v.estado, total: v.total, medio_pago: v.medio_pago,
            id_farmaceutico: v.id_farmaceutico, id_receta: v.id_receta
        }
    }] +
    [(c)<-[:PRESCRIPTA_A]-(r:Receta) | {
        tipo: 'receta', id: r.id_receta, fecha: r.fecha_emision,
        datos: {
            tipo: r.tipo, medico: r.medico, matricula_medico: r.matricula_medico,
            estado: r.estado, dispensas_autorizadas: r.dispensas_autorizadas,
            dispensas_realizadas: r.dispensas_realizadas,
            proxima_dispensa: toString(r.proxima_dispensa)
        }
    }] AS historial
RETURN c.id_cliente AS id_cliente, COLLECT {
    UNWIND historial AS evento
    WITH evento ORDER BY evento.fecha ASC, evento.tipo ASC, evento.id ASC
    RETURN evento{.*, fecha: toString(evento.fecha)}
} AS eventos
"""


def q03(db_mongo, sesion_neo4j, id_cliente):
    """Devuelve el historial de ventas y recetas de un cliente en Neo4j.

    Recibe la base fuente de MongoDB, la sesión de Neo4j y el ID del cliente.
    Devuelve un diccionario con el ID y sus eventos por fecha, tipo e ID.
    Un cliente existente sin historial tiene una lista vacía. Para un ID
    inexistente devuelve None. Las fechas se devuelven en formato ISO.
    """
    if not isinstance(id_cliente, str) or not id_cliente.strip():
        raise ValueError("Indicá un ID de cliente no vacío.")

    def consultar(tx):
        registro = tx.run(HISTORIAL_CLIENTE, id_cliente=id_cliente).single()
        return registro.data() if registro is not None else None

    return sincronizar_grafo(db_mongo, sesion_neo4j, consulta=consultar)
