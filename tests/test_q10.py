import unittest
from unittest.mock import Mock, patch

from src.services import query_10_clientes_por_sucursal as clientes
from src.services.sincronizacion_neo4j import ErrorSincronizacion


class ClientesPorSucursalTest(unittest.TestCase):
    def test_parametriza_el_id_y_materializa_la_respuesta(self):
        db, sesion, tx = Mock(), Mock(), Mock()
        identificador = "SUCURSAL-'PRUEBA'"
        with patch.object(clientes, "sincronizar_grafo") as refrescar:
            refrescar.side_effect = lambda db, sesion, consulta: consulta(tx)
            for filas in ([{"id_cliente": "C004", "nombre": "Federico", "apellido": "Navarro"}], []):
                with self.subTest(filas=filas):
                    tx.run.return_value.data.return_value = filas
                    self.assertEqual(clientes.q10(db, sesion, identificador), filas)
                    self.assertEqual(refrescar.call_args.args, (db, sesion))

        args, kwargs = tx.run.call_args
        self.assertIn("$id_sucursal", args[0])
        self.assertNotIn(identificador, args[0])
        self.assertEqual(kwargs, {"id_sucursal": identificador})

    def test_rechaza_id_invalido_antes_de_refrescar(self):
        with patch.object(clientes, "sincronizar_grafo") as refrescar:
            for identificador in (None, 10, "", "  "):
                with self.subTest(identificador=identificador):
                    with self.assertRaisesRegex(ValueError, "ID de sucursal"):
                        clientes.q10(Mock(), Mock(), identificador)
            refrescar.assert_not_called()

    def test_propaga_el_fallo_del_refresco(self):
        fallo = ErrorSincronizacion("No se pudo publicar la proyección.")
        with patch.object(clientes, "sincronizar_grafo", side_effect=fallo):
            with self.assertRaises(ErrorSincronizacion) as exc:
                clientes.q10(Mock(), Mock(), "S002")
        self.assertIs(exc.exception, fallo)
