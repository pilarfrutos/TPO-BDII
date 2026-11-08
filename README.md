# TPO-BDII — FarmaRed

Base inicial del Trabajo Práctico de Base de Datos II: CSV de la cátedra y loaders
para MongoDB y Neo4j, con configuración local de Docker. No incluye todavía
consultas, servicios ni registros propios.

## Estructura

```text
data/original/          Los nueve CSV de la cátedra, sin modificaciones.
scripts/loader_mongo.py Loader de MongoDB.
scripts/loader_neo4j.py Loader de Neo4j.
scripts/datos_csv.py    Lectura, conversión de tipos y validaciones compartidas.
requirements.txt       Drivers y lectura de variables .env.
docker-compose.yml     MongoDB y Neo4j con volúmenes persistentes.
.env.example           Plantilla versionable, sin contraseñas.
.env                   Configuración local privada; excluida de Git.
```

## Preparación

Abrir esta carpeta en VS Code. Usar Python 3.12 o posterior:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Los loaders leen automáticamente `.env`; las variables ya exportadas en la
terminal tienen prioridad. `python-dotenv` permite esa lectura sin cargar el archivo
como un script de shell.

Las dependencias tienen rangos de versión compatibles; todavía no hay un archivo
con versiones exactas verificadas. No se instalaron automáticamente en la Mac.

## Iniciar las bases de datos con Docker

Abrir Docker Desktop y esperar a que esté listo. Ya se preparó un `.env` local
con contraseñas aleatorias que no se versionan. Para otro integrante o una copia
nueva del repositorio:

```sh
cp .env.example .env
```

Completar `MONGODB_PASSWORD` y `NEO4J_PASSWORD` en ese archivo antes de iniciar.
Neo4j usa el usuario `neo4j`; su contraseña debe tener al menos ocho caracteres.
Luego ejecutar desde la raíz del proyecto:

```sh
docker compose config --quiet
docker compose up -d --wait
docker compose ps
```

Se usan MongoDB 8.0.16 y Neo4j 5.26.0 Community. Los puertos se publican solo en
localhost. Descarga y arranque verificados en la Mac: ambos servicios alcanzaron estado
`healthy`, incluyendo sus comprobaciones de conexión autenticada.
MongoDB está configurado como instancia standalone para la carga inicial; antes
de implementar las transacciones de q14/q15 habrá que configurar un replica set.

Conexiones:

- **DataGrip / MongoDB:** host `localhost`, puerto `27017`, usuario y contraseña
  de `.env`, base de autenticación `admin`. Usar la URI `MONGODB_URI` sin agregar
  la contraseña a archivos versionados y comprobar **Test Connection**.
- **Neo4j Browser:** abrir http://localhost:7474, conectar a
  `bolt://localhost:7687`, usuario `neo4j` y contraseña `NEO4J_PASSWORD` de `.env`.

Detener conservando los datos y volver a iniciar:

```sh
docker compose down
docker compose up -d --wait
```

Los volúmenes conservan los datos. `docker compose down -v` los eliminaría.
Cambiar contraseñas en `.env` no cambia automáticamente usuarios de bases que ya
fueron inicializadas en esos volúmenes. No versionar `.env` ni compartirlo.

## Validar sin bases de datos

Estos comandos no necesitan instalar los drivers y no escriben datos:

```sh
python3 scripts/loader_mongo.py --dry-run
python3 scripts/loader_neo4j.py --dry-run
```

Se esperan 103 registros entre los nueve CSV. La fecha de próxima dispensa de RC002
no coincide con sumar 30 días a su última venta completada (15/09 frente a 14/09).
Los loaders conservan el valor original y lo informan; no corrigen los archivos.

## Cargar MongoDB

Requiere que el servicio MongoDB de Docker esté saludable.
Por defecto conecta a localhost:27017 y usa la base `farmared_importacion`.
Para una conexión diferente, definir `MONGODB_URI` y `MONGODB_DATABASE` en el entorno.

```sh
python3 scripts/loader_mongo.py
```

Crea una colección por CSV, con índices únicos para los identificadores, DNI y
matrícula. Inserta los registros faltantes sin reemplazar los existentes.
Las fechas se representan como medianoche UTC en BSON; mostrarlas como fechas UTC
para no cambiar su día por conversión de zona horaria. Vacíos: null; booleanos y
cantidades se convierten a sus tipos respectivos. Los identificadores siguen como texto.

## Cargar Neo4j

Requiere que el servicio Neo4j de Docker esté saludable. Lee URI, usuario,
contraseña y base desde `.env`.

```sh
python3 scripts/loader_neo4j.py
```

Crea etiquetas Cliente, Sucursal, Farmaceutico, Proveedor, Producto, Lote, Receta,
Venta y DetalleVenta, con unicidad por identificador y también por DNI/matrícula.
Las diez referencias del dataset se representan como relaciones dirigidas.
Las fechas son propiedades nativas Date. En Neo4j un campo vacío no se almacena
como propiedad, equivalente a su ausencia. Nodos y relaciones se cargan en una
transacción; las restricciones se crean previamente.

## Alcance de esta primera carga

Se importan inicialmente los nueve CSV a ambos motores para explorar sus modelos.
Es una decisión de arranque propia, no un requisito de la cátedra ni una copia del
código del otro grupo. La distribución definitiva de responsabilidades entre
motores se diseñará después; esta carga no la reemplaza.

Repetir un loader no duplica ni sobrescribe entidades existentes. Tampoco resta
stock por las ventas históricas. No hay sincronización automática entre motores.
MongoDB carga por colección: si falla a mitad de proceso, puede quedar una carga
parcial; al resolver el error se puede reejecutar para insertar lo faltante.

Los CSV originales están intactos. Los loaders se validaron sin conexión; todavía
falta comprobar su ejecución e idempotencia con ambos motores reales. La
configuración de Codespaces, los diez registros adicionales por colección/tabla,
q01–q15 y el informe PDF siguen pendientes para cumplir la consigna completa.
