def q01(db):
    return list(db.productos.aggregate([
        {"$match": {"activo": True}},
        {"$sort": {"id_producto": 1}},
        {"$lookup": {
            "from": "proveedores",
            "localField": "id_proveedor",
            "foreignField": "id_proveedor",
            "as": "proveedor",
            "pipeline": [{"$project": {"_id": 0}}],
        }},
        {"$unwind": "$proveedor"},
        {"$project": {"_id": 0}},
    ]))
