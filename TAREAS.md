# FarmaRed — Tareas del equipo

Equipo de cuatro integrantes. Pilar es A. B, C y D son asignaciones provisionales.
Las estimaciones iniciales sumaban 99 horas, más margen.

## Estado revisado el 11/11/2026

- Docker Compose arranca ambos motores e inicializa el replica set. Se
  verificaron en Docker la carga repetida, la persistencia y el rollback con
  documentos de prueba antes de retirar los scripts de T03 y T04.
- Los cargadores importan los nueve CSV originales. Q01, q07, q08 y q11 se
  ejecutan por terminal y se comprobaron en MongoDB con resultados esperados.
- Quedan pendientes validar el modelo definitivo, cargar datos adicionales,
  sincronizar el grafo y completar las demás consultas. La prueba integrada de
  venta, receta y lotes de q14/q15 también sigue pendiente.

| Integrante | Responsabilidad | Horas estimadas al inicio |
| --- | --- | ---: |
| A · Pilar | Consultas MongoDB, FEFO e integración de venta, receta y stock | 24 |
| B | Modelo, sincronización Neo4j y consultas del grafo | 26 |
| C | Requisitos, carga MongoDB, ABM, venta y ensayo final | 24 |
| D | Datos propios, consultas, ejecución, pruebas e informe | 25 |

## Acuerdos para todos

1. Validar en conjunto el modelo y los contratos antes de desarrollar servicios separados.
2. Mantener los nueve CSV originales intactos; los datos propios van separados.
3. Cada integrante entrega código, pruebas, documentación y ejemplos de su parte.
4. Documentar cada q con propósito, parámetros, retorno y motor utilizado.
5. q03, q10 y q13–q15 reciben sus parámetros como argumentos, sin IDs fijos.
6. Las consultas temporales usan la fecha del sistema. Definir zona horaria y límites.
7. Trabajar en ramas por tarea. Cada integrante
   realiza sus propios commits; no compartir identidades ni credenciales.
8. No dar una tarea por terminada solo porque funciona con un ejemplo favorable.
9. Consultar a la cátedra la contradicción entre cuatro integrantes en portada y
   tres en entregables. El equipo confirmó que son cuatro. Incluir a los cuatro integrantes en
   la carátula y reflejar sus contribuciones en el historial.

## Base integrada — T03 y T04

Listas de verificación de referencia para el ensayo final.

### T03. Configurar Codespaces y el entorno — 6 h

Dependencia: base existente; coordinar ajustes con T02 y T04.

1. Comprobar que el repositorio clonado permite preparar variables locales sin subir secretos.
2. Configurar Codespaces reutilizando Compose y el entorno Python.
3. Resolver conexiones entre contenedores y acceso desde las herramientas de desarrollo.
4. Verificar y registrar versiones de dependencias utilizadas.
5. Probar inicio, detención y conservación de datos en volúmenes.
6. Actualizar el README con los pasos exactos de preparación y conexión.
7. Terminado: un Codespace nuevo levanta ambos motores siguiendo el README.

### T04. Habilitar transacciones MongoDB — 4 h

Dependencia: T02; modificar configuración coordinadamente con T03.

1. Convertir el entorno standalone actual a un replica set de desarrollo.
2. Resolver autenticación e inicialización repetible sin versionar secretos.
3. Comprobar que existe un PRIMARY y que las conexiones funcionan desde el entorno elegido.
4. Ejecutar una transacción que confirme cambios sobre varios documentos.
5. Ejecutar otra que falle y comprobar que no persiste ningún cambio parcial.
6. Documentar las garantías y las limitaciones del entorno de un nodo.
7. Terminado: confirmación y rollback reales comprobados, también en Codespaces.

## Integrante A · Pilar — Consultas, stock e integración transaccional

Esfuerzo pendiente estimado: 24 horas.

### T08. Implementar q01, q07, q08 y q11 — 10 h

Dependencias: T02, T05 y datos de prueba de T07.

