# Agentes operativos y automatizaciones

Implementación integrada en `AutomationService` mediante composición con servicios de inventario, comercial y un flujo específico de recepción de pedidos existentes. `ExecutiveService` conserva su política de solo lectura; se corrige además la posición de su método `decisions` dentro de la clase.

## Acceso y arranque

En la navegación principal, **Resumen → Centro de control de agentes** (`/agentes/control`) y **Editor de reglas** (`/agentes/reglas`). El frontend usa la sesión y los estilos existentes. La antigua pantalla del Ejecutivo muestra también las nuevas propuestas de compra y enlaza al centro para aprobarlas.

La migración aditiva es `BackEnd/apps/MonoliticDataStructure/app/src/DataBaseManagement/automation_schema.sql`. Se aplica al inicializar el backend, después del esquema operativo existente, siguiendo el mecanismo de extensiones del proyecto. Para una instalación nueva se debe arrancar la API además de inicializar PostgreSQL. No es necesario reaplicar `init.sql` sobre una base existente.

La migración conserva las propuestas antiguas, pero marca como obsoletas sus propuestas pendientes: carecen de instantánea de evidencia y de versión de política. Deben analizarse de nuevo antes de ejecutar. No se transforman en pedidos ni se eliminan.

En desarrollo, Vite sirve las páginas en `http://localhost:5173`. El portal Nginx necesita recompilar su imagen para incorporar los cambios de frontend. Esta entrega no publica una nueva imagen Nginx.

## Permisos y autonomía

Las rutas de automatización exigen una sesión firmada, una cuenta activa y permisos consultados en PostgreSQL. Una clave API por sí sola no concede acceso operativo. `users.automation_permissions` admite:

| Permiso | Uso |
| --- | --- |
| `read` | Consultar reglas, actividad, propuestas, métricas y revisar resultados |
| `edit` | Guardar versiones y simular instantáneas |
| `activate` | Activar, pausar, ejecutar análisis y usar el interruptor de parada |
| `approve` | Aprobar o rechazar una propuesta con motivo |
| `execute` | Ejecutar una acción aprobada y confirmar recepción o traslado físico |
| `authorize` | Autorizar presupuestos, proveedores de IA sin coste medido y políticas automáticas |

Al crear la columna, la cuenta administradora inicial recibe estos permisos; las demás cuentas reciben `read`. La migración no vuelve a conceder permisos revocados en reinicios posteriores. La asignación adicional se administra en base de datos; la pantalla de usuarios existente no edita esta nueva columna.

Los modos son `observation`, `assisted` y `limited_auto`. Activar una regla habilita su análisis; no concede permisos operativos. Una nueva versión se guarda pausada y registra autor, fecha y motivo. Cambiar una política automática requiere autorización; cambiar una regla invalida sus propuestas pendientes. Se rechazan cambios mientras la regla tiene una ejecución en curso y ediciones basadas en una versión anterior.

Pausar una regla detiene su programación futura. Las propuestas vigentes de esa versión conservan la posibilidad de aprobación explícita. Para bloquear todas las acciones, usar el interruptor de parada; se consulta de nuevo dentro de la transacción operativa. También existe `AUTOMATION_EMERGENCY_STOP=true` como parada del entorno.

## Ciclo y contratos

El worker existente sigue usando una conexión propia por ciclo, sin compartir conexiones con peticiones ni con otros hilos. Cada proceso puede iniciar su worker: la exclusión entre procesos reside en PostgreSQL.

1. Reclama la regla con bloqueo breve `FOR UPDATE SKIP LOCKED` y un token de propietario.
2. Persiste la versión exacta y su configuración en la ejecución.
3. Consulta stock, reservas, compras pendientes, despachos, costes históricos y unidades.
4. Calcula escenarios y registra la evidencia completa antes de consultar IA.
5. El modelo elige y prioriza alternativas; puede pedir herramientas tipadas o terminar sin acciones.
6. El código valida entidades, alternativas y políticas. En observación/simulación solo registra análisis.
7. Crea propuestas idempotentes, solicita aprobación o intenta únicamente acciones automáticas autorizadas.
8. Revalida antes de aprobar y de ejecutar; registra identidad, autorización y resultado.
9. Revisa resultados vencidos cada sondeo del worker o mediante la API.

