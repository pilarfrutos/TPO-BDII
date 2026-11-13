import unittest
from unittest.mock import Mock, patch

from src.services.query_03_historial_cliente import q03
from src.services.sincronizacion_neo4j import ErrorSincronizacion


class HistorialClienteTest(unittest.TestCase):
    def test_parametriza_el_id_y_conserva_el_historial_vacio(self):
        db, sesion, tx = Mock(), Mock(), Mock()
        identificador = "CLIENTE-'PRUEBA'"
        esperado = {"id_cliente": identificador, "eventos": []}
        tx.run.return_value.single.return_value.data.return_value = esperado

        with patch("src.services.query_03_historial_cliente.sincronizar_grafo") as refrescar:
            refrescar.side_effect = lambda db, sesion, consulta: consulta(tx)
            self.assertEqual(q03(db, sesion, identificador), esperado)

        args, kwargs = tx.run.call_args
        self.assertIn("$id_cliente", args[0])
        self.assertNotIn(identificador, args[0])
        self.assertEqual(kwargs, {"id_cliente": identificador})
        self.assertEqual(refrescar.call_args.args, (db, sesion))

    def test_cliente_inexistente_devuelve_none(self):
        tx = Mock()
        tx.run.return_value.single.return_value = None
        with patch("src.services.query_03_historial_cliente.sincronizar_grafo") as refrescar:
            refrescar.side_effect = lambda db, sesion, consulta: consulta(tx)
            self.assertIsNone(q03(Mock(), Mock(), "NO-EXISTE"))

    def test_id_invalido_se_rechaza_antes_de_refrescar(self):
        with patch("src.services.query_03_historial_cliente.sincronizar_grafo") as refrescar:
            for identificador in (None, 3, "", "  "):
                with self.subTest(identificador=identificador):
                    with self.assertRaisesRegex(ValueError, "ID de cliente"):
                        q03(Mock(), Mock(), identificador)
            refrescar.assert_not_called()

    def test_fallo_de_sincronizacion_se_propaga(self):
        fallo = ErrorSincronizacion("No se pudo publicar la proyección.")
        with patch("src.services.query_03_historial_cliente.sincronizar_grafo", side_effect=fallo):
            with self.assertRaises(ErrorSincronizacion) as exc:
                q03(Mock(), Mock(), "C001")
        self.assertIs(exc.exception, fallo)