1. q01: productos activos con todos los datos de su proveedor.
2. q07: top 5 por unidades vendidas, considerando solo ventas completadas.
3. q08: lotes con menos de 50 unidades, indicando producto, sucursal y proveedor.
4. q11: ingresos por farmacéutico en el mes actual, solo ventas completadas.
5. Usar funciones o módulos separados y documentar sus entradas y resultados.
6. Probar límites de stock 49/50, estados de venta, empates y períodos sin resultados.
7. No agregar filtros no pedidos: por ejemplo, q08 no exige excluir lotes vencidos.
8. Guardar un ejemplo comprobado por consulta para el informe.
9. Terminado: las cuatro funciones y sus pruebas pasan con los datos acordados.

### T12. Implementar q15: descuento de stock FEFO — 8 h

Dependencias: T02, T04, T05 y T07.

1. Recibir una venta identificada y resolver la sucursal de su farmacéutico.
2. Agrupar cantidades si hay ítems repetidos del mismo producto.
3. Seleccionar lotes de esa sucursal, omitiendo vencidos según la política acordada.
4. Consumir primero los lotes con vencimiento más próximo; definir desempate estable.
5. Repartir el consumo entre varios lotes si es necesario.
6. Rechazar toda la operación si falta stock en cualquiera de los productos.
7. Evitar stock negativo ante operaciones concurrentes y prevenir el doble descuento.
8. Participar en la sesión transaccional de q14, sin confirmar por su cuenta.
9. Probar cantidad exacta, insuficiencia en el segundo producto, vencidos y varios lotes.
10. Guardar lotes antes/después y evidencia de rechazo sin cambios parciales.
11. Terminado: q15 funciona integrada y cumple las garantías anteriores.

### T14. Integrar q14 y q15 — 6 h

Dependencias: T12 y T13.

1. Usar un coordinador y una misma transacción para venta, receta y stock.
2. Acordar con C que la venta registrada dentro de la transacción no quede confirmada
   antes del descuento de stock.
3. Propagar errores: q15 no debe ocultar una falla ni confirmar cambios independientes.
4. Inyectar fallos después de modificar un lote y después de actualizar la receta.
5. Verificar ausencia de venta y reversión completa de receta y lotes en cada rechazo.
6. Definir reintentos seguros, incluyendo prevención de ventas o descuentos duplicados.
7. Guardar evidencia de una venta válida y de una rechazada de extremo a extremo.
8. Terminado: éxito completo o rechazo completo, comprobado con pruebas reales.

## Integrante B — Modelo, grafo y consultas de relaciones

Esfuerzo pendiente estimado: 26 horas.

### T02. Definir modelo y contratos — 6 h

Dependencia: T01.

1. Justificar MongoDB documental y Neo4j de grafos con casos de uso concretos.
2. Definir la fuente autoritativa y los datos que se representan en cada motor.
3. Diseñar documentos, posibles ítems embebidos, etiquetas, relaciones e índices.
4. Conservar identificadores de origen y acordar tipos, nulos y representación de fechas.
5. Definir firmas, resultados y errores de servicios compartidos, especialmente q14/q15.
6. Acordar límites temporales, vencimiento en el día actual y comportamiento de reintentos.
7. Definir actualización del grafo y tratamiento de datos históricos o desnormalizados.
8. Crear diagramas breves y registrar decisiones e interpretaciones pendientes.
9. Terminado: los cuatro aprueban un modelo que permite resolver las quince funciones.

### T06. Adaptar carga y sincronización de Neo4j — 9 h

Dependencias: T02 y contrato de datos de T05.

1. Adaptar el loader exploratorio al modelo aprobado.
2. Crear restricciones y relaciones con identificadores estables, sin duplicaciones.
3. Incorporar originales y adicionales conservando sus tipos y referencias.
4. Implementar una sincronización explícita desde la fuente autoritativa acordada.
5. Definir cómo actualizar propiedades y relaciones existentes, no solamente insertar nodos.
6. Garantizar una lectura consistente para la proyección y su actualización transaccional.
7. Resolver qué ocurre si falla la sincronización antes de una consulta del grafo.
8. Probar repetición, cambios posteriores, referencias y recuperación tras interrupciones.
9. No afirmar atomicidad conjunta entre MongoDB y Neo4j.
10. Terminado: el grafo refleja los datos acordados y no presenta información obsoleta
    como actual si la actualización falla.

