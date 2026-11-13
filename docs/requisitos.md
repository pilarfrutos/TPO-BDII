# FarmaRed: requisitos y decisiones pendientes (T01)

Lista de verificación para comprobar que la entrega cumple la consigna
(`TPO_FarmaRed.pdf`, 2.º cuatrimestre 2026). Cada requisito indica su origen en
la consigna y la tarea de [TAREAS.md](../TAREAS.md) que lo cubre.

- **Consigna**: exigencia del enunciado; su incumplimiento afecta la nota.
- **Equipo**: recomendación o interpretación propia; puede cambiarse si se
  acuerda y se documenta.

Revisado el 12/11/2026.

## 1. Datos de la entrega

| Tema | Estado |
| --- | --- |
| Integrantes | La portada indica grupos de 4; §5.1 menciona "los tres integrantes". El equipo confirmó que son cuatro. Se consulta a la cátedra (D1). |
| Fecha de entrega | "A definir por la cátedra". Completar aquí cuando se comunique. |
| Formato | Link al repositorio GitHub + informe PDF. |
| Plataforma | GitHub Codespaces. |

## 2. Entregables

| # | Requisito | Origen | Tarea |
| --- | --- | --- | --- |
| E1 | README con pasos para levantar el entorno en Codespaces, cargar datos y ejecutar cada consulta | §5.1 | T03, T16, T18 |
| E2 | Configuración del entorno (devcontainer y/o docker-compose) con los motores | §5.1 | T03, T04 |
| E3 | Carpeta con los datasets provistos y los registros adicionales | §5.1 | T05, T07 |
| E4 | Scripts de carga de datos | §5.1 | T05, T06 |
| E5 | Un módulo o función documentada por consulta (q01–q15) | §5.1, §4 | T08–T13, T16 |
| E6 | Historial de commits que evidencie la participación de todos los integrantes | §5.1 | Todos, T18 |
| E7 | Informe: carátula con integrantes y link al repositorio | §5.2 | T17 |
| E8 | Informe: arquitectura políglota y justificación por entidad o caso de uso | §5.2, §3.1 | T02, T17 |
| E9 | Informe: modelo de datos de cada motor con diagramas | §5.2 | T02, T17 |
| E10 | Informe: estrategia de carga y descripción de los registros adicionales | §5.2 | T05, T07, T17 |
| E11 | Informe: las 15 consultas con enunciado, código o sentencia y ejemplo de resultado | §5.2, §4 | Autores de cada q, T17 |
| E12 | Informe: decisiones de consistencia e integridad, en especial q14/q15 | §5.2, §4 | T02, T14, T17 |
| E13 | Informe: limitaciones, alternativas evaluadas y conclusiones | §5.2 | T17 |

## 3. Requisitos técnicos

| # | Requisito | Origen | Tarea |
| --- | --- | --- | --- |
| R1 | Al menos dos motores NoSQL de paradigmas distintos (MongoDB documental + Neo4j grafos) | §3.1 | T02 |
| R2 | Decidir y justificar qué datos persiste cada motor y cómo se relacionan | §3.1 | T02 |
| R3 | Entorno completo en Codespaces sin pasos manuales no documentados | §3.3 | T03, T18 |
| R4 | Carga reproducible e idempotente desde los CSV y los registros adicionales | §3.3 | T05, T06 |
| R5 | Al menos 10 registros adicionales propios por colección/tabla | §2 | T07 |
| R6 | Los adicionales ejercitan las consultas: fechas recientes, stock bajo, lotes próximos a vencer o vencidos, recetas vencidas, clientes sin compras, ventas pendientes, otros casos borde | §3.3 | T07 |
| R7 | Documentar cómo se resuelve la integridad referencial | §3.3 | T02, T05, T17 |
| R8 | "Hoy", "mes actual", "últimos 60 días" y "último año" se calculan con la fecha del sistema, nunca con fechas fijas | §3.3 | T08–T10 |
| R9 | q03, q10, q13, q14 y q15 reciben sus parámetros como argumentos | §4 | T09, T11–T13 |
| R10 | q14 y q15 integradas: si falla el stock, no queda venta ni receta modificada; el informe explica la estrategia | §4 | T12–T14 |
| R11 | Para consultas que cruzan entidades, explicar cómo se resuelve la relación (embebido, referencia, recorrido, aplicación) | §4 | Autores de cada q, T17 |
| R12 | q13–q15: estado antes y después, con al menos un rechazo por validación | §4 | T11–T14, T17 |
| R13 | Convenciones de tipos: vacío = nulo, booleanos True/False, fechas ISO, importes enteros en ARS | §2 | T02, T05 |
| R14 | Los nueve CSV originales permanecen intactos | Equipo | T05, T07 |
| R15 | Repositorio sin secretos; configuración local fuera del control de versiones | Equipo | T03, T18 |

## 4. Reglas de negocio para los servicios de escritura

Todas provienen de §2.11 de la consigna.