No se solicitan cadenas internas de pensamiento. Se guardan motivos breves, cálculos, resultados de herramientas y evidencias. El modelo no recibe acceso a SQL ni a métodos de mutación. Los textos del catálogo se tratan como datos. Las herramientas permitidas son `product_snapshot` y `compare_scenarios`, siempre sobre entidades ya observadas; se rechazan nombres, identificadores y respuestas fuera del contrato Pydantic.

La IA decide el orden y tipo de acción dentro de alternativas calculadas por código. Si falla o su respuesta es inválida, la ejecución queda **degradada** con su análisis determinista persistido, sin inventar una decisión de IA ni ejecutar un respaldo fijo.

## Cálculos y datos

Cantidades y dinero se calculan con `Decimal`. Para reposición:

```text
disponible = físico − reservado
media_diaria_de_despachos = despachos_confirmados_90_días / 90
objetivo = máximo(punto_de_pedido,
                  media_diaria × (cobertura_objetivo + plazo_configurado) + seguridad)
necesidad = máximo(0, objetivo − disponible − compras_pendientes)
si necesidad > 0:
  cantidad = redondear_hacia_arriba_a_múltiplo(
               máximo(necesidad, mínimo_configurado, cantidad_de_reposición_del_producto))
```

La cantidad de reposición del producto es una configuración de inventario, no un mínimo contractual del proveedor. Las compras pendientes se agregan por producto y almacén desde pedidos emitidos/parciales. Las reservas se descuentan una sola vez. Despachos, devoluciones y traslados tienen tipos de movimiento distintos; los traslados y devoluciones no se suman como ventas.

La media de despachos describe registros confirmados. No demuestra demanda en días sin registro ni disponibilidad completa. Las tendencias del servicio comercial ahora usan ventanas reales de fechas y señalan historial insuficiente. No se rellenan días ausentes como observaciones de demanda cero.

Para trasladar se exige demanda registrada en el destino y que el origen conserve el máximo de su punto de pedido y cobertura mínima, más seguridad. La cantidad se redondea hacia abajo a cuatro decimales. Los costes logísticos desconocidos se mantienen como desconocidos. Al confirmar físicamente se reutilizan bloqueos, conversiones, invariantes y movimientos de `InventoryService` dentro de una única transacción, sin sus commits internos.

La cobertura excesiva y la ausencia de despachos generan candidatos para revisión; con historial incompleto se indica la limitación. Una promoción solo tiene precio de referencia cuando existe coste histórico. Se condiciona a coste vigente, margen mínimo, precio y costes comerciales; nunca se publica ni se presupone respuesta del cliente. Devolver a proveedor requiere condiciones verificadas que el catálogo operativo actual no contiene.

## Acciones implementadas

| Acción | Comportamiento real |
| --- | --- |
| Esperar | Decisión registrada sin operación |
| Reposición | Propuesta; después de aprobación y oferta humana vigente en EUR, emite un pedido y líneas pendientes; no aumenta stock |
| Recepción | Confirmación física parcial o completa del pedido emitido; crea recepción y movimientos, actualiza pendiente; no duplica pedido |
| Traslado | Propuesta; exige aprobación, permiso de ejecución y confirmación física explícita antes del movimiento |
| Suspender reposición | Suprime nuevas propuestas automáticas por producto/almacén hasta la revisión; no cancela pedidos ni cambia configuración de producto |
| Promoción/paquete/venta cruzada | Recomendación condicionada; sin preparación ni publicación de campañas |
| Devolución al proveedor | Propuesta condicionada; sin operación por falta de términos verificables |

En automático limitado solo puede ejecutarse actualmente la supresión de reposición. El contrato contempla reposición entre tipos autorizables, pero su ejecución automática permanece bloqueada porque no existe integración de ofertas vigentes: una oferta humana se adjunta al ejecutar una compra aprobada. No se declara esta compra automática como terminada.

Los presupuestos se expresan en EUR y el periodo diario es UTC. El límite diario suma compras de automatización de todas las reglas y se serializa con el interruptor de control. No incluye compras externas a este flujo: falta un presupuesto corporativo integrado. Las ofertas en otras monedas se rechazan; no se inventan conversiones actuales. El presupuesto por acción también se vuelve a comprobar al ejecutar.

## Límites, concurrencia y reintentos

