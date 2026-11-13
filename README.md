# FarmaRed — Base de Datos II

## Preparar el entorno

Ejecutá los comandos desde la raíz del repositorio, donde está `docker-compose.yml`.

**Mac.** Abrí Docker Desktop e instalá Python 3.12 desde python.org si
todavía no lo tenés. [Instalador de Python para Mac](https://www.python.org/downloads/macos/)

```sh
python3.12 -m pip install --user -r requirements.txt
sh .devcontainer/initialize.sh
```

Si `command -v python3.12` muestra el Python de Homebrew, usá la ruta del
ejecutable de python.org en los comandos de esta guía:
`/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12`.

**Windows.** Abrí Docker Desktop con contenedores Linux. Con Python 3.12
instalado, ejecutá en PowerShell:

```powershell
py -3.12 -m pip install --user -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Si se creó `.env`, completá `MONGODB_PASSWORD` y `NEO4J_PASSWORD` con
contraseñas locales alfanuméricas de al menos ocho caracteres.

**GitHub Codespaces.** Abrí **Code → Codespaces → Create codespace**. Una vez
listo, usá la terminal integrada. El entorno prepara las dependencias y
genera `.env`.

## Iniciar y cargar los datos

Los ejemplos usan `python3.12` en Mac. En Windows, reemplazalo por
`py -3.12`. En Codespaces, usá `python`.

```sh
docker compose up -d --wait
python3.12 scripts/check_connections.py
python3.12 scripts/loaders/load_mongo.py
python3.12 scripts/loaders/load_neo4j.py
```

El chequeo debe confirmar la autenticación en ambos motores y que MongoDB tiene
un PRIMARY. `load_mongo.py` carga los 103 registros de los CSV originales y,
si existen, los de `data/adicionales/`. Después, `load_neo4j.py` proyecta los
documentos que están en MongoDB, incluidos los cambios de negocio.

El cargador de MongoDB es aditivo: inserta lo que falta y nunca pisa
documentos existentes, así que repetirlo no revierte ventas, dispensas ni
descuentos de stock. Al terminar compara la base con los CSV. Para verificar
sin escribir o para volver al estado de los CSV (borra las nueve colecciones):

```sh
python3.12 scripts/loaders/load_mongo.py --verificar
python3.12 scripts/loaders/load_mongo.py --reiniciar farmared_importacion
```

`--reiniciar` exige el nombre de la base configurada en `MONGODB_DATABASE`.

Para refrescar Neo4j después de una escritura en MongoDB, ejecutá
`python3.12 scripts/loaders/load_neo4j.py`. Con `--dry-run`, el comando lee y
valida el snapshot de MongoDB sin conectarse a Neo4j. Ante un fallo devuelve
código `1` y escribe el motivo en stderr. Por ejemplo, si Neo4j está caído:

```text
ERROR: No se pudo publicar la proyección o completar la lectura en Neo4j.
```

## Ejecutar las pruebas

```sh
python3.12 -m unittest discover -s tests
python3.12 tests/carga/verify_mongo.py
python3.12 tests/queries/verify.py
python3.12 tests/queries/verify_t10.py
python3.12 tests/servicios/verify_q13.py
python3.12 tests/servicios/verify_q14.py
python3.12 tests/servicios/verify_q15.py
```

Los scripts usan una base temporal de MongoDB y la eliminan al terminar.
Con `--evidencia`, `tests/queries/verify.py` imprime ejemplos verificados de
[q01, q07, q08 y q11](docs/evidencias/t08.md). Los scripts de q13, q14 y q15
imprimen el antes y el después de las operaciones (ver
[docs/evidencias/](docs/evidencias/)).

## Ejecutar una consulta

```sh
python3.12 scripts/run_query.py 1
python3.12 scripts/run_query.py 2
python3.12 scripts/run_query.py q03 --id-cliente C001
python3.12 scripts/run_query.py q04
python3.12 scripts/run_query.py 5
python3.12 scripts/run_query.py q06
python3.12 scripts/run_query.py 7
python3.12 scripts/run_query.py 8
python3.12 scripts/run_query.py 9
python3.12 scripts/run_query.py q10 --id-sucursal S002
python3.12 scripts/run_query.py 11
python3.12 scripts/run_query.py q12
```

q03, q04, q06, q10 y q12 refrescan la proyección desde MongoDB antes de consultar Neo4j.
Los ejemplos verificados cubren el [historial de un cliente](docs/evidencias/q03.md),
los [clientes con más de una receta](docs/evidencias/q04.md), las
[dispensas atrasadas](docs/evidencias/q06.md), los
[clientes atendidos por sucursal](docs/evidencias/q10.md) y los
[clientes sin ventas en el último año](docs/evidencias/q12.md).
Los ejemplos de q02, q05 y q09 están en las
[evidencias de T10](docs/evidencias/t10.md).
q06 y q12 usan la fecha actual de Buenos Aires.

## Detener las bases

```sh
docker compose stop mongo neo4j
```

Para reanudar conservando los datos, ejecutá `docker compose up -d --wait`.

## Opciones para Mac

Si ya usás Conda, podés instalar las dependencias en `base`.

```sh
conda activate base
python -m pip install -r requirements.txt
sh .devcontainer/initialize.sh
```

Si preferís un entorno virtual, creá `.venv` y activalo.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
sh .devcontainer/initialize.sh
```

En ambos casos usá `python` en los comandos de carga y consulta. Si elegiste
`.venv`, activalo en cada terminal nueva con `source .venv/bin/activate`.