| # | Regla | Afecta a |
| --- | --- | --- |
| N1 | Productos 'Bajo receta' y 'Bajo receta archivada' solo se venden con una receta del mismo cliente en estado 'Vigente'. 'Venta libre' no requiere receta. | q14 |
| N2 | Tratamiento prolongado: cada dispensa incrementa `dispensas_realizadas`; si quedan dispensas, `proxima_dispensa` = dispensa + 30 días; al alcanzar `dispensas_autorizadas`, pasa a 'Completada' y `proxima_dispensa` queda vacía. | q14 |
| N3 | Recetas simples y archivadas se completan con su única dispensa. | q14 |
| N4 | 'Completada' descuenta stock y computa ingresos; 'Pendiente' no descuenta ni computa; 'Anulada' no tiene efecto económico. | q07, q11, q14, q15, carga |
| N5 | Solo se registran ventas en sucursales tipo 'Farmacia', mediante un farmacéutico activo. La droguería solo mantiene stock. | q14 |
| N6 | FEFO: primero los lotes con vencimiento más próximo; los vencidos no se dispensan; el stock nunca queda negativo. | q15 |
| N7 | Ninguna entidad se elimina físicamente; la baja es `activo = False`. | q13, todo el sistema |
| N8 | `precio_unit` del detalle es el precio vigente al vender; el total coincide con la suma de los ítems. | q14, carga |
| N9 | DNI de cliente y matrícula de farmacéutico son únicos. | q13, carga |

## 5. Consultas y servicios

Filtros exactos de la consigna. No agregar exclusiones que el enunciado no pide.

| q | Enunciado resumido | Filtros obligatorios | Motor previsto | Tarea |
| --- | --- | --- | --- | --- |
| 01 | Productos activos con todos los datos del proveedor | `activo = True` del producto; el proveedor puede estar inactivo | MongoDB | T08 ✅ |
| 02 | Ventas 'Pendiente' con farmacéutico (nombre, matrícula, sucursal) y total | Solo estado 'Pendiente' | MongoDB | T10 |
| 03 | Historial de un cliente: ventas y recetas por fecha | Parámetro `id_cliente`; orden cronológico; desempate definido | Neo4j | T09 |
| 04 | Clientes con más de una receta y su cantidad | Cantidad > 1; recetas en cualquier estado | Neo4j | T09 |
| 05 | Farmacéuticos activos y ventas de los últimos 60 días | Excluir solo 'Anulada'; incluir conteo 0 | MongoDB | T10 |
| 06 | Tratamientos prolongados 'Vigente' con próxima dispensa anterior a hoy, con cliente | `proxima_dispensa < hoy` | Neo4j | T09 |
| 07 | Top 5 productos por unidades vendidas | Solo 'Completada'; empates definidos | MongoDB | T08 ✅ |
| 08 | Lotes con menos de 50 unidades con producto, sucursal y proveedor | `unidades < 50`; no excluir vencidos | MongoDB | T08 ✅ |
| 09 | Ventas 'Venta libre' con total < 5.000 | Excluir 'Anulada'; `total < 5000` estricto | MongoDB | T10 |
| 10 | Clientes atendidos en una sucursal | Parámetro `id_sucursal`; vía farmacéutico activo o no; sin duplicados | Neo4j | T09 |
| 11 | Ingresos por farmacéutico en el mes actual | Solo 'Completada'; mes calendario actual | MongoDB | T08 ✅ |
| 12 | Clientes sin ventas en el último año | Incluir quienes nunca compraron; no excluir inactivos por suposición | Neo4j | T09 |
| 13 | ABM de clientes | Alta con DNI único; modificación de contacto y cobertura; baja lógica | MongoDB (+ refresco del grafo) | T11 ✅ |
| 14 | Registro de venta 'Completada' validada | Ver N1–N5 y N8; total calculado; receta actualizada | MongoDB (transacción) | T13 y T14 ✅ |
| 15 | Descuento de stock FEFO de una venta | Lotes de la sucursal del farmacéutico; omitir vencidos; todo o nada | MongoDB (transacción) | T12 y T14 ✅ |

Las consultas q01, q07, q08 y q11 ya existen en `src/services/`. Queda completar
sus pruebas de borde (T08, puntos 6 y 8).

## 6. Criterios de evaluación

| Aspecto | Peso | Tareas principales |
| --- | ---: | --- |
| Arquitectura políglota y justificación técnica | 25 % | T02, T17 |
| Modelado de datos y estrategia de carga | 20 % | T02, T05, T06, T07 |
| Consultas de lectura y agregación (1–12) | 25 % | T08, T09, T10 |
| Servicios de escritura (13–15): validaciones y consistencia | 20 % | T11–T15 |
| Calidad del repositorio, documentación e informe | 10 % | T16, T17, T18 |

## 7. Datos originales: anomalías y estados históricos válidos

Referencia temporal de los datasets: 13/10/2026. Las consultas usan la fecha
del sistema, así que los resultados de los originales cambian con el tiempo.

### Anomalías (se conservan sin corregir)

