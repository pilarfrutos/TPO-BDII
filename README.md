# FarmaRed — Base de Datos II

Entorno de desarrollo con MongoDB, Neo4j y loaders para los nueve CSV de
`data/original/`. Permite validar e importar los datos desde GitHub Codespaces o
una Mac con Docker Desktop.

## 1. Preparar el entorno

Elegir una de las siguientes opciones. Todos los comandos posteriores se ejecutan
en la raíz del repositorio.

### Opción A: GitHub Codespaces

1. En el repositorio de GitHub, seleccionar `main` y abrir
   **Code → Codespaces → Create codespace**. Esa versión remota debe incluir la
   carpeta `.devcontainer/`.
2. Elegir una máquina con al menos 2 CPU y 4 GB de RAM y esperar la construcción.
   Python y las dependencias se instalan automáticamente. Se inicia el contenedor
   de desarrollo; los motores se levantan en el paso 3.
3. Abrir `.env` en el editor y revisar la configuración. Se genera automáticamente
   con credenciales aleatorias si no existe; un archivo existente se conserva.
4. Abrir la terminal integrada en la raíz del proyecto, donde están `README.md`
   y `docker-compose.yml`. La ruta puede ser `/workspaces/TPO-BDII` o
   `/workspaces/FarmaRed`, según cómo se haya abierto el entorno.

No hace falta instalar Python ni Docker en la máquina personal. Para actualizar
un Codespace existente después de cambios en la configuración, ejecutar
**Codespaces: Rebuild Container**.

### Opción B: Mac con Docker Desktop

Requisitos: Docker Desktop en funcionamiento, Docker Compose 2.24.4 o posterior
y Python 3.12. Abrir la carpeta del repositorio y ejecutar:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
sh .devcontainer/initialize.sh
```

En cada terminal nueva, activar el entorno antes de ejecutar Python:

```sh
source .venv/bin/activate
```

Para usar el mismo contenedor de Codespaces en la Mac, abrir el proyecto en VS Code
con la extensión Dev Containers y ejecutar **Dev Containers: Reopen in Container**.
En ese caso, Python y las dependencias ya están instalados y no se utiliza el venv.

## 2. Configurar variables y credenciales

El script de preparación crea `.env` con credenciales aleatorias sin mostrarlas ni
sobrescribir un archivo existente. Para preparar el archivo manualmente, copiar
`.env.example` a `.env` solamente si todavía no existe y completar las contraseñas
en el editor.

| Variable | Uso / valor predeterminado |
| --- | --- |
| `MONGODB_URI` | `mongodb://localhost:27017/?authSource=admin&directConnection=true&replicaSet=rs0` |
| `MONGODB_DATABASE` | `farmared_importacion` |
| `MONGODB_USER` | `farmared_admin` |
| `MONGODB_PASSWORD` | Contraseña privada de MongoDB |
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_DATABASE` | `neo4j` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | Contraseña privada de Neo4j |

Para contraseñas manuales, usar letras y números; Neo4j requiere al menos ocho
caracteres. No usar `/`, espacios, `$`, `#` ni comillas. No subir `.env` ni compartir
sus contenidos. No cargarlo con `source`: los scripts lo leen automáticamente.

Dentro del devcontainer, la terminal usa `mongo:27017` y `bolt://neo4j:7687` en
lugar de localhost. No modificar las URI del `.env` para cambiar entre Mac y
Codespaces: el devcontainer las sobrescribe automáticamente. Otras variables
exportadas en la terminal tienen prioridad sobre `.env`.

El miembro del replica set anuncia `mongo:27017`, resoluble dentro de la red Docker.
Desde la Mac se usa `localhost:27017` con `directConnection=true`, para que el driver
no intente descubrir ese nombre interno. La URI recomendada también indica
`replicaSet=rs0`; un `.env` existente de T03 con `directConnection=true` funciona
sin reescribirlo. Usar la conexión directa solo para este replica set de desarrollo
de un nodo; no ofrece descubrimiento ni failover hacia otros miembros.

## 3. Iniciar y comprobar las bases

```sh
sh scripts/start.sh
docker compose ps
python scripts/check_connections.py
```

El script construye la imagen MongoDB, inicia ambos motores, configura `rs0` si
todavía no existe y espera a que MongoDB sea PRIMARY. Puede ejecutarse nuevamente:
conserva la configuración y los datos existentes. Usarlo también en el primer
arranque, en lugar de ejecutar directamente `up --wait` antes de inicializar el set.

Ambos servicios deben aparecer como `healthy`. El comprobador debe informar
**autenticación OK** para ambos motores y **replica set rs0; PRIMARY disponible**
para MongoDB. No escribe datos ni muestra contraseñas.

