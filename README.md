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
un PRIMARY. Cada loader procesa los 103 registros de los CSV originales y,
si existen, los de `data/adicionales/`.
Al volver a ejecutar el cargador de Neo4j se reaplican las propiedades y
relaciones de los registros incluidos en los CSV.

El cargador de MongoDB es aditivo: inserta lo que falta y nunca pisa
documentos existentes, así que repetirlo no revierte ventas, dispensas ni
descuentos de stock. Al terminar compara la base con los CSV. Para verificar
sin escribir o para volver al estado de los CSV (borra las nueve colecciones):

```sh
python3.12 scripts/loaders/load_mongo.py --verificar
python3.12 scripts/loaders/load_mongo.py --reiniciar farmared_importacion
```

`--reiniciar` exige el nombre de la base configurada en `MONGODB_DATABASE`.

## Ejecutar las pruebas

```sh
python3.12 -m unittest discover -s tests
python3.12 tests/carga/verify_mongo.py
python3.12 tests/queries/verify.py
```

Los dos scripts usan una base temporal de MongoDB y la eliminan al terminar.

## Ejecutar una consulta

```sh
python3.12 scripts/run_query.py 8
```

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