### T09. Implementar q03, q04, q06, q10 y q12 — 11 h

Dependencias: T02, T06 y T07.

1. q03: historial completo de ventas y recetas del cliente recibido por argumento,
   ordenado cronológicamente; definir desempate de fechas.
2. q04: clientes con más de una receta, indicando cantidad de recetas únicas.
3. q06: tratamientos prolongados vigentes con próxima dispensa anterior a hoy y cliente.
4. q10: clientes atendidos en la sucursal recibida por argumento, incluso a través de
   farmacéuticos hoy inactivos; evitar duplicar clientes.
5. q12: clientes sin ventas registradas en el último año, incluidos quienes nunca compraron.
6. Probar cliente o sucursal inexistente, ausencia de relaciones y fechas límite.
7. Respetar los filtros de la consigna; no excluir estados o clientes inactivos por suposición.
8. Verificar que las consultas usan la proyección actualizada según el contrato de T06.
9. Documentar cada función y guardar un ejemplo para el informe.
10. Terminado: las cinco funciones devuelven resultados contrastados y casos vacíos correctos.

## Integrante C — Carga MongoDB, clientes, ventas y ensayo final

Esfuerzo pendiente estimado: 24 horas.

### T01. Cerrar requisitos y decisiones pendientes — 3 h

Sin dependencias técnicas.

1. Registrar requisitos obligatorios, entregables y criterios de evaluación.
2. Separar exigencias de la consigna de recomendaciones del equipo.
3. Registrar la contradicción sobre integrantes y la fecha de entrega comunicada.
4. Documentar RC002 y distinguir anomalías de estados históricos válidos.
5. Identificar dudas sobre bajas lógicas, vencimientos y cómputo de adicionales.
6. Asignar a cada requisito una tarea de este plan.
7. Terminado: hay una lista breve que permita comprobar que no falta ningún requisito.

### T05. Adaptar la carga MongoDB — 4 h

Dependencia: T02.

1. Adaptar colecciones y documentos al modelo aprobado; la carga actual es exploratoria.
2. Mantener tipos, identificadores, referencias e índices únicos de DNI y matrícula.
3. Incorporar originales y adicionales sin modificar los CSV de la cátedra.
4. Evitar que la importación de ventas históricas vuelva a descontar stock.
5. Repetir la carga y comparar conteos, identificadores y contenido.
6. Distinguir carga aditiva de un reinicio destructivo explícito de la demostración.
7. Definir cómo pasar de la carga exploratoria al modelo final. Los upserts
   actuales conservan los documentos existentes. Verificar la transición en una
   base aislada.
8. Acordar con B la interfaz de datos utilizada para construir el grafo.
9. Terminado: la carga real es repetible, verificable y no sobrescribe operaciones de negocio.

### T11. Implementar q13: ABM de clientes — 5 h

Dependencias: T02 y T05.

1. Alta de cliente con identificador y DNI únicos, mediante validación e índice único.
2. Modificación de datos de contacto y cobertura recibidos como argumentos.
3. Baja lógica con activo=False, conservando registro e historial.
4. Definir resultados y errores para cliente inexistente y datos inválidos.
5. Probar altas concurrentes con el mismo DNI y verificar que solo una prospere.
6. Verificar el efecto de cambios y bajas en la actualización del grafo según T06.
7. Guardar antes/después de cada operación y al menos un rechazo por validación.
8. Terminado: alta, modificación y baja funcionan sin eliminar físicamente clientes.

### T13. Implementar q14: registro de venta — 8 h

Dependencias: T02, T04 y T05; integrar con T12.

1. Recibir cliente, farmacéutico, ítems y receta cuando corresponda como argumentos.
2. Validar cliente existente y activo.
3. Validar farmacéutico existente, activo y perteneciente a una sucursal tipo Farmacia.
4. Validar productos existentes y activos, y cantidades positivas.
5. Para productos bajo receta, validar receta existente, vigente y del mismo cliente.
6. Calcular el total desde los ítems y conservar el precio vigente de la venta en el detalle.
7. Incrementar dispensas por dispensa, no por cada ítem vendido; coordinar la política
   para ventas con varios productos bajo una receta.
