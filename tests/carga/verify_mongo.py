"""Verifica la carga MongoDB (T05) en una base temporal que se elimina al final.

Uso: python tests/carga/verify_mongo.py
"""
from pathlib import Path
import sys
from unittest import TestCase
from uuid import uuid4

from pymongo.errors import DuplicateKeyError, WriteError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.check_connections import conectar_mongo
from scripts.loaders.load_mongo import ENTIDADES, cargar, reiniciar, verificar
from src.services.query_14_registro_venta import ErrorVenta, q14
from src.utils.datos_csv import leer_datos, para_mongo
from src.utils.datos_mongo import leer_snapshot
from src.utils.proyeccion_neo4j import preparar_proyeccion


def contenido(db):
    return {n: sorted(db[n].find({}, {"_id": 0}), key=lambda d: d[c])
            for n, (_, c, _) in ENTIDADES.items()}


def verificar_carga(client, db):
    datos = leer_datos()
    total = sum(map(len, datos.values()))

    # 1. Primera carga y repetición: mismos conteos, IDs y contenido.
    primera = cargar(db, datos)
    assert sum(n for n, _ in primera.values()) == total
    despues_primera = contenido(db)
    segunda = cargar(db, datos)
    assert all(n == 0 and e == len(datos[c]) for c, (n, e) in segunda.items()), segunda
    assert contenido(db) == despues_primera, "la segunda carga no debe cambiar nada"
    informe, problemas = verificar(client, db, datos)
    assert problemas == [], problemas
    assert all(not i["faltantes"] and not i["modificados"] and not i["propios"]
               for i in informe.values()), informe

    # 2. El stock cargado es el del CSV: las ventas históricas no se vuelven a descontar.
    lotes = {l["id_lote"]: l["unidades"] for l in db.stock_lotes.find()}
    assert lotes == {l["id_lote"]: l["unidades"] for l in datos["stock_lotes"]}

    # 3. Índices únicos de ID, DNI y matrícula.
    duplicados = (
        ("clientes", {"id_cliente": "DUP-C"}),        # mismo DNI que C001
        ("farmaceuticos", {"id_farmaceutico": "DUP-F"}),  # misma matrícula que F001
        ("ventas", {}),                               # mismo id_venta que V001
    )
    for nombre, cambios in duplicados:
        try:
            db[nombre].insert_one(para_mongo(dict(datos[nombre][0], **cambios)))
        except DuplicateKeyError:
            continue
        raise AssertionError(f"{nombre}: el índice único debe rechazar el duplicado")

    # 4. Operaciones de negocio: la recarga no las pisa y la verificación las informa.
    db.stock_lotes.update_one({"id_lote": "L001"}, {"$inc": {"unidades": -3}})
    db.recetas.update_one({"id_receta": "RC006"},
                          {"$set": {"dispensas_realizadas": 1, "estado": "Completada"}})
    db.clientes.update_one({"id_cliente": "C003"}, {"$set": {"activo": False}})
    nuevo = para_mongo(dict(datos["clientes"][0], id_cliente="Q13-C01", dni="99999999"))
    db.clientes.insert_one(nuevo)
    cargar(db, datos)
    assert db.stock_lotes.find_one({"id_lote": "L001"})["unidades"] == lotes["L001"] - 3
    assert db.recetas.find_one({"id_receta": "RC006"})["dispensas_realizadas"] == 1
    assert db.clientes.find_one({"id_cliente": "C003"})["activo"] is False
    informe, problemas = verificar(client, db, datos)
    assert problemas == [], problemas
    assert informe["stock_lotes"]["modificados"] == {"L001": ["unidades"]}
    assert informe["recetas"]["modificados"] == {"RC006": ["dispensas_realizadas", "estado"]}
    assert informe["clientes"]["modificados"] == {"C003": ["activo"]}
    assert informe["clientes"]["propios"] == ["Q13-C01"]

    # 5. Un registro borrado se informa como faltante y la carga aditiva lo repone.
    db.productos.delete_one({"id_producto": "PRD002"})
    _, problemas = verificar(client, db, datos)
    assert any("productos: faltan PRD002" in p for p in problemas), problemas
    assert cargar(db, datos)["productos"][0] == 1

    # 6. Interfaz con el grafo: el snapshot cumple el contrato de la proyección.
    proyeccion = preparar_proyeccion(leer_snapshot(client, db))
    assert len(proyeccion["clientes"]) == len(datos["clientes"]) + 1

    # 7. Reinicio explícito: vuelve exactamente al estado de los CSV.
    reiniciar(db)
    cargar(db, datos)
    assert contenido(db) == despues_primera


