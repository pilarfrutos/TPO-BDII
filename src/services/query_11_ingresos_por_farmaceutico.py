from src.utils.calendario import hoy_local, limites_mes


def q11(db, *, hoy=None):
    inicio, fin = limites_mes(hoy if hoy is not None else hoy_local())
    return list(db.ventas.aggregate([
        {"$match": {"estado": "Completada", "fecha": {"$gte": inicio, "$lt": fin}}},
        {"$group": {"_id": "$id_farmaceutico", "ingresos": {"$sum": "$total"}}},
        {"$sort": {"_id": 1}},
        {"$lookup": {
            "from": "farmaceuticos",
            "localField": "_id",
            "foreignField": "id_farmaceutico",
            "as": "farmaceutico",
            "pipeline": [{"$project": {"_id": 0}}],
        }},
        {"$unwind": "$farmaceutico"},
        {"$project": {"_id": 0, "id_farmaceutico": "$_id", "nombre": "$farmaceutico.nombre",
                      "apellido": "$farmaceutico.apellido", "matricula": "$farmaceutico.matricula",
                      "ingresos": 1}},
    ]))
