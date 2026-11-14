import csv
import tempfile
import unittest
from pathlib import Path

from src.utils.datos_csv import ADICIONALES_DIR, ENTIDADES, ORIGINALES_DIR, leer_datos


def escribir(directorio, nombre, filas):
    campos = ENTIDADES[nombre][2].split()
    with (directorio / f"{nombre}.csv").open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(filas)


CLIENTE = dict(id_cliente="T05-C01", nombre="Prueba", apellido="Carga", dni="99000001",
               email="prueba@example.com", telefono="1100000000", ciudad="CABA",
               provincia="Buenos Aires", obra_social="Sin cobertura", nro_afiliado="", activo="True")
VENTA = dict(id_venta="T05-V01", id_cliente="T05-C01", id_farmaceutico="F001", id_receta="",
             fecha="2026-11-01", tipo="Venta libre", medio_pago="Efectivo", total="3000",
             estado="Completada")
DETALLE = dict(id_detalle="T05-D01", id_venta="T05-V01", id_producto="PRD001", cantidad="2",
               precio_unit="1500")


class LecturaCsvTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.adicionales = Path(self._tmp.name) / "adicionales"
        self.adicionales.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def leer(self):
        return leer_datos([ORIGINALES_DIR, self.adicionales])

    def test_originales_solos(self):
        datos = leer_datos([ORIGINALES_DIR])
        self.assertEqual(sum(map(len, datos.values())), 103)

    def test_directorio_por_defecto_incluye_adicionales_si_existen(self):
        self.assertEqual(leer_datos.__defaults__[0], (ORIGINALES_DIR, ADICIONALES_DIR))

    def test_adicionales_vacios_o_ausentes(self):
        self.assertEqual(self.leer(), leer_datos([ORIGINALES_DIR]))
        self.assertEqual(leer_datos([ORIGINALES_DIR, self.adicionales / "no-existe"]),
                         leer_datos([ORIGINALES_DIR]))

    def test_suma_adicionales_que_referencian_originales(self):
        escribir(self.adicionales, "clientes", [CLIENTE])
        escribir(self.adicionales, "ventas", [VENTA])
        escribir(self.adicionales, "detalle_ventas", [DETALLE])
        datos = self.leer()
        self.assertEqual(sum(map(len, datos.values())), 106)
        cliente = datos["clientes"][-1]
        self.assertEqual(cliente["id_cliente"], "T05-C01")
        self.assertIsNone(cliente["nro_afiliado"])
        self.assertIs(cliente["activo"], True)
        self.assertEqual(datos["ventas"][-1]["total"], 3000)

    def test_rechaza_id_repetido_con_los_originales(self):
        escribir(self.adicionales, "clientes", [dict(CLIENTE, id_cliente="C001")])
        with self.assertRaisesRegex(ValueError, r"adicionales/clientes.csv:2: identificador "
                                                r"repetido C001 \(ya definido en original/"):
            self.leer()

    def test_rechaza_dni_repetido_con_los_originales(self):
        dni = leer_datos([ORIGINALES_DIR])["clientes"][0]["dni"]
        escribir(self.adicionales, "clientes", [dict(CLIENTE, dni=dni)])
        with self.assertRaisesRegex(ValueError, "clientes: dni repetido"):
            self.leer()

    def test_rechaza_referencia_inexistente(self):
        escribir(self.adicionales, "ventas", [dict(VENTA, id_cliente="C999")])
        escribir(self.adicionales, "detalle_ventas", [DETALLE])
        with self.assertRaisesRegex(ValueError, r"ventas\[T05-V01\]\.id_cliente: referencia"):
            self.leer()

    def test_rechaza_venta_atribuida_a_una_drogueria(self):
        escribir(self.adicionales, "clientes", [CLIENTE])
        escribir(self.adicionales, "ventas", [dict(VENTA, id_farmaceutico="F007")])
        escribir(self.adicionales, "detalle_ventas", [DETALLE])
        with self.assertRaisesRegex(ValueError, r"ventas\[T05-V01\]\.id_sucursal: S005 no es una Farmacia"):
            self.leer()

    def test_rechaza_item_bajo_receta_sin_receta_asociada(self):
        escribir(self.adicionales, "clientes", [CLIENTE])
        escribir(self.adicionales, "ventas", [VENTA])
        escribir(self.adicionales, "detalle_ventas", [dict(DETALLE, id_producto="PRD003")])
        with self.assertRaisesRegex(ValueError, r"ventas\[T05-V01\]\.id_receta: falta receta para PRD003"):
            self.leer()

    def test_rechaza_total_inconsistente_o_venta_sin_detalle(self):
        escribir(self.adicionales, "clientes", [CLIENTE])
        escribir(self.adicionales, "ventas", [dict(VENTA, total="2999")])
        escribir(self.adicionales, "detalle_ventas", [DETALLE])
        with self.assertRaisesRegex(ValueError, "T05-V01: total inconsistente"):
            self.leer()
        (self.adicionales / "detalle_ventas.csv").unlink()
        with self.assertRaisesRegex(ValueError, "T05-V01: total inconsistente"):
            self.leer()

    def test_rechaza_dominios_contadores_y_receta_ajena(self):
        datos = leer_datos([ORIGINALES_DIR])
        casos = (
            ("productos", "id_producto", {"condicion_venta": "Bajo recetaa"}, "condicion_venta"),
            ("recetas", "id_receta", {"dispensas_autorizadas": 4}, "dispensas_autorizadas"),
            ("stock_lotes", "id_lote", {"unidades": -1}, r"unidades: mínimo 0"),
        )
        for nombre, clave, cambios, mensaje in casos:
            with self.subTest(nombre=nombre):
                fila = {campo: "" if valor is None else str(valor)
                        for campo, valor in datos[nombre][0].items()}
                escribir(self.adicionales, nombre, [dict(fila, **{clave: "H04"}, **cambios)])
                with self.assertRaisesRegex(ValueError, mensaje):
                    self.leer()
                (self.adicionales / f"{nombre}.csv").unlink()

        escribir(self.adicionales, "ventas",
                 [dict(VENTA, id_cliente="C001", tipo="Con receta", id_receta="RC005")])
        escribir(self.adicionales, "detalle_ventas", [DETALLE])
        with self.assertRaisesRegex(ValueError, "RC005 pertenece a otro cliente"):
            self.leer()

    def test_rechaza_encabezado_distinto(self):
        (self.adicionales / "clientes.csv").write_text("id_cliente,nombre\nX,Y\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "adicionales/clientes.csv: encabezado inesperado"):
            self.leer()

    def test_rechaza_tipos_invalidos_con_su_origen(self):
        escribir(self.adicionales, "clientes", [dict(CLIENTE, activo="si")])
        with self.assertRaisesRegex(ValueError, "adicionales/clientes.csv:2: booleano"):
            self.leer()


if __name__ == "__main__":
    unittest.main()
