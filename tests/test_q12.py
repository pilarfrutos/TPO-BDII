import unittest
from datetime import date
from unittest.mock import Mock, patch

from src.services import query_12_clientes_sin_ventas as clientes
from src.services.sincronizacion_neo4j import ErrorSincronizacion
from src.utils.calendario import inicio_ultimo_anio


class ClientesSinVentasTest(unittest.TestCase):
    def test_corte_anual_y_bisiesto(self):
        casos = (
            (date(2026, 11, 13), date(2025, 11, 13)),
            (date(2024, 2, 29), date(2023, 2, 28)),
            (date(2025, 2, 28), date(2024, 2, 28)),
            (date(2024, 3, 1), date(2023, 3, 1)),
        )
        for hoy, inicio in casos:
            with self.subTest(hoy=hoy):
                self.assertEqual(inicio_ultimo_anio(hoy), inicio)

    def test_fija_el_periodo_antes_del_refresco_y_lo_reutiliza(self):
        db, sesion, tx = Mock(), Mock(), Mock()
        hoy = date(2026, 11, 13)
        filas = [{"id_cliente": "C008", "nombre": "Hugo", "apellido": "Mansilla"}]
        tx.run.return_value.data.return_value = filas

        with patch.object(clientes, "hoy_local", return_value=hoy) as reloj, \
             patch.object(clientes, "sincronizar_grafo") as refrescar:
            def ejecutar(db_mongo, sesion_neo4j, consulta):
                reloj.assert_called_once_with()
                self.assertIs(db_mongo, db)
                self.assertIs(sesion_neo4j, sesion)
                consulta(tx)
                return consulta(tx)

            refrescar.side_effect = ejecutar
            self.assertEqual(clientes.q12(db, sesion), filas)
            reloj.assert_called_once_with()

        self.assertEqual(tx.run.call_count, 2)
        for llamada in tx.run.call_args_list:
            self.assertEqual(llamada.kwargs, {"inicio": date(2025, 11, 13), "hoy": hoy})

    def test_corte_controlado_y_resultado_vacio(self):
        tx = Mock()
        tx.run.return_value.data.return_value = []
        hoy = date(2024, 2, 29)
        with patch.object(clientes, "hoy_local") as reloj, \
             patch.object(clientes, "sincronizar_grafo") as refrescar:
            refrescar.side_effect = lambda db, sesion, consulta: consulta(tx)
            self.assertEqual(clientes.q12(Mock(), Mock(), hoy=hoy), [])
        reloj.assert_not_called()
        self.assertEqual(tx.run.call_args.kwargs, {"inicio": date(2023, 2, 28), "hoy": hoy})

    def test_propaga_el_error_del_refresco(self):
        error = ErrorSincronizacion("No se pudo publicar la proyección.")
        with patch.object(clientes, "sincronizar_grafo", side_effect=error):
            with self.assertRaises(ErrorSincronizacion) as exc:
                clientes.q12(Mock(), Mock(), hoy=date(2026, 11, 13))
        self.assertIs(exc.exception, error)