La inicialización utiliza el servicio temporal `mongo-init`. Para repetirla o
recuperarse de un arranque interrumpido, con `mongo` en ejecución:

```sh
docker compose run --rm --no-deps mongo-init
python scripts/check_connections.py
```

### Actualizar un entorno standalone existente

Conservar el `.env` original y los volúmenes. Detener MongoDB para que finalice
sus escrituras y aplicar la nueva configuración:

```sh
docker compose stop mongo
sh scripts/start.sh
python scripts/check_connections.py
```

La conversión reutiliza `mongo-data` con sus usuarios, colecciones e índices. No
reinicializa la base ni vuelve a cargar los CSV. Si hay datos importantes, contar
con un respaldo antes de la conversión. No cambiar las contraseñas de `.env` ni
el nombre de proyecto `farmared`.

El keyfile de autenticación interna se genera dentro de Docker, sin pasar por el
repositorio. Se conserva en `farmared_mongo-keyfile`, propiedad del usuario
`mongodb`, con permisos `0400`. Conservar ese volumen junto con `mongo-data`; no
mostrar ni copiar su contenido a archivos versionados.

Versiones del entorno: MongoDB 8.0.16, Neo4j Community 5.26.0 y, en el contenedor,
Python 3.12.12, Docker CLI 28.0.4 y Compose 2.35.0. Las dependencias Python están
fijadas en `requirements.txt`.

## 4. Validar y cargar los CSV

Primero, validar sin conexión ni escrituras:

```sh
python scripts/loader_mongo.py --dry-run
python scripts/loader_neo4j.py --dry-run
```

Cada comando debe informar **103 registros**. El aviso sobre la fecha de RC002 es
esperado: se conserva el dato original del CSV.

Con ambos motores saludables, cargar los datos:

```sh
python scripts/loader_mongo.py
python scripts/loader_neo4j.py
```

Los loaders insertan los registros faltantes sin reemplazar los existentes.
Repetirlos no duplica entidades ni vuelve a descontar stock por ventas históricas.
La carga MongoDB puede quedar parcial si falla: resolver el error y volver a
ejecutarla. No hay sincronización automática entre los motores.

Los CSV se importan a ambos motores. MongoDB crea una colección por archivo y
Neo4j crea nodos y relaciones. Las fechas se conservan como medianoche UTC en
MongoDB y como Date en Neo4j; mostrar las fechas MongoDB en UTC para conservar su día.

## 5. Detener y volver a iniciar

Detener los motores conservando los datos:

```sh
docker compose stop mongo neo4j
```

Volver a iniciarlos y comprobar conexiones:

```sh
sh scripts/start.sh
python scripts/check_connections.py
```

Los datos persisten en `farmared_mongo-data` y `farmared_neo4j-data`; el keyfile
persiste en `farmared_mongo-keyfile`.
No usar `docker compose down -v`, `docker volume rm` ni `docker volume prune`.
En Codespaces, detener y reanudar conserva el disco; eliminar el Codespace elimina
su almacenamiento. Respaldar los datos necesarios antes de eliminarlo o hacer una
reconstrucción que limpie Docker.

## Prueba completa en bases aisladas

Para comprobar autenticación, carga repetida y persistencia sin escribir en las
bases de trabajo:

```sh
sh scripts/test_t03.sh
```

Se puede ejecutar desde la Mac o la terminal del devcontainer. Para reducir el uso
de memoria, detener antes los motores de desarrollo con el comando del paso 5.
El resultado esperado es:

```text
T03 OK: autenticación, dos cargas iguales y persistencia tras stop/up.
```

La prueba crea un proyecto Docker propio, con red, credenciales y volúmenes
independientes, sin publicar puertos. Ejecuta ambos loaders dos veces, compara
conteos y contenido, detiene los motores, los reinicia y comprueba el contenido
persistido. Al terminar, detiene los motores de prueba y conserva los volúmenes.

Las credenciales y los informes quedan en `.t03/<proyecto>/`, excluido de Git.
Cada ejecución crea volúmenes nuevos. El archivo `tests/t03/compose.yml` complementa
al Compose raíz: usar el script, no ejecutarlo por separado.

## Probar transacciones MongoDB en un entorno aislado

```sh
sh scripts/test_t04.sh
```

Detener antes los motores de desarrollo si se necesita reducir el uso de memoria.
La prueba crea otro proyecto Docker y no usa las bases de trabajo. Primero carga
un MongoDB standalone con datos e índices, lo convierte a `rs0` sobre el mismo
volumen y comprueba que se conserva su contenido. Luego verifica:

