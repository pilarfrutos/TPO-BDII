import argparse
from contextlib import redirect_stderr
from io import StringIO
import unittest
from unittest.mock import MagicMock, patch

from scripts import run_query
from src.services.query_13_abm_clientes import ErrorCliente


class RunQueryParserTest(unittest.TestCase):
    def setUp(self):
        self.parser = run_query.crear_parser()

    def test_acepta_codigo_y_alias_numerico(self):
        for entrada, esperado in (("q01", "q01"), ("1", "q01"), ("01", "q01"),
                                  ("q12", "q12"), ("12", "q12")):
            with self.subTest(entrada=entrada):
                self.assertEqual(self.parser.parse_args([entrada]).consulta, esperado)

    def test_parametros_de_lecturas(self):
        q03 = self.parser.parse_args(["3", "--id-cliente", "C001"])
        q10 = self.parser.parse_args(["q10", "--id-sucursal", "S002"])
        self.assertEqual((q03.consulta, q03.id_cliente), ("q03", "C001"))
        self.assertEqual((q10.consulta, q10.id_sucursal), ("q10", "S002"))

    def test_q13_alta_y_modificacion(self):
        alta = self.parser.parse_args([
            "13", "alta", "--id-cliente", "CLI-C01", "--nombre", "Ada",
            "--apellido", "Lovelace", "--dni", "50999999", "--email",
            "ada@example.com", "--telefono", "1155559999", "--ciudad", "CABA",
            "--provincia", "Buenos Aires", "--obra-social", "Sin cobertura",
        ])
        self.assertNotIn("nro_afiliado", run_query._argumentos_q13(alta))

        modificar = self.parser.parse_args([
            "q13", "modificar", "--id-cliente", "CLI-C01",
            "--email", "ada.nueva@example.com",
        ])
        self.assertEqual(run_query._argumentos_q13(modificar), {
            "id_cliente": "CLI-C01", "email": "ada.nueva@example.com"})

    def test_q14_convierte_items_repetibles(self):
        args = self.parser.parse_args([
            "14", "--id-venta", "CLI-V01", "--id-cliente", "C001",
            "--id-farmaceutico", "F001", "--medio-pago", "Efectivo",
            "--item", "PRD001:2", "--item", "PRD011:1",
        ])
        self.assertEqual(args.item, [
            {"id_producto": "PRD001", "cantidad": 2},
            {"id_producto": "PRD011", "cantidad": 1},
        ])

    def test_item_invalido_se_rechaza_antes_de_conectar(self):
        for valor in ("PRD001", "PRD001:0", ":2", "PRD001:dos"):
            with self.subTest(valor=valor), self.assertRaises(argparse.ArgumentTypeError):
                run_query.item_venta(valor)


class RunQueryExecutionTest(unittest.TestCase):
    def test_q13_pasa_solo_los_campos_informados(self):
        args = run_query.crear_parser().parse_args([
            "13", "modificar", "--id-cliente", "C001", "--telefono", "1155550000",
        ])
        db = MagicMock()
        with patch.object(run_query, "q13", return_value={"ok": True}) as consulta:
            self.assertEqual(run_query.ejecutar_mongo(db, args), {"ok": True})
        consulta.assert_called_once_with(
            db, "modificar", id_cliente="C001", telefono="1155550000")

    def test_q15_abre_una_transaccion(self):
        args = run_query.crear_parser().parse_args(["15", "--id-venta", "CLI-V01"])
        db = MagicMock()
        sesion = MagicMock()
        db.client.start_session.return_value.__enter__.return_value = sesion
        sesion.with_transaction.side_effect = lambda funcion: funcion(sesion)
        with patch.object(run_query, "q15", return_value=[{"id_lote": "L001"}]) as consulta:
            resultado = run_query.ejecutar_mongo(db, args)
        self.assertEqual(resultado, [{"id_lote": "L001"}])
        consulta.assert_called_once_with(db, "CLI-V01", sesion)

    def test_error_de_dominio_es_legible_y_conserva_codigo(self):
        salida = StringIO()
        with patch.object(run_query, "ejecutar",
                          side_effect=ErrorCliente("inexistente", "No existe C999")), \
             redirect_stderr(salida):
            codigo = run_query.main(["13", "baja", "--id-cliente", "C999"])
        self.assertEqual(codigo, 1)
        self.assertEqual(salida.getvalue(),
                         "ERROR q13 [inexistente]: No existe C999\n")


if __name__ == "__main__":
    unittest.main()
