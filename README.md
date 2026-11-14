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
un PRIMARY. `load_mongo.py` carga los 103 registros de los CSV originales y
los 90 de `data/adicionales/`: 193 en total. Después, `load_neo4j.py` proyecta
los documentos que están en MongoDB, incluidos los cambios de negocio.

El cargador de MongoDB inserta lo que falta y completa `id_sucursal` en
ventas importadas que aún carecen del campo. Para inferirlo usa la asignación
del farmacéutico en los CSV. Repetir la carga conserva las sucursales ya
guardadas y los cambios de negocio. Al terminar compara la base con los CSV. Para verificar
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
Agregá `--evidencia` a [`verify.py`](tests/queries/verify.py) para ver ejemplos
de q01, q07, q08 y q11, y a [`verify_t10.py`](tests/queries/verify_t10.py) para
q02, q05 y q09. Los verificadores de q13, q14 y q15 aceptan el mismo argumento
para mostrar en JSON el estado antes y después de las operaciones y los rechazos.

[`verify_t15.py`](tests/servicios/verify_t15.py) verifica concurrencia, rollbacks
y recuperación de la proyección. Ese script y `verify_q13.py --neo4j` publican
en `neo4j-test`, una instancia aparte con almacenamiento temporal. Con MongoDB
en marcha, levantá esa instancia y ejecutá las dos pruebas de grafo en serie.

```sh
docker compose up -d --wait neo4j-test
python3.12 tests/servicios/verify_q13.py --neo4j
python3.12 tests/servicios/verify_t15.py
docker compose stop neo4j-test
```

Desde el host, las pruebas usan `bolt://127.0.0.1:17687`. El devcontainer
configura `NEO4J_TEST_URI` para usar el servicio dentro de la red de Compose.

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
python3.12 scripts/run_query.py q13 alta \
  --id-cliente CLI-C01 --nombre Ada --apellido Lovelace --dni 50999999 \
  --email ada@example.com --telefono 1155559999 --ciudad CABA \
  --provincia "Buenos Aires" --obra-social "Sin cobertura"
python3.12 scripts/run_query.py q14 \
  --id-venta CLI-V01 --id-cliente C001 --id-farmaceutico F001 \
  --medio-pago Efectivo --item PRD001:1
python3.12 scripts/run_query.py q15 --id-venta CLI-V01
```

q03, q04, q06, q10 y q12 refrescan la proyección desde MongoDB antes de consultar
Neo4j. Con los CSV cargados, q03 devuelve para `C001` los eventos `RC001`,
`V003`, `V015`, `V013`, `RC008` y `V010`, en ese orden. q10 incluye a `C004`
entre los clientes atendidos en `S002`, por una venta de un farmacéutico hoy
inactivo. q05, q06, q11 y q12 usan la fecha actual de Buenos Aires.

Cada consulta acepta su número (`3`) o código (`q03`) y muestra el resultado
como JSON. Usá `python3.12 scripts/run_query.py q13 --help` para ver las
operaciones `alta`, `modificar`, `baja` y `reactivar`; cada operación también
tiene ayuda propia. En q14, repetí `--item PRODUCTO:CANTIDAD` para agregar
productos y usá `--id-receta` cuando corresponda. q14 registra la venta y llama
a q15 en la misma transacción. Si falta stock, se revierten la venta, el
detalle, la dispensa y los cambios de lotes.

En modo autónomo, q15 aplica FEFO sobre una venta ya completada con ítems,
fecha, una sucursal histórica de tipo `Farmacia` y `registro.stock_pendiente: true`.
El modo autónomo solo modifica lotes y guarda el reparto en la venta. Ante
un rechazo, la venta existente conserva la marca y los saldos quedan intactos.
El comando con `CLI-V01` devuelve el reparto ya aplicado por q14. Las ventas
importadas tienen stock consolidado y quedan fuera del descuento. Para ver un
descuento autónomo real y el rollback integrado, ejecutá
`python3.12 tests/servicios/verify_q15.py --evidencia`. La prueba prepara sus
propias ventas en una base temporal.

q13, q14 y q15 pueden modificar MongoDB, por lo que conviene usar
identificadores propios como los de los ejemplos. Los cambios de q13 aparecen
en Neo4j en el siguiente refresco de la proyección.

Los errores de uso, como un argumento obligatorio ausente o un ítem con
formato inválido, muestran la ayuda de uso en stderr y devuelven código `2`.
Los rechazos de ejecución gestionados, incluidos los datos fuera del rango
BSON y las fallas de conexión, se escriben en stderr con formato
`ERROR qNN [codigo]: mensaje` y devuelven código `1`. La salida JSON de una
ejecución exitosa se escribe en stdout y devuelve código `0`.

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