- PRIMARY y autenticación, incluido rechazo de una contraseña incorrecta.
- Commit de cambios sobre documentos de dos colecciones en una misma sesión.
- Rollback por un fallo inyectado después de una escritura.
- Rollback por un error de unicidad después de modificar dos documentos.
- Compatibilidad e idempotencia de los loaders existentes.
- Inicialización repetida sin cambiar la identidad del set.
- Conservación de datos, identidad del set y keyfile tras detener y reiniciar.

El resultado esperado es:

```text
T04 OK: migración sin pérdida, PRIMARY, commit, rollback, inicialización repetible y persistencia.
```

Los motores de prueba quedan detenidos; sus volúmenes se conservan. Credenciales e
informes quedan en `.t04/<proyecto>/`, excluido de Git. Cada ejecución usa volúmenes
nuevos. El comprobador de transacciones solo admite la base `farmared_t04_test` del
entorno de prueba, sin limpiar ni sobrescribir bases existentes.

### Garantías y límites

Las transacciones usan una sesión, lectura `snapshot` y escritura `majority`.
El commit confirma conjuntamente las escrituras; una excepción dentro del bloque
transaccional provoca abort y descarta sus cambios. Todas las operaciones de una
transacción deben recibir la misma sesión. Los loaders siguen siendo cargas
aditivas: habilitar el replica set no los convierte en cargas transaccionales.

El replica set tiene un solo nodo: habilita transacciones, pero no aporta
redundancia ni tolerancia a la pérdida de ese nodo. `majority` en este entorno
corresponde a ese único miembro. No hay atomicidad conjunta entre MongoDB y Neo4j.
Los servicios de negocio y sus políticas de reintento se implementan por separado.

## Conectar herramientas gráficas

En la Mac:

- **DataGrip / MongoDB:** `localhost:27017`, usuario y contraseña de `.env`, base
  de autenticación `admin`, base de datos `farmared_importacion`, conexión directa y replica set `rs0`.
- **Neo4j Browser:** abrir [localhost:7474](http://localhost:7474), conectar a
  `bolt://localhost:7687` con usuario `neo4j` y contraseña de `.env`.

En Codespaces, abrir el proyecto en VS Code de escritorio y reenviar desde la
pestaña **Ports** los puertos `mongo:27017`, `neo4j:7474` y `neo4j:7687`.
Mantener la visibilidad **Private** y usar los puertos locales que indique VS Code.
Si alguno está ocupado, el puerto local puede cambiar. La URL HTTPS de Codespaces
no reemplaza una URI MongoDB o Bolt. Las comprobaciones por terminal no requieren
forwarding.

## Problemas frecuentes

Los scripts de arranque y pruebas omiten las sugerencias del CLI y la recopilación
opcional de metadatos Git para las imágenes de desarrollo. Los warnings y errores
de Docker se siguen mostrando.

- **Falta una variable o contraseña:** revisar `.env` en el editor. La preparación
  conserva archivos existentes, incluso si tienen campos vacíos. Si esto impide
  crear el Codespace, corregir `.env` en el modo de recuperación y reconstruir.
- **MongoDB no alcanza `healthy` o no tiene PRIMARY:** ejecutar `sh scripts/start.sh`.
  Un `up --wait` inicial no configura por sí solo el replica set. Si la inicialización
  informa una configuración incompatible, no usar `rs.reconfig` ni `rs.initiate`
  a ciegas; revisar el set y los volúmenes conservados antes de cambiarlo.
- **Autenticación rechazada después de cambiar `.env`:** los usuarios de los
  volúmenes existentes conservan su contraseña anterior. Recuperar las credenciales
  originales o cambiar la contraseña dentro del motor; no borrar volúmenes.
- **Error de conexión desde el devcontainer:** usar la terminal integrada de VS Code.
  Las URI internas se aplican a sus herramientas; un `docker compose exec` manual
  necesita recibir también las URI de servicio.
- **Advertencia de contenedor huérfano `dev`:** conservarlo; es el contenedor del
  editor. La configuración actual lo declara con el perfil opcional `development`.
  Si aparece con una versión anterior, actualizar el repositorio y reconstruir el
  devcontainer. No usar `--remove-orphans` ni cambiar `COMPOSE_PROJECT_NAME`.
- **El editor subraya `!reset`:** `.vscode/settings.json` declara la etiqueta YAML.
  Ejecutar **Developer: Reload Window** para recargar la configuración.
- **Compartir una salida de diagnóstico:** usar `docker compose config --quiet`.
  La salida completa de `config`, `inspect` o `.env` puede revelar credenciales.

Referencias: [conversión a replica set](https://www.mongodb.com/docs/v8.0/tutorial/convert-standalone-to-replica-set/),
[autenticación por keyfile](https://www.mongodb.com/docs/v8.0/tutorial/deploy-replica-set-with-keyfile-access-control/)
y [transacciones con PyMongo](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/transactions/).