8. Completar recetas simples/archivadas con su única dispensa; para tratamiento prolongado,
   fijar próxima dispensa a 30 días o completar y vaciar la fecha al alcanzar el límite.
9. Invocar q15 dentro de la misma transacción y propagar cualquier rechazo.
10. Probar entidades inexistentes/inactivas, droguería, receta ajena/vencida/completada,
    stock insuficiente, total calculado y última dispensa.
11. Guardar antes/después y casos de rechazo para el informe.
12. Terminado: funciona de extremo a extremo junto con T12/T14, sin cambios parciales.

### T18. Realizar el ensayo final — 4 h

Dependencias: T03, T04 y T15–T17.

1. Crear un Codespace limpio desde la versión candidata a entrega.
2. Seguir únicamente el README, registrando cualquier paso faltante.
3. Iniciar motores, cargar originales y adicionales, y repetir la carga.
4. Ejecutar pruebas y las quince funciones con parámetros reales cuando corresponda.
5. Comprobar que el informe y sus ejemplos coinciden con la versión entregada.
6. Revisar secretos, archivos temporales y participación real en el historial.
7. Corregir diferencias y repetir solamente las verificaciones afectadas.
8. Terminado: otro integrante puede reproducir todo sin instrucciones externas.

## Integrante D — Datos propios, consultas, pruebas e informe

Esfuerzo pendiente estimado: 25 horas.

### T07. Preparar datos adicionales — 6 h

Dependencias: T02 y coordinación con T05/T06.

1. Acordar identificadores propios sin colisiones con los originales ni entre integrantes.
2. Cubrir al menos diez registros adicionales por colección/tabla según el modelo;
   consultar cómo se cuentan detalles embebidos y estructuras del grafo.
3. Como criterio conservador, preparar al menos diez filas propias por dataset de negocio
   y verificar luego su correspondencia con las estructuras finales.
4. Incluir fechas recientes, ventas pendientes/anuladas y clientes sin compras recientes.
5. Incluir profesionales activos sin ventas, múltiples recetas y tratamientos atrasados.
6. Incluir stock bajo, lotes vencidos/próximos a vencer y consumo repartido entre lotes.
7. Preparar casos de insuficiencia y validación para las pruebas sin contaminar la carga válida.
8. Validar referencias, unicidad, totales y coherencia de los estados.
9. Documentar qué consulta o prueba ejercita cada escenario.
10. Terminado: mínimos y casos borde están cubiertos con datos trazables y reproducibles.

### T10. Implementar q02, q05 y q09 — 5 h

Dependencias: T02, T05 y T07.

1. q02: ventas pendientes con nombre, matrícula y sucursal del farmacéutico, más total.
2. q05: farmacéuticos activos con cantidad de ventas en los últimos 60 días, excluyendo
   anuladas e incluyendo quienes tienen cero; las pendientes no están excluidas.
3. q09: ventas libres con total menor a 5.000 ARS, excluyendo anuladas.
4. Probar límites temporales, profesionales con cero ventas y montos 4.999/5.000.
5. No inventar exclusiones adicionales de clientes, profesionales o estados.
6. Documentar cada función y guardar un resultado comprobado.
7. Terminado: las tres funciones respetan los filtros y sus casos borde.

### T15. Probar concurrencia y fallos parciales — 6 h

Dependencias: T06 y T14; preparar escenarios con anticipación.

1. Ejecutar dos ventas que compitan por las mismas unidades de stock.
2. Comprobar que las unidades nunca sean negativas ni se vendan dos veces.
3. Probar competencia por la última dispensa disponible de una receta.
4. Probar reintentos de una misma operación sin duplicar efectos.
5. Simular fallas intermedias y comprobar venta, receta y todos los lotes.
6. Simular indisponibilidad del grafo, recuperar el servicio y verificar sincronización.
7. Registrar resultados esperados y observados con escenarios repetibles.
8. Terminado: las pruebas demuestran las garantías prometidas y documentan sus límites.

### T16. Unificar ejecución de las quince funciones — 3 h

Dependencia: contratos T02 y módulos disponibles.