Valores predeterminados: análisis diario, 30 entidades por ciclo, 2 llamadas de modelo, 4 herramientas, 120 segundos de análisis, 4096 tokens máximos de salida por llamada, caducidad de propuestas de 24 horas, enfriamiento de 24 horas y revisión a 30 días. Los rangos máximos están definidos en `RuleConfig`; el editor impone rangos y el servidor los valida de nuevo. Frecuencia mínima: 15 minutos. Ventanas de ejecución usan una zona IANA configurada y no cruzan medianoche.

Se fuerza Ollama sin fallback de pago por defecto. Para permitir proveedores que no informan coste monetario se necesita autorización explícita en la regla. Los tiempos HTTP se acotan por llamada al presupuesto restante y una respuesta recibida fuera de plazo se descarta. Se conserva el uso de tokens cuando el proveedor lo devuelve. No se estima un precio monetario sin datos del proveedor.

El lease dura diez minutos, por encima del máximo de análisis admitido. Al caducar se marca la ejecución abandonada, se registra recuperación y se incrementan intentos. El token impide a un propietario anterior crear propuestas o sobrescribir el resultado de otro. Después de tres fallos/abandonos el scheduler deja de reclamar la regla; reactivar o ejecutar manualmente permite una recuperación supervisada. Un fallo no detiene otras reglas.

Hay unicidad de clave de propuesta y de propuesta abierta por producto, almacén y tipo de acción. Los datos modificados vuelven obsoleta la propuesta anterior al siguiente análisis. En ejecución se bloquea la entidad, se comprueban políticas actuales y se repite la validación; los reintentos de acciones ejecutadas devuelven el resultado original. Las recepciones usan su propia clave de operación y rechazan reutilizarla con cantidades diferentes.

La simulación de instantánea del editor no llama al modelo ni crea ejecuciones, propuestas, pedidos, movimientos, campañas o reservas. Devuelve escenarios deterministas, fecha de datos, autorizaciones/bloqueos previstos y solapamientos. Por ello no garantiza qué alternativa elegirá el modelo en una ejecución posterior. Si se guarda una regla con `simulation=true`, sus ejecuciones sí registran eventos y pueden consultar IA dentro de sus límites, pero no persisten propuestas operativas ni ejecutan acciones. Se bloquea activar autonomía automática con reglas de ámbito contradictorio y se conserva deduplicación/revalidación para reglas coincidentes.

## Métricas y límites de evaluación

El centro usa sondeo controlado (15 segundos, suspendido cuando la página está oculta) y eventos por ejecución. Muestra versión de regla, modelo observado, estado de conexión, errores, datos vacíos, latencia mediana/P95, respuestas válidas del modelo, herramientas, fallos del proveedor y bloqueos de políticas. Las métricas se filtran por regla, periodo, versión y modelo. Solo hay un coordinador operativo; los servicios auxiliares no se presentan como agentes programados independientes.

Las series y tablas proceden de PostgreSQL. El éxito técnico incluye ejecuciones degradadas que conservaron su análisis; no mide acierto comercial. El denominador mostrado es el total de ejecuciones del periodo. Los tokens cubren solo llamadas con uso informado; el coste monetario y coste por tarea permanecen no disponibles. Las ejecuciones históricas anteriores a la migración pueden no tener eventos.

Por decisión vencida se registran despachos y devoluciones del periodo, previsión de referencia, MAE, WAPE y sesgo. MAE y sesgo usan unidades base; WAPE es una razón y queda no disponible si el total observado es cero. Cada registro individual tiene una única observación agregada por horizonte: no debe interpretarse como una muestra robusta. Se conserva el tipo de acción, versión, modelo y trazabilidad para posteriores evaluaciones.

El editor permite configurar un umbral de unidades despachadas confirmadas durante el horizonte de revisión (`objective_target`). Con umbral explícito, el objetivo se evalúa como despachos confirmados >= umbral; sin él queda no evaluable. La tasa de cumplimiento muestra su denominador y no se presenta como fiabilidad de la decisión, probabilidad de éxito ni efecto causal de la acción.

La instantánea de negocio muestra disponibilidad actual, despachos de 90 días, cobertura y capital a coste histórico donde existe coste. No se presenta una falta de disponibilidad puntual como una serie de roturas ni como ventas perdidas. La rotación sobre inventario medio, margen realizado por acción, beneficio neto atribuible, coste logístico, calibración de probabilidades y fiabilidad causal están **no disponibles**, por falta de observaciones o integraciones suficientes. Sin objetivo medible configurado se indica no evaluable y la fiabilidad indica **Evidencia insuficiente**. La aprobación humana no se usa como resultado positivo.