def verificar_transicion(client, db):
    """Documentos de una carga exploratoria (fechas como texto, sin índices)."""
    datos = leer_datos()
    exploratorio = dict(para_mongo(datos["ventas"][0]), fecha="2026-09-10")
    db.ventas.insert_one(exploratorio)
    db.ventas.insert_one(dict(exploratorio, _id="duplicada"))

    try:
        cargar(db, datos)
    except RuntimeError as exc:
        assert "ventas" in str(exc) and "--reiniciar" in str(exc), exc
    else:
        raise AssertionError("con IDs repetidos no se puede crear el índice único")
    _, problemas = verificar(client, db, datos)
    assert any("ventas: hay documentos con id_venta repetido" in p for p in problemas), problemas

    db.ventas.delete_one({"_id": "duplicada"})
    cargar(db, datos)  # El upsert conserva el documento exploratorio.
    informe, problemas = verificar(client, db, datos)
    assert informe["ventas"]["modificados"] == {"V001": ["fecha"]}
    assert any("contrato de datos: ventas[V001].fecha" in p for p in problemas), problemas

    reiniciar(db)
    cargar(db, datos)
    _, problemas = verificar(client, db, datos)
    assert problemas == [], problemas
    assert db.ventas.find_one({"id_venta": "V001"})["fecha"] == para_mongo(datos["ventas"][0])["fecha"]


def verificar_reglas(client, db):
    datos = leer_datos()
    # Simula una colección preexistente a la incorporación de validadores.
    db.productos.insert_one(para_mongo(dict(datos["productos"][0], condicion_venta="Bajo recetaa")))
    cargar(db, datos)
    with TestCase().assertRaises(ErrorVenta) as rechazo:
        q14(db, "H04-V", "C001", "F001", "Efectivo", [{"id_producto": "PRD001", "cantidad": 1}])
    assert rechazo.exception.codigo == "producto_invalido"
    assert db.ventas.find_one({"id_venta": "H04-V"}) is None

    for coleccion, filtro, campos in (
        (db.productos, {"id_producto": "PRD002"}, {"condicion_venta": "Bajo recetaa"}),
        (db.stock_lotes, {"id_lote": "L001"}, {"unidades": -1}),
        (db.stock_lotes, {"id_lote": "L001"}, {"unidades": 1.5}),
        (db.recetas, {"id_receta": "RC002"}, {"dispensas_autorizadas": 4}),
        (db.recetas, {"id_receta": "RC006"}, {"dispensas_realizadas": 1}),
    ):
        with TestCase().assertRaises(WriteError) as rechazo:
            coleccion.update_one(filtro, {"$set": campos})
        assert rechazo.exception.code == 121

    db.stock_lotes.update_one({"id_lote": "L001"}, {"$set": {"unidades": -1}},
                              bypass_document_validation=True)
    db.ventas.update_one({"id_venta": "V003"}, {"$set": {"total": 1, "id_receta": "RC005"}})
    _, problemas = verificar(client, db, datos)
    for mensaje in ("PRD001].condicion_venta", "L001].unidades", "V003: total inconsistente",
                    "V003].id_receta: RC005 pertenece a otro cliente"):
        assert any(mensaje in p for p in problemas), problemas


def main():
    cliente, _ = conectar_mongo()
    with cliente:
        for prueba in (verificar_carga, verificar_transicion, verificar_reglas):
            nombre = f"farmared_test_carga_{uuid4().hex}"
            try:
                prueba(cliente, cliente[nombre])
            finally:
                cliente.drop_database(nombre)
            print(f"{prueba.__name__}: OK")


if __name__ == "__main__":
    main()
