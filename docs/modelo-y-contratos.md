# FarmaRed: modelo y contratos propuestos

Esta base se armó con los nueve CSV y el plan de trabajo. Las decisiones de
negocio pendientes de validar con el equipo y la consigna están al final.

## MongoDB: fuente de verdad

MongoDB conserva catálogo, clientes, recetas, ventas y stock. Las altas y bajas,
las dispensas y los descuentos se confirman allí. Una transacción del replica
set permite confirmar o revertir conjuntamente las escrituras de una venta.

| Colección | ID único | Referencias |
| --- | --- | --- |
| `clientes` | `id_cliente` | DNI también único; baja lógica con `activo: false`. |
| `sucursales` | `id_sucursal` | Distingue Farmacia de Droguería. |
| `farmaceuticos` | `id_farmaceutico` | Sucursal; matrícula también única. |
| `proveedores` | `id_proveedor` | Datos de origen. |
| `productos` | `id_producto` | Proveedor. |
| `stock_lotes` | `id_lote` | Producto y sucursal. El número de lote puede repetirse en distintas sucursales. |
| `recetas` | `id_receta` | Cliente; estado, dispensas y próxima dispensa. |
| `ventas` | `id_venta` | Cliente, farmacéutico y receta opcional. |
| `detalle_ventas` | `id_detalle` | Venta y producto; cantidad y precio unitario de la operación. |

Se mantienen las colecciones e IDs que ya creó el loader. El detalle queda
separado para preservar sus identificadores, consultar unidades por producto
y mantener la carga existente. El servicio de venta deberá escribir cabecera y
detalles en la misma transacción. El total se calcula como la suma de
`cantidad × precio_unit` de cada detalle; los importes se guardan como enteros
en pesos. Los IDs, DNI, matrículas y teléfonos se guardan como texto. Los
opcionales vacíos del CSV se guardan como `null` en MongoDB.

Los índices únicos cubren los IDs y las dos claves adicionales. El loader
también crea índices para productos activos, ventas por estado y fecha, detalle
por venta, lotes por unidades y búsqueda FEFO por sucursal, producto, vencimiento
e ID. Para aplicar estos índices a una base ya cargada basta repetir el loader:
inserta faltantes y conserva los documentos existentes.

## Neo4j: proyección de lectura

El grafo permite recorrer el historial de un cliente y su atención en sucursales
sin volver a expresar todas las relaciones en cada consulta. Se conservan las
etiquetas e IDs actuales (`Cliente`, `Sucursal`, `Farmaceutico`, `Proveedor`,
`Producto`, `Lote`, `Receta`, `Venta` y `DetalleVenta`), sus restricciones de
unicidad y las relaciones ya definidas en `src/utils/datos_csv.py`. Los caminos
principales de q03, q04, q06, q10 y q12 son:

- `Venta → REALIZADA_POR → Cliente`
- `Receta → PRESCRIPTA_A → Cliente`
- `Venta → ATENDIDA_POR → Farmaceutico → TRABAJA_EN → Sucursal`
- `Venta → CON_RECETA → Receta` (solo si hay receta).

T06 debe leer un snapshot de MongoDB y aplicar la proyección en una transacción
de Neo4j, actualizando propiedades y sustituyendo relaciones que hayan cambiado.
Las actualizaciones se serializan para evitar que un snapshot anterior pise
uno más nuevo. Las consultas del grafo deben informar si el refresco requerido
falla; no hay una transacción compartida entre motores. El loader actual sigue
siendo una carga inicial desde CSV y todavía no hace esta sincronización.

Para q10, los CSV solo permiten inferir la sucursal de ventas históricas con la
asignación disponible del farmacéutico. Se propone guardar `id_sucursal` en
ventas nuevas como dato de la operación, para no reinterpretar su historial
si el farmacéutico se muda de sucursal.

## Fechas y contratos de venta para T12–T14

- El día de negocio se calcula en `America/Argentina/Buenos_Aires`. Una fecha
  sin hora se codifica como medianoche UTC en MongoDB y como `Date` en Neo4j.
  Los límites mensuales incluyen el primer día y excluyen el primer día del
  mes siguiente. Se propone considerar utilizable un lote hasta su fecha de
  vencimiento inclusive.
- q14 recibe un ID estable de venta, cliente, farmacéutico, medio de pago, una
  lista de productos y cantidades, y una receta opcional. Valida actividad,
  sucursal tipo Farmacia, cantidades y receta según los productos. Guarda el
  precio vigente al registrar la venta y devuelve el ID y el total confirmados.
  El día se determina una vez por operación, también ante reintentos del driver.
- q15 recibe el ID de venta y la misma sesión activa de q14. Lee la venta y sus
  detalles, agrupa cantidades por producto y consume lotes de su sucursal por
  vencimiento ascendente y luego por `id_lote`. Un rechazo de stock se propaga
  al coordinador. q15 devuelve el reparto del descuento por lote y no confirma
  la transacción.
- Propuesta de reintento: la misma clave con los mismos argumentos devuelve
  el resultado de la operación anterior; reutilizarla con otros argumentos
  da conflicto. La protección se persiste junto con la venta y el descuento.
  q15 no se expone como un descuento independiente; si se ofrece por terminal
  para una venta existente, debe usar la misma protección transaccional para
  evitar un segundo descuento.
- La dispensa se cuenta una vez por venta con receta. En tratamientos
  prolongados, la próxima se fija a 30 días mientras queden dispensas; al
  completar la receta se limpia la fecha. RC002 se conserva tal como vino.

Pendiente de validar: vencimiento durante el mismo día, criterios de vigencia
de una receta cuando no trae fecha de vencimiento, si la próxima dispensa impide
dispensar antes de ese día, cuándo una venta puede usar una sola receta para
varios productos y cómo espera la cátedra que se ejecute q15. La carga aditiva
de datos propios y las escrituras de negocio quedan en sus respectivas tareas.
