import unittest
from unittest.mock import Mock, patch

from neo4j.exceptions import IncompleteCommit, ServiceUnavailable
from pymongo.errors import ConnectionFailure

from src.services import sincronizacion_neo4j as sincronizacion
from src.utils.datos_csv import ENTIDADES


class SincronizacionNeo4jTest(unittest.TestCase):
    def test_bloquea_antes_de_leer_y_consulta_despues_de_publicar(self):
        db = Mock()
        sesion = Mock()
        transaccion = Mock()
        pasos = []
        def ejecutar_cypher(cypher, **_):
            pasos.append("bloqueo" if "ControlProyeccion" in cypher else "limpieza")
            return Mock()

        transaccion.run.side_effect = ejecutar_cypher

        def ejecutar(callback, *args):
            resultado = callback(transaccion, *args)
            pasos.append("commit")
            return resultado

        def consultar(tx):
            self.assertIs(tx, transaccion)
            pasos.append("consulta")
            return ["C001"]

        sesion.execute_write.side_effect = ejecutar
        with patch.object(sincronizacion, "leer_proyeccion") as leer, \
             patch.object(sincronizacion, "cargar") as cargar:
            datos = {nombre: [] for nombre in ENTIDADES}
            leer.side_effect = lambda _: pasos.append("snapshot") or datos
            cargar.side_effect = lambda *_: pasos.append("publicación")
            self.assertEqual(sincronizacion.sincronizar_grafo(db, sesion, consultar), ["C001"])

        self.assertEqual(pasos, ["bloqueo", "snapshot"] + ["limpieza"] * len(ENTIDADES)
                         + ["publicación", "consulta", "commit"])
        leer.assert_called_once_with(db)
        cargar.assert_called_once_with(transaccion, datos)

    def test_error_de_mongo_y_datos_invalidos_se_distinguen(self):
        db = Mock()
        with patch.object(sincronizacion, "leer_snapshot", side_effect=ConnectionFailure):
            with self.assertRaisesRegex(sincronizacion.ErrorSincronizacion, "leer el snapshot"):
                sincronizacion.leer_proyeccion(db)
        with patch.object(sincronizacion, "leer_snapshot", return_value={}):
            with self.assertRaisesRegex(sincronizacion.ErrorSincronizacion, "Datos de MongoDB inválidos"):
                sincronizacion.leer_proyeccion(db)

    def test_snapshot_vacio_pide_carga_inicial(self):
        datos = {nombre: [] for nombre in ENTIDADES}
        with patch.object(sincronizacion, "leer_snapshot", return_value=datos):
            with self.assertRaisesRegex(sincronizacion.ErrorSincronizacion, "Ejecutá load_mongo.py"):
                sincronizacion.leer_proyeccion(Mock())

    def test_neo4j_caido_no_ejecuta_la_consulta(self):
        sesion = Mock()
        consulta = Mock()
        sesion.run.side_effect = ServiceUnavailable
        with self.assertRaisesRegex(sincronizacion.ErrorSincronizacion, "publicar la proyección"):
            sincronizacion.sincronizar_grafo(Mock(), sesion, consulta)
        sesion.execute_write.assert_not_called()
        consulta.assert_not_called()

    def test_commit_indeterminado_descarta_el_resultado_de_la_consulta(self):
        sesion = Mock()
        transaccion = Mock()
        consulta = Mock(return_value=["C001"])

        def ejecutar(callback, *args):
            callback(transaccion, *args)
            raise IncompleteCommit

        sesion.execute_write.side_effect = ejecutar
        with patch.object(sincronizacion, "leer_proyeccion", return_value={n: [] for n in ENTIDADES}):
            with self.assertRaisesRegex(sincronizacion.ErrorSincronizacion, "commit quedó indeterminado"):
                sincronizacion.sincronizar_grafo(Mock(), sesion, consulta)
        consulta.assert_called_once_with(transaccion)
