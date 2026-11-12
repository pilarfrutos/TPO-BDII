def q08(db):
    return list(db.stock_lotes.aggregate([
        {"$match": {"unidades": {"$lt": 50}}},
        {"$sort": {"id_lote": 1}},
        {"$lookup": {
            "from": "productos",
            "localField": "id_producto",
            "foreignField": "id_producto",
            "as": "producto",
            "pipeline": [{"$project": {"_id": 0}}],
        }},
        {"$unwind": "$producto"},
        {"$lookup": {
            "from": "sucursales",
            "localField": "id_sucursal",
            "foreignField": "id_sucursal",
            "as": "sucursal",
            "pipeline": [{"$project": {"_id": 0}}],
        }},
        {"$unwind": "$sucursal"},
        {"$lookup": {
            "from": "proveedores",
            "localField": "producto.id_proveedor",
            "foreignField": "id_proveedor",
            "as": "proveedor",
            "pipeline": [{"$project": {"_id": 0}}],
        }},
        {"$unwind": "$proveedor"},
        {"$project": {"_id": 0, "id_lote": 1, "nro_lote": 1, "vencimiento": 1, "unidades": 1,
                      "producto": {"id_producto": "$id_producto", "nombre": "$producto.nombre"},
                      "sucursal": {"id_sucursal": "$id_sucursal", "nombre": "$sucursal.nombre"},
                      "proveedor": {"id_proveedor": "$proveedor.id_proveedor",
                                    "razon_social": "$proveedor.razon_social"}}},
    ]))
