import unittest
from datetime import date
from unittest.mock import Mock, patch

from src.services import query_06_dispensas_atrasadas as dispensas
from src.services.sincronizacion_neo4j import ErrorSincronizacion


class DispensasAtrasadasTest(unittest.TestCase):
    def test_calcula_hoy_una_vez_antes_del_refresco_y_lo_reutiliza(self):
        db, sesion, tx = Mock(), Mock(), Mock()
        hoy = date(2026, 10, 13)
        filas = [{"receta": {"id_receta": "RC002"}, "cliente": {"id_cliente": "C003"}}]
        tx.run.return_value.data.return_value = filas

        with patch.object(dispensas, "hoy_local", return_value=hoy) as reloj, \
             patch.object(dispensas, "sincronizar_grafo") as refrescar:
            def ejecutar(db_mongo, sesion_neo4j, consulta):
                reloj.assert_called_once_with()
                self.assertIs(db_mongo, db)
                self.assertIs(sesion_neo4j, sesion)
                consulta(tx)
                return consulta(tx)

            refrescar.side_effect = ejecutar
            self.assertEqual(dispensas.q06(db, sesion), filas)
            reloj.assert_called_once_with()

        self.assertEqual(tx.run.call_count, 2)
        for llamada in tx.run.call_args_list:
            self.assertIn("$hoy", llamada.args[0])
            self.assertEqual(llamada.kwargs, {"hoy": hoy})

    def test_acepta_un_corte_controlado_y_devuelve_lista_vacia(self):
        tx = Mock()
        tx.run.return_value.data.return_value = []
        hoy = date(2026, 10, 13)
        with patch.object(dispensas, "hoy_local") as reloj, \
             patch.object(dispensas, "sincronizar_grafo") as refrescar:
            refrescar.side_effect = lambda db, sesion, consulta: consulta(tx)
            self.assertEqual(dispensas.q06(Mock(), Mock(), hoy=hoy), [])
        reloj.assert_not_called()
        self.assertEqual(tx.run.call_args.kwargs, {"hoy": hoy})

    def test_propaga_el_error_de_sincronizacion(self):
        error = ErrorSincronizacion("No se pudo publicar la proyección.")
        with patch.object(dispensas, "sincronizar_grafo", side_effect=error):
            with self.assertRaises(ErrorSincronizacion) as exc:
                dispensas.q06(Mock(), Mock(), hoy=date(2026, 10, 13))
        self.assertIs(exc.exception, error)
