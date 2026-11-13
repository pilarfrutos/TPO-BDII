"""Verifica q13 (ABM de clientes) en una base temporal que se elimina al final.

Uso: python tests/servicios/verify_q13.py [--evidencia]
Con --evidencia imprime en JSON el antes/después de cada operación y los rechazos.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
from threading import Barrier
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.check_connections import conectar_mongo
from scripts.loaders.load_mongo import cargar
from src.services.query_13_abm_clientes import ErrorCliente, q13
from src.utils.datos_csv import ORIGINALES_DIR, leer_datos
from src.utils.datos_mongo import leer_snapshot
from src.utils.proyeccion_neo4j import preparar_proyeccion

NUEVO = dict(id_cliente="Q13-C01", nombre="Ana", apellido="Prueba", dni="45111222",
             email="ana.p@example.com", telefono="1144556677", ciudad="La Plata",
             provincia="Buenos Aires", obra_social="IOMA", nro_afiliado="IO-123456")


def rechazo(codigo, db, operacion, **argumentos):
    """Ejecuta una operación que debe fallar y comprueba que no cambió ningún cliente."""
    antes = list(db.clientes.find({}, {"_id": 0}).sort("id_cliente", 1))
    try:
        q13(db, operacion, **argumentos)
    except ErrorCliente as exc:
        assert exc.codigo == codigo, f"{operacion} {argumentos}: {exc.codigo} != {codigo} ({exc})"
        assert list(db.clientes.find({}, {"_id": 0}).sort("id_cliente", 1)) == antes
        return {"operacion": operacion, "argumentos": argumentos, "codigo": exc.codigo,
                "mensaje": str(exc)}
    raise AssertionError(f"{operacion} {argumentos} debía rechazarse con {codigo}")


def verificar(client, db):
    cargar(db, leer_datos([ORIGINALES_DIR]))
    evidencia = []
    iniciales = db.clientes.count_documents({})

    # Alta válida y rechazos de unicidad y formato.
    resultado = q13(db, "alta", **NUEVO)
    assert resultado["antes"] is None
    assert resultado["despues"] == dict(NUEVO, activo=True)
    assert db.clientes.find_one({"id_cliente": "Q13-C01"}, {"_id": 0}) == resultado["despues"]
    evidencia.append(resultado)
    evidencia.append(rechazo("dni_duplicado", db, "alta", **dict(NUEVO, id_cliente="Q13-C02",
                                                                 dni="31245678")))
    rechazo("id_duplicado", db, "alta", **dict(NUEVO, id_cliente="C001", dni="45000001"))
    for campo, valor in (("dni", "31.245.678"), ("email", "sin-arroba"), ("telefono", "11 4455"),
                         ("nombre", "  "), ("obra_social", "Medifé"), ("nro_afiliado", None)):
        evidencia.append(rechazo("datos_invalidos", db, "alta",
                                 **(dict(NUEVO, id_cliente="Q13-C03", dni="45000002")
                                    | {campo: valor})))
    rechazo("datos_invalidos", db, "alta", **dict(NUEVO, id_cliente="Q13-C03", dni="45000002",
                                                  obra_social="Sin cobertura"))
    sin_cobertura = q13(db, "alta", **dict(NUEVO, id_cliente="Q13-C04", dni="45000003",
                                           obra_social="Sin cobertura", nro_afiliado=""))
    assert sin_cobertura["despues"]["nro_afiliado"] is None

    # Altas concurrentes con el mismo DNI: solo una prospera.
    hilos = 8
    barrera = Barrier(hilos)

    def alta_concurrente(n):
        barrera.wait()
        try:
            q13(db, "alta", **dict(NUEVO, id_cliente=f"Q13-K{n}", dni="45999999"))
            return "ok"
        except ErrorCliente as exc:
            return exc.codigo

    with ThreadPoolExecutor(hilos) as ejecutor:
        resultados = sorted(ejecutor.map(alta_concurrente, range(hilos)))
    assert resultados == ["dni_duplicado"] * (hilos - 1) + ["ok"], resultados
    assert db.clientes.count_documents({"dni": "45999999"}) == 1

    # Modificación de contacto: solo cambian los campos informados.
    resultado = q13(db, "modificar", id_cliente="C002", email="martin.gomez@example.com",
                    telefono="3415000000")
    assert resultado["despues"] == dict(resultado["antes"], email="martin.gomez@example.com",
                                        telefono="3415000000")
    evidencia.append(resultado)

    # Cobertura: pasar a 'Sin cobertura' vacía el afiliado; cambiar de obra lo exige.
    resultado = q13(db, "modificar", id_cliente="C001", obra_social="Sin cobertura")
    assert resultado["despues"]["nro_afiliado"] is None
    evidencia.append(resultado)
    evidencia.append(rechazo("datos_invalidos", db, "modificar", id_cliente="C005",
                             obra_social="PAMI"))
    rechazo("datos_invalidos", db, "modificar", id_cliente="C002", obra_social="OSDE")
    rechazo("datos_invalidos", db, "modificar", id_cliente="C005", nro_afiliado="X-1")
    resultado = q13(db, "modificar", id_cliente="C005", obra_social="PAMI",
                    nro_afiliado="PA-900001")
    assert (resultado["despues"]["obra_social"], resultado["despues"]["nro_afiliado"]) == (
        "PAMI", "PA-900001")
    evidencia.append(resultado)
    resultado = q13(db, "modificar", id_cliente="C004", nro_afiliado="IO-999999")
    assert resultado["despues"]["obra_social"] == "IOMA"

    rechazo("inexistente", db, "modificar", id_cliente="C999", email="x@example.com")
    rechazo("datos_invalidos", db, "modificar", id_cliente="C002")
    rechazo("datos_invalidos", db, "modificar", id_cliente="C002", email="no-es-email")
    try:
        q13(db, "modificar", id_cliente="C002", dni="11111111")
    except TypeError:
        pass  # El DNI, el nombre y el domicilio no se modifican por q13.
    else:
        raise AssertionError("modificar no debe aceptar dni")

    # Baja lógica: el documento y su historial quedan; no se puede modificar sin reactivar.
    ventas_c003 = db.ventas.count_documents({"id_cliente": "C003"})
    resultado = q13(db, "baja", id_cliente="C003")
    assert resultado["despues"] == dict(resultado["antes"], activo=False)
    assert db.clientes.find_one({"id_cliente": "C003"})["activo"] is False
    assert db.ventas.count_documents({"id_cliente": "C003"}) == ventas_c003 > 0
    evidencia.append(resultado)
    evidencia.append(rechazo("inactivo", db, "baja", id_cliente="C003"))
    evidencia.append(rechazo("inactivo", db, "modificar", id_cliente="C003",
                             email="carla@example.com"))
    rechazo("inexistente", db, "baja", id_cliente="C999")
    rechazo("datos_invalidos", db, "borrar", id_cliente="C003")
    resultado = q13(db, "reactivar", id_cliente="C003")
    assert resultado["despues"]["activo"] is True
    rechazo("activo", db, "reactivar", id_cliente="C003")
    q13(db, "baja", id_cliente="C003")

    # Nunca se elimina un cliente.
    assert db.clientes.count_documents({}) == iniciales + 3

    # Efecto en el grafo: la próxima proyección desde MongoDB refleja alta, cambios
    # y baja, y conserva las relaciones históricas del cliente dado de baja.
    proyeccion = preparar_proyeccion(leer_snapshot(client, db))
    clientes = {c["id_cliente"]: c for c in proyeccion["clientes"]}
    assert clientes["Q13-C01"]["activo"] is True
    assert clientes["C003"]["activo"] is False
    assert clientes["C002"]["email"] == "martin.gomez@example.com"
    assert clientes["C001"]["nro_afiliado"] is None
    assert sum(v["id_cliente"] == "C003" for v in proyeccion["ventas"]) == ventas_c003
    return evidencia


def main():
    cliente, _ = conectar_mongo()
    nombre = f"farmared_test_q13_{uuid4().hex}"
    with cliente:
        try:
            evidencia = verificar(cliente, cliente[nombre])
        finally:
            cliente.drop_database(nombre)
    if "--evidencia" in sys.argv:
        print(json.dumps(evidencia, ensure_ascii=False, indent=2))
    print("q13: OK en MongoDB")


if __name__ == "__main__":
    main()
