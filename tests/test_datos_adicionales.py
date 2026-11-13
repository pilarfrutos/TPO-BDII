import unittest
from datetime import date

from src.utils.datos_csv import ADICIONALES_DIR, ENTIDADES, leer_datos


class DatosAdicionalesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datos = leer_datos([ADICIONALES_DIR])

    def test_hay_diez_filas_por_cada_dataset(self):
        self.assertEqual(set(self.datos), set(ENTIDADES))
        self.assertEqual({nombre: len(filas) for nombre, filas in self.datos.items()},
                         {nombre: 10 for nombre in ENTIDADES})

    def test_el_conjunto_unido_es_valido_y_tiene_193_registros(self):
        unidos = leer_datos()
        self.assertEqual(sum(map(len, unidos.values())), 193)

    def test_cubre_estados_y_limites_de_ventas(self):
        ventas = {v["id_venta"]: v for v in self.datos["ventas"]}
        self.assertEqual({v["estado"] for v in ventas.values()},
                         {"Completada", "Pendiente", "Anulada"})
        self.assertEqual((ventas["DV008"]["tipo"], ventas["DV008"]["total"],
                          ventas["DV008"]["estado"]),
                         ("Venta libre", 4999, "Pendiente"))
        self.assertEqual(ventas["DV009"]["total"], 5000)
        self.assertEqual(ventas["DV010"]["estado"], "Anulada")

    def test_cubre_profesionales_sin_ventas_e_historial_inactivo(self):
        ventas = self.datos["ventas"]
        con_ventas = {v["id_farmaceutico"] for v in ventas}
        farmaceuticos = {f["id_farmaceutico"]: f for f in self.datos["farmaceuticos"]}
        self.assertTrue(farmaceuticos["DF008"]["activo"])
        self.assertTrue(farmaceuticos["DF010"]["activo"])
        self.assertNotIn("DF008", con_ventas)
        self.assertNotIn("DF010", con_ventas)
        self.assertFalse(farmaceuticos["DF009"]["activo"])
        self.assertTrue(any(v["id_farmaceutico"] == "DF009" for v in ventas))

    def test_cubre_recetas_multiples_y_tratamientos_atrasados(self):
        recetas = self.datos["recetas"]
        self.assertEqual(sum(r["id_cliente"] == "DC001" for r in recetas), 3)
        por_id = {r["id_receta"]: r for r in recetas}
        self.assertLess(por_id["DRC001"]["proxima_dispensa"], date(2026, 11, 13))
        self.assertEqual(por_id["DRC004"]["proxima_dispensa"], date(2026, 11, 13))
        self.assertEqual(por_id["DRC005"]["estado"], "Vencida")

    def test_cubre_stock_bajo_vencido_fefo_e_insuficiente(self):
        lotes = {l["id_lote"]: l for l in self.datos["stock_lotes"]}
        self.assertEqual(lotes["DL004"]["unidades"], 49)
        self.assertEqual(lotes["DL005"]["unidades"], 50)
        self.assertLess(lotes["DL003"]["vencimiento"], date(2026, 11, 13))
        self.assertEqual(lotes["DL006"]["unidades"], 0)
        fefo = [l for l in lotes.values()
                if l["id_producto"] == "DPRD001" and l["id_sucursal"] == "DS001"]
        self.assertEqual(len(fefo), 3)
        self.assertGreaterEqual(sum(l["unidades"] for l in fefo
                                    if l["vencimiento"] >= date(2026, 11, 13)), 4)


if __name__ == "__main__":
    unittest.main()