Faltan una categoría vinculada al catálogo operativo, un historial completo de disponibilidad diaria, ofertas vigentes automatizadas, plazos y fiabilidad observados por proveedor, condiciones de devolución y costes comerciales/logísticos. El catálogo analítico dispone de otros campos, pero no hay un vínculo fiable para mezclarlos con productos operativos. Se pueden crear reglas distintas por listas de productos; no se inventa una relación de categorías.

## API

Todas bajo `/api/automation`:

| Ruta | Uso |
| --- | --- |
| `GET/PUT /control` | Estado y parada global |
| `GET/POST /rules`, `PUT /rules/{id}` | Consultar y guardar versiones |
| `GET /rules/{id}/versions` | Historial para comparación/restauración como nueva versión |
| `POST /simulate` | Validar y simular `RuleConfig` |
| `GET /runs`, `GET /runs/{id}/events` | Actividad y traza |
| `GET /proposals` | Propuestas y evaluación |
| `POST /proposals/{id}/decision` | `{approve, reason}` |
| `POST /proposals/{id}/execute` | `{physical_confirmed, quote?}` |
| `POST /proposals/{id}/receipt` | Recepción física con cantidad y clave idempotente |
| `POST /evaluate` | Revisar resultados vencidos |
| `GET /metrics?days=30&rule_id=1&version=1&model=...` | Métricas trazables |

Activar/pausar y analizar ahora mantienen las rutas compatibles `/api/executive/automations/{id}` y `/api/executive/automations/{id}/run`, con los mismos controles de sesión y permiso. Las versiones se identifican con `expected_version` para detectar ediciones concurrentes.

## Demostración y pruebas reproducibles

Con los contenedores locales en ejecución, desde la raíz del repositorio:

```powershell
& .\BackEnd\apps\MonoliticDataStructure\app\scripts\test_automation.ps1
node Frontend/node_modules/typescript/bin/tsc --noEmit -p Frontend/tsconfig.json
Set-Location Frontend
npm.cmd run build
```

La suite crea una base `automation_test_<aleatorio>`, aplica el esquema y la migración, usa dobles del proveedor de IA y elimina solo esa base al terminar. No necesita pytest dentro del contenedor ni realiza llamadas pagadas. El usuario PostgreSQL de pruebas debe poder crear una base. Los fixtures permanecen separados de los indicadores de negocio reales.

`test_e2e_purchase_receipt_separated_and_idempotent_evaluation` reproduce detección → comparación → propuesta → aprobación → pedido emitido → recepción parcial física → registro → revisión posterior. Comprueba que emitir no cambia existencias, recibir no crea otro pedido y repetir la operación no duplica movimientos. La evaluación temporal se adelanta únicamente en la base temporal de pruebas.

`test_physical_transfer_requires_confirmation_conserves_stock_and_is_idempotent` prueba el traslado completo y sus dos movimientos. Las otras pruebas cubren reservas y compras pendientes, ausencia de costes/demanda, herramientas desconocidas, permisos, presupuestos, salida inválida, caída de proveedor, simulación, dos reclamaciones concurrentes, versiones concurrentes, datos caducados, cambio de regla, lease abandonado y continuidad del scheduler tras fallos.

Para el recorrido de negocio en una instalación de pruebas: abrir Editor → crear regla asistida con productos y almacenes existentes → validar/simular → guardar versión pausada → activar → abrir Centro y analizar → consultar traza y alternativas → aprobar con motivo → adjuntar oferta vigente en EUR y ejecutar → al recibir físicamente, registrar unidades recibidas → después del horizonte, consultar evaluación. Mantener la regla pausada o usar simulación si todavía no se desea programación real. La IA local debe estar disponible para obtener una propuesta elegida por modelo; si no lo está se verá el análisis degradado y no se fabricará una decisión.

Verificaciones de navegador realizadas en desarrollo: sesión local, enlaces de navegación de ambas páginas, etiquetas de formularios visibles en el árbol de accesibilidad, carga de métricas persistidas y simulación de datos reales sin guardar una regla. La demostración de aprobación, ejecución y evaluación se automatiza en la base temporal, no en los datos del usuario.