1. Proponer una entrada simple por terminal, sin agregar API ni interfaz web.
2. Permitir ejecutar q01–q15 con argumentos reales cuando corresponda.
3. Mostrar resultados y errores de forma legible y consistente.
4. Leer configuración sin imprimir contraseñas ni incorporarlas al código.
5. Documentar un comando reproducible para cada función en el README.
6. Terminado: otro integrante puede ejecutar las quince funciones siguiendo los ejemplos.

### T17. Unificar informe y evidencias — 5 h

Dependencia: aportes y resultados de todas las tareas.

1. Preparar carátula, integrantes y enlace al repositorio.
2. Integrar justificación de motores, distribución de datos y diagramas de ambos modelos.
3. Explicar carga idempotente, registros adicionales e inconsistencias conservadas.
4. Incluir las quince funciones con enunciado, código o sentencia y un ejemplo de resultado.
5. Incorporar estados antes/después y rechazos de q13, q14 y q15.
6. Explicar integridad, transacción de venta/stock y consistencia del grafo.
7. Incluir limitaciones, alternativas evaluadas y conclusiones.
8. Exportar a PDF y revisar legibilidad de tablas, diagramas y código.
9. Terminado: el PDF cumple la consigna y coincide con el código de entrega.

## Orden de integración

1. C cierra T01 y B coordina T02 con los cuatro integrantes.
2. C adapta MongoDB, B prepara la proyección de Neo4j y D prepara los datos propios.
   A y C acuerdan las firmas de q14/q15 durante T02.
3. A implementa FEFO y C implementa el registro de ventas. Integrar pronto un caso
   válido y otro por stock insuficiente.
4. En paralelo, A, B y D desarrollan las lecturas en módulos separados.
5. D ejecuta las pruebas de fallos y concurrencia e integra los ejemplos al informe.
   Cada integrante aporta los resultados de sus tareas.
6. C ensaya la entrega desde un Codespace limpio.

Ruta crítica: T02 → T05 → T12 + T13 → T14 → T15 → T18.
T06 también debe estar lista para validar las consultas del grafo.

## Condición de entrega del equipo

1. Dos motores NoSQL de paradigmas diferentes, con uso y modelo justificados.
2. Entorno completo reproducido desde Codespaces mediante el README.
3. Originales intactos, adicionales suficientes y carga ejecutada dos veces sin duplicación.
4. Quince funciones separadas, documentadas y comprobadas con sus filtros exactos.
5. Fechas relativas calculadas con el sistema y casos con conteos cero donde se exige.
6. q13 con unicidad y baja lógica; q14/q15 con atomicidad, FEFO y reintentos seguros.
7. Pruebas de concurrencia y fallos intermedios sin efectos parciales persistidos.
8. Informe PDF con diagramas, resultados, antes/después, rechazos y conclusiones.
9. Repositorio sin secretos y con contribuciones técnicas propias de los cuatro integrantes.

## Commits sugeridos

- T01: `docs: registrar requisitos y decisiones del TP`.
- T02: `docs: definir modelo y contratos de servicios`.
- T03: `chore: configurar entorno reproducible en Codespaces`.
- T04: `chore: habilitar transacciones de MongoDB`.
- T05: `feat: adaptar carga MongoDB al modelo acordado`.
- T06: `feat: implementar carga y sincronizacion del grafo`.
- T07: `feat: agregar datos propios y casos borde`.
- T08: `feat: implementar consultas de catalogo stock e ingresos`.
- T09: `feat: implementar consultas de clientes y recetas`.
- T10: `feat: implementar consultas de ventas y farmaceuticos`.
- T11: `feat: implementar ABM de clientes`.
- T12: `feat: implementar descuento de stock FEFO`.
- T13: `feat: implementar registro validado de ventas`.
- T14: `feat: integrar venta receta y stock en una transaccion`.
- T15: `test: verificar concurrencia y fallos parciales`.
- T16: `feat: agregar ejecucion por terminal de las consultas`.
- T17: `docs: completar informe y evidencias del TP`.
- T18: `test: validar entrega desde un Codespace limpio`.

Estos mensajes son propuestas; no se realizan commits ni pushes automáticamente.
