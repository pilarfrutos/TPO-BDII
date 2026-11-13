import unittest
from unittest.mock import Mock, patch

from src.services.query_04_recetas_por_cliente import q04
from src.services.sincronizacion_neo4j import ErrorSincronizacion


class RecetasPorClienteTest(unittest.TestCase):
    def test_materializa_las_filas_dentro_del_refresco(self):
        db, sesion, tx = Mock(), Mock(), Mock()
        filas = [{"id_cliente": "C001", "nombre": "Lucía", "apellido": "Fernández",
                  "cantidad_recetas": 2}]
        with patch("src.services.query_04_recetas_por_cliente.sincronizar_grafo") as refrescar:
            refrescar.side_effect = lambda db, sesion, consulta: consulta(tx)
            for esperado in (filas, []):
                with self.subTest(esperado=esperado):
                    tx.run.return_value.data.return_value = esperado
                    self.assertEqual(q04(db, sesion), esperado)
                    self.assertEqual(refrescar.call_args.args, (db, sesion))

        self.assertEqual(tx.run.return_value.data.call_count, 2)

    def test_propaga_el_error_de_sincronizacion(self):
        fallo = ErrorSincronizacion("No se pudo publicar la proyección.")
        with patch("src.services.query_04_recetas_por_cliente.sincronizar_grafo", side_effect=fallo):
            with self.assertRaises(ErrorSincronizacion) as exc:
                q04(Mock(), Mock())
        self.assertIs(exc.exception, fallo)
