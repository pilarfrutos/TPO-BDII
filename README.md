# FarmaRed — Base de Datos II

## Preparar el entorno

Ejecutá los comandos desde la raíz del repositorio, donde está `docker-compose.yml`.

**Mac.** Abrí Docker Desktop y ejecutá estos comandos con Python 3.12:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
sh .devcontainer/initialize.sh
```

El último comando genera `.env` con las credenciales locales. En cada terminal
nueva, activá el entorno con `source .venv/bin/activate`.

**Windows.** Abrí Docker Desktop con contenedores Linux. Con Python 3.12
instalado, ejecutá en PowerShell:

```powershell
py -3.12 -m venv .venv
Set-Alias python "$PWD\.venv\Scripts\python.exe"
python -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Si se creó `.env`, completá `MONGODB_PASSWORD` y `NEO4J_PASSWORD` con
contraseñas locales alfanuméricas de al menos ocho caracteres. En cada
PowerShell nuevo, repetí el comando `Set-Alias` desde la raíz del repo.

**GitHub Codespaces.** Abrí **Code → Codespaces → Create codespace**. Una vez
listo, usá la terminal integrada. El entorno prepara las dependencias y
genera `.env`.

## Iniciar y cargar los datos

```sh
docker compose up -d --wait
python scripts/check_connections.py
python scripts/loaders/load_mongo.py
python scripts/loaders/load_neo4j.py
```

El chequeo debe confirmar la autenticación en ambos motores y que MongoDB tiene
un PRIMARY. Cada loader procesa los 103 registros de los CSV originales.

## Ejecutar una consulta

```sh
python scripts/run_query.py 8
```

Podés usar los números 1, 7, 8 y 11.

## Detener las bases

```sh
docker compose stop mongo neo4j
```

Para reanudar conservando los datos, ejecutá `docker compose up -d --wait`.