- **RC002**: dispensas el 15/07 (V004) y el 15/08 (V005). Según N2, la
  próxima dispensa sería el 14/09/2026, pero el CSV dice 15/09/2026. Se
  conserva el valor original y se documenta en el informe.

### Estados históricos válidos (no son errores)

- **V001** fue atendida por **F004**, hoy inactivo. Es una venta histórica
  válida y es justamente el caso de q10 ("esté activo o no").
- **Precios distintos al de lista** (V001, V002, V004, entre otros): N8 indica
  que el detalle guarda el precio del momento de la venta.
- **V014** incluye **PRD012**, hoy discontinuado. Estaba activo al venderse.
- **V011** está 'Pendiente' con **RC006**, y RC006 tiene 0 dispensas. Es
  coherente: una pendiente no dispensa ni descuenta stock.
- **RC009** está 'Vencida' con 0 dispensas. Las recetas no tienen fecha de
  vencimiento propia; el estado viene dado (ver D3).
- **F007** trabaja en la droguería **S005**. No debe poder registrar ventas
  (caso de rechazo para q14).
- **L018** (vencido el 30/09/2026, producto inactivo) y **L012** (vence el
  31/10/2026, vigente en la fecha de referencia pero vencido hoy). Sirven
  como lotes vencidos para q15 y siguen apareciendo en q08.

### Evidencia útil para las políticas de q14

- V006 y V007 (RC003) venden **dos productos bajo receta con una sola receta**,
  y RC003 suma una dispensa por venta (2 de 3, próxima = 01/09 + 30 = 01/10).
  Esto respalda contar **una dispensa por venta**, no por ítem.
- RC003 y RC004 son consistentes con N2; solo RC002 se aparta.

### Consecuencia para los datos adicionales (T07)

Con la fecha del sistema, los originales casi no producen resultados en las
consultas relativas: en noviembre de 2026 no hay ventas del mes actual (q11),
y el resultado de q05 depende del día en que se ejecute. Los adicionales deben incluir fechas relativas al
período de evaluación. Conviene que T07 genere esas fechas en el momento de la
carga, o documentar con qué fecha se ensayó.

## 8. Dudas e interpretaciones pendientes

Las dudas marcadas "Cátedra" se envían a la cátedra. Mientras no haya
respuesta, se aplica la interpretación propuesta y se documenta en el informe.

| # | Duda | Interpretación propuesta | Consultar a | Afecta a |
| --- | --- | --- | --- | --- |
| D1 | Cuatro integrantes (portada) frente a "tres" (§5.1) | Cuatro, confirmado por el equipo; los cuatro en carátula e historial | Cátedra | E6, E7 |
| D2 | ¿Cómo se cuentan los "10 registros por colección/tabla" con ítems embebidos o relaciones del grafo? | Al menos 10 filas propias por cada uno de los nueve datasets, detalle incluido | Cátedra | T07 |
| D3 | Vigencia de una receta sin fecha de vencimiento propia | Vigente = `estado == 'Vigente'`, sin calcular vencimiento por antigüedad | Cátedra | q14 |
| D4 | ¿`proxima_dispensa` futura impide dispensar antes de esa fecha? | No bloquea (la consigna la llama "fecha estimada"); se documenta | Cátedra | q14 |
| D5 | ¿Un lote que vence hoy puede dispensarse? | Utilizable hasta su fecha de vencimiento inclusive | Equipo | q15 |
| D6 | Varios productos bajo receta en una venta | Una sola receta cubre la venta y cuenta una dispensa (respaldado por RC003) | Equipo | q14 |
| D7 | ¿Cómo espera la cátedra que se ejecute q15: dentro de q14 o también aislada? | Se ejecuta en la transacción de q14; por terminal solo con protección contra doble descuento | Cátedra | T12, T14, T16 |
| D8 | ¿La sucursal debe estar activa además de ser tipo 'Farmacia'? | Validar también `activo` de la sucursal, aunque la consigna solo exige el tipo | Equipo | q14 |
| D9 | ¿El cliente dado de baja (`activo = False`) aparece en q12? | Sí; la consigna no lo excluye (C008 nunca compró y está inactivo) | Equipo | q12 |
| D10 | ¿Mezclar productos de venta libre y bajo receta en una venta? | Permitido; tipo 'Con receta' si se informa receta, 'Venta libre' si no | Equipo | q14 |
| D11 | Bajas lógicas en q13: ¿modificar un cliente dado de baja? | Rechazar modificaciones sobre clientes inactivos, salvo reactivación explícita | Equipo | q13 |
| D12 | ¿Se modifican los registros originales al operar (p. ej., q14 sobre RC006)? | Sí en la base; los CSV quedan intactos y la carga no pisa cambios de negocio | Equipo | T05 |

## 9. Verificación final

Antes de entregar, revisar cada fila de las secciones 2–5 y marcarla con el
commit o la evidencia que la cumple. Las dudas de la sección 8 deben estar
respondidas por la cátedra o documentadas en el informe como interpretación.
