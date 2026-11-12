def q07(db):
    return list(db.ventas.aggregate([
        {"$match": {"estado": "Completada"}},
        {"$lookup": {
            "from": "detalle_ventas",
            "localField": "id_venta",
            "foreignField": "id_venta",
            "as": "detalle",
            "pipeline": [{"$project": {"_id": 0}}],
        }},
        {"$unwind": "$detalle"},
        {"$group": {"_id": "$detalle.id_producto", "unidades": {"$sum": "$detalle.cantidad"}}},
        {"$sort": {"unidades": -1, "_id": 1}},
        {"$limit": 5},
        {"$lookup": {
            "from": "productos",
            "localField": "_id",
            "foreignField": "id_producto",
            "as": "producto",
            "pipeline": [{"$project": {"_id": 0}}],
        }},
        {"$unwind": "$producto"},
        {"$project": {"_id": 0, "id_producto": "$_id", "producto": "$producto.nombre", "unidades": 1}},
    ]))
