"""q05: cantidad de ventas recientes por farmacéutico activo."""

from src.utils.calendario import hoy_local, limites_ultimos_dias


def q05(db, *, hoy=None):
    """Devuelve farmacéuticos activos y sus ventas no anuladas de los últimos 60 días.

    La ventana contiene 60 fechas de calendario, incluido el día ``hoy``. En
    producción se usa la fecha actual de Buenos Aires. Los profesionales sin
    ventas aparecen con ``cantidad_ventas`` igual a cero.
    """
    inicio, fin = limites_ultimos_dias(hoy if hoy is not None else hoy_local(), 60)
    return list(db.farmaceuticos.aggregate([
        {"$match": {"activo": True}},
        {"$sort": {"id_farmaceutico": 1}},
        {"$lookup": {
            "from": "ventas",
            "let": {"id_farmaceutico": "$id_farmaceutico"},
            "as": "ventas_recientes",
            "pipeline": [
                {"$match": {"$expr": {"$and": [
                    {"$eq": ["$id_farmaceutico", "$$id_farmaceutico"]},
                    {"$gte": ["$fecha", inicio]},
                    {"$lt": ["$fecha", fin]},
                    {"$ne": ["$estado", "Anulada"]},
                ]}}},
                {"$count": "cantidad"},
            ],
        }},
        {"$set": {
            "cantidad_ventas": {
                "$ifNull": [{"$arrayElemAt": ["$ventas_recientes.cantidad", 0]}, 0]
            }
        }},
        {"$project": {
            "_id": 0,
            "id_farmaceutico": 1,
            "nombre": 1,
            "apellido": 1,
            "matricula": 1,
            "cantidad_ventas": 1,
        }},
    ]))
