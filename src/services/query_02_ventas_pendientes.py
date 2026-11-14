"""q02: ventas pendientes con el farmacéutico y la sucursal asignados."""


def q02(db):
    """Devuelve ventas pendientes con la sucursal de la venta, por fecha e ID.

    Para documentos sin sucursal usa la asignación actual del farmacéutico.
    """
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
        {"$set": {"sucursal_venta": {"$ifNull": ["$id_sucursal", "$farmaceutico.id_sucursal"]}}},
        {"$lookup": {
            "from": "sucursales",
            "localField": "sucursal_venta",
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
