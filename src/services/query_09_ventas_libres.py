"""q09: ventas libres menores a 5.000 ARS, excluidas las anuladas."""


def q09(db):
    """Devuelve ventas libres no anuladas con total menor a 5.000 ARS."""
    return list(db.ventas.aggregate([
        {"$match": {
            "tipo": "Venta libre",
            "total": {"$lt": 5000},
            "estado": {"$ne": "Anulada"},
        }},
        {"$sort": {"total": 1, "id_venta": 1}},
        {"$project": {"_id": 0}},
    ]))
