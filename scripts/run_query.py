import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from pymongo.errors import PyMongoError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.check_connections import conectar_mongo
from src.services.query_01_productos_activos import q01
from src.services.query_07_productos_mas_vendidos import q07
from src.services.query_08_stock_bajo import q08
from src.services.query_11_ingresos_por_farmaceutico import q11

CONSULTAS = {consulta.__name__: consulta for consulta in (q01, q07, q08, q11)}


def a_json(valor):
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    raise TypeError(f"No se puede serializar {type(valor).__name__}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("consulta", choices=CONSULTAS,
                        type=lambda valor: "q" + valor.lower().removeprefix("q").zfill(2),
                        help="Código o número de consulta, por ejemplo q08 u 8.")
    args = parser.parse_args()
    try:
        cliente, db = conectar_mongo()
        with cliente:
            resultado = CONSULTAS[args.consulta](db)
    except (ValueError, PyMongoError) as exc:
        print(f"No se pudo ejecutar {args.consulta} ({type(exc).__name__}). "
              "Revisá la configuración y el estado de MongoDB.", file=sys.stderr)
        return 1
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=a_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
