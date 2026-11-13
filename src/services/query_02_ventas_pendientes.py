"""q02: ventas pendientes con el farmacéutico y la sucursal asignados."""


def q02(db):
    """Devuelve ventas pendientes desde MongoDB, ordenadas por fecha e ID."""
    return list(db.ventas.aggregate([
        {"$match": {"estado": "Pendiente"}},
        {"$sort": {"fecha": 1, "id_venta": 1}},
        {"$lookup": {
            "from": "farmaceuticos",
            "localField": "id_farmaceutico",
            "foreignField": "id_farmaceutico",
            "as": "farmaceutico",
            "pipeline": [{"$project": {"_id": 0}}],
        }},
        {"$unwind": "$farmaceutico"},
        {"$lookup": {
            "from": "sucursales",
            "localField": "farmaceutico.id_sucursal",
            "foreignField": "id_sucursal",
            "as": "sucursal",
            "pipeline": [{"$project": {"_id": 0}}],
        }},
        {"$unwind": "$sucursal"},
        {"$project": {
            "_id": 0,
            "id_venta": 1,
            "fecha": 1,
            "total": 1,
            "farmaceutico": {
                "id_farmaceutico": "$farmaceutico.id_farmaceutico",
                "nombre": "$farmaceutico.nombre",
                "apellido": "$farmaceutico.apellido",
                "matricula": "$farmaceutico.matricula",
            },
            "sucursal": {
                "id_sucursal": "$sucursal.id_sucursal",
                "nombre": "$sucursal.nombre",
            },
        }},
    ]))
