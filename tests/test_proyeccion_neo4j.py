import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

from src.services.sincronizacion_neo4j import cargar
from src.utils.datos_csv import ORIGINALES_DIR, leer_datos, para_mongo
from src.utils.proyeccion_neo4j import preparar_proyeccion


class ContratoProyeccionTest(unittest.TestCase):
    def setUp(self):
        self.datos = leer_datos([ORIGINALES_DIR])

    def test_proyecta_originales_y_conserva_datos_historicos(self):
        datos = preparar_proyeccion(self.datos)
        self.assertEqual(sum(map(len, datos.values())), 103)
        ventas = {fila["id_venta"]: fila for fila in datos["ventas"]}
        recetas = {fila["id_receta"]: fila for fila in datos["recetas"]}
        farmaceuticos = {fila["id_farmaceutico"]: fila for fila in datos["farmaceuticos"]}

        self.assertIsNone(ventas["V002"]["id_receta"])
        self.assertIsNone(ventas["V002"]["id_sucursal"])
        self.assertIsNone(recetas["RC001"]["proxima_dispensa"])
        self.assertEqual(recetas["RC002"]["proxima_dispensa"], date(2026, 9, 15))
        self.assertEqual(ventas["V001"]["id_farmaceutico"], "F004")
        self.assertIs(farmaceuticos["F004"]["activo"], False)

    def test_documentos_mongo_y_csv_producen_la_misma_proyeccion(self):
        documentos = {
            nombre: [dict(para_mongo(fila), _id=i) for i, fila in enumerate(filas)]
            for nombre, filas in self.datos.items()
        }
        ventas = {fila["id_venta"]: fila for fila in documentos["ventas"]}
        del ventas["V002"]["id_receta"]
        ventas["V003"]["fecha"] = datetime(2026, 9, 9, 21, tzinfo=timezone(timedelta(hours=-3)))
        documentos["recetas"][0]["proxima_dispensa"] = ""
        documentos["stock_lotes"][0]["vencimiento"] = documentos["stock_lotes"][0][
            "vencimiento"
        ].replace(tzinfo=None)

        self.assertEqual(preparar_proyeccion(documentos), preparar_proyeccion(self.datos))
        self.assertIn("_id", ventas["V002"])
        self.assertNotIn("id_receta", ventas["V002"])

    def test_conserva_la_sucursal_de_la_venta_independiente_del_farmaceutico(self):
        venta = self.datos["ventas"][0]
        venta["id_sucursal"] = "S001"
        venta["registro"] = {"descuento": []}
        proyectada = preparar_proyeccion(self.datos)["ventas"][0]
        self.assertEqual(proyectada["id_sucursal"], "S001")
        self.assertNotIn("registro", proyectada)

    def test_valida_referencias_obligatorias_y_opcionales_informadas(self):
        venta = self.datos["ventas"][0]
        for campo, invalido in (("id_cliente", "C999"), ("id_receta", "RC999"),
                                ("id_sucursal", "S999")):
            with self.subTest(campo=campo):
                original = venta.get(campo)
                venta[campo] = invalido
                with self.assertRaisesRegex(ValueError, rf"ventas\[V001\]\.{campo}: referencia"):
                    preparar_proyeccion(self.datos)
                venta[campo] = original

    def test_rechaza_campo_obligatorio_ausente(self):
        del self.datos["ventas"][0]["id_cliente"]
        with self.assertRaisesRegex(ValueError, r"ventas\[V001\]\.id_cliente: se esperaba texto"):
            preparar_proyeccion(self.datos)

    def test_rechaza_tipos_incorrectos(self):
        casos = (
            ("clientes", "dni", 12345678),
            ("farmaceuticos", "matricula", 18041),
            ("farmaceuticos", "activo", 0),
            ("ventas", "total", True),
            ("ventas", "fecha", "2026-09-10"),
        )
        for nombre, campo, invalido in casos:
            with self.subTest(campo=campo):
                fila = self.datos[nombre][0]
                original = fila[campo]
                fila[campo] = invalido
                with self.assertRaisesRegex(ValueError, rf"{nombre}\[.+\]\.{campo}: se esperaba"):
                    preparar_proyeccion(self.datos)
                fila[campo] = original

    def test_rechaza_sucursal_de_venta_con_tipo_invalido(self):
        for valor in (123, ""):
            with self.subTest(valor=valor):
                self.datos["ventas"][0]["id_sucursal"] = valor
                with self.assertRaisesRegex(ValueError, r"ventas\[V001\]\.id_sucursal: se esperaba"):
                    preparar_proyeccion(self.datos)

    def test_rechaza_ids_repetidos(self):
        self.datos["ventas"].append(self.datos["ventas"][0])
        with self.assertRaisesRegex(ValueError, r"ventas\[V001\]: identificador repetido"):
            preparar_proyeccion(self.datos)

    def test_carga_envia_ventas_con_y_sin_receta_a_reconciliacion(self):
        tx = Mock()
        cargar(tx, preparar_proyeccion(self.datos))
        referencias = next(
            llamada.kwargs["referencias"]
            for llamada in tx.run.call_args_list
            if "[:CON_RECETA]" in llamada.args[0]
        )
        self.assertIn({"origen": "V001", "destino": "RC007"}, referencias)
        self.assertIn({"origen": "V002", "destino": None}, referencias)


if __name__ == "__main__":
    unittest.main()
