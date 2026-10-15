Actúa como arquitecto e ingeniero sénior de agentes de IA especializados en inventario, compras y ventas. Implementa los cambios en este repositorio; no te limites a describir una arquitectura.

Punto de partida:
BackEnd/apps/MonoliticDataStructure/app/src/executive_service.py
Clase principal: AutomationService.

OBJETIVO

Transformar AutomationService en un agente operativo que, al activar sus reglas, analice periódicamente el negocio, detecte oportunidades y problemas, compare acciones, genere propuestas, ejecute las acciones autorizadas y evalúe sus resultados.

Debe contribuir a reducir roturas de stock, exceso de inventario y capital inmovilizado, manteniendo márgenes y disponibilidad. No prometas crecimiento ni beneficios garantizados.

1. INSPECCIONA E INTEGRA EL CÓDIGO EXISTENTE

Antes de modificar:
- Lee las instrucciones del repositorio.
- Revisa AutomationService, ExecutiveService, AgentService,
  CommercialAgentService, InventoryService, ai_service, SystemPrompts,
  las rutas reales, los esquemas SQL y los tests.
- Localiza la interfaz que activa reglas y muestra propuestas.
- Reutiliza generate_ai y los servicios de dominio existentes.
- Comprueba qué datos existen realmente: ventas, reservas, compras
  pendientes, costes, proveedores, plazos, almacenes y devoluciones.
- No inventes tablas, columnas, endpoints ni capacidades disponibles.

Mantén la política de lectura de ExecutiveService. Implementa las
capacidades operativas mediante composición y servicios específicos.

2. IMPLEMENTA UN CICLO AGÉNTICO

Cada ejecución debe seguir:
observar → diagnosticar → consultar herramientas → comparar alternativas
→ proponer un plan → validar políticas → actuar o solicitar aprobación
→ registrar resultados → revisar posteriormente.

La IA debe participar en la selección y priorización de acciones,
no limitarse a redactar una explicación de decisiones fijas.

Permite obtener información adicional mediante herramientas de dominio
con contratos tipados. Limita pasos, llamadas, duración y coste por ciclo.
Finaliza explícitamente cuando falten datos o ninguna acción aporte valor.

El modelo propone; el código valida cantidades, permisos, presupuesto,
disponibilidad, unidades y restricciones.

3. REPOSICIÓN INTELIGENTE

Genera propuestas por producto y almacén considerando, cuando existan:
- Demanda histórica, cambios recientes y calidad del historial.
- Stock disponible, reservado y compras pendientes de recibir.
- Plazos de suministro y variabilidad.
- Stock de seguridad y cobertura objetivo.
- Cantidades mínimas, múltiplos de compra y unidades base.
- Coste total, presupuesto disponible y fiabilidad del proveedor.

Calcula cantidades mediante funciones verificables y Decimal.
Distingue datos observados, estimaciones y supuestos.

Antes de comprar, compara:
a) No actuar.
b) Reponer desde proveedor.
c) Redistribuir excedente de otro almacén.

No dupliques propuestas ni pedidos. Revisa propuestas existentes cuando
cambien los datos y permite marcarlas como obsoletas.

No uses confirm_receipt para crear un pedido pendiente: una compra
propuesta, un pedido emitido y una recepción física son hechos distintos.

4. STOCK ESTANCADO Y ACTIVACIÓN COMERCIAL

Detecta productos con exceso de cobertura, baja rotación o ausencia
prolongada de ventas mediante umbrales configurables por categoría.

No confundas ausencia de ventas con falta de demanda cuando el producto
haya estado sin disponibilidad. Separa ventas, devoluciones y traslados.

Para cada caso compara:
- Trasladar unidades a un almacén con demanda demostrada.
- Reducir o suspender reposición.
- Proponer una promoción, un paquete o venta cruzada.
- Proponer devolución al proveedor si existen condiciones verificadas.
- Esperar cuando actuar cueste más que el beneficio esperado.

Para traslados, verifica disponibilidad libre, cobertura del origen,
necesidad del destino y coste logístico si se conoce.

Para promociones, calcula el margen con costes reales y respeta un
margen mínimo configurable. Si falta información, genera una propuesta
condicionada; no inventes rentabilidad ni respuesta del cliente.

Distingue una recomendación comercial, una campaña preparada y una
campaña publicada. No envíes comunicaciones sin autorización específica.

5. HERRAMIENTAS Y SALIDA ESTRUCTURADA

Define herramientas permitidas para consultar datos, calcular escenarios,
crear propuestas, revisar propuestas y ejecutar acciones autorizadas.

El modelo no puede ejecutar SQL arbitrario ni modificar existencias
directamente. Reutiliza InventoryService y sus invariantes.

Exige salida estructurada y validada con:
- Tipo de acción y entidades afectadas.
- Evidencias: fuente, periodo y fecha.
- Cantidades, unidades y cálculos asociados.
- Alternativas consideradas.
- Justificación breve y verificable.
- Impacto estimado, supuestos y limitaciones.
- Dependencias, caducidad y condiciones de ejecución.
- Necesidad de aprobación y clave de idempotencia.
- Métricas y fecha de revisión del resultado.

Rechaza herramientas desconocidas, identificadores inválidos, cantidades
imposibles y respuestas que incumplan el esquema.

No solicites cadenas internas de pensamiento; registra evidencias,
cálculos y motivos de decisión.

6. AUTONOMÍA CONFIGURABLE

Implementa tres modos:
- Observación: analiza y registra, sin ejecutar operaciones.
- Asistido: crea propuestas que requieren aprobación.
- Automático limitado: ejecuta únicamente tipos de acción expresamente
  autorizados y dentro de límites configurados.

Activar una regla habilita su análisis periódico; no concede por sí solo
permiso para gastar, publicar campañas o registrar movimientos físicos.

Configura límites por operación y periodo, margen mínimo, cobertura
mínima, alcance por almacén y caducidad de propuestas.

Antes de ejecutar o aprobar, vuelve a validar datos y políticas actuales.
Registra quién aprobó, qué autorizó y qué se ejecutó.

Un traslado sugerido no demuestra que la mercancía se haya movido:
respeta el flujo logístico real y exige confirmación física cuando proceda.

Incluye modo simulación e interruptor de parada.

7. FIABILIDAD Y CONCURRENCIA

Corrige los riesgos del flujo actual:
- El worker puede ejecutarse en varios procesos.
- La selección de reglas vencidas necesita exclusión distribuida.
- WHERE NOT EXISTS no evita duplicados bajo concurrencia.
- El fallo de una regla no debe impedir procesar las restantes.
- Un código de regla desconocido debe rechazarse explícitamente.

Implementa reclamación atómica de ejecuciones, restricciones de unicidad,
idempotencia, reintentos limitados y recuperación de ejecuciones abandonadas.

No mantengas transacciones ni bloqueos abiertos durante llamadas al modelo.
Evita compartir conexiones entre hilos y revisa los commits internos
de los servicios que se reutilicen.

Si falla la IA, registra el modo degradado y conserva los análisis
deterministas útiles; no presentes una respuesta fija como decisión de IA.

Trata los textos externos como datos, nunca como instrucciones operativas.

8. MEMORIA Y EVALUACIÓN DE RESULTADOS

Persiste observaciones, propuestas, decisiones, aprobaciones, acciones
y resultados medidos con trazabilidad entre ellos.

Revisa después de un plazo configurable:
- Rotación y cobertura.
- Roturas de stock.
- Unidades vendidas y devoluciones.
- Margen realizado.
- Coste de traslado o promoción.
- Capital inmovilizado.
- Precisión y sesgo de previsiones.

Compara previsiones con resultados. No atribuyas una mejora a una acción
sin evidencia suficiente ni permitas que el agente amplíe sus permisos
o modifique límites de negocio por sí mismo.

La previsión actual usa una media histórica y su tendencia toma segmentos
de filas con ventas. Revisa ventanas por fechas reales y tratamiento de
días sin registros, sin asumir que datos ausentes equivalen a ventas cero.

9. API E INTERFAZ

Amplía los contratos existentes para:
- Configurar reglas, objetivos, modos y límites.
- Consultar evidencias y alternativas.
- Aprobar o rechazar propuestas con motivo.
- Ejecutar acciones autorizadas.
- Consultar resultados, errores y modo degradado.

Si existe interfaz para estas funciones, intégralas manteniendo
compatibilidad. Evita crear pantallas desconectadas del flujo real.

10. VALIDACIÓN Y ENTREGA

Añade pruebas relevantes para:
- Reposición con reservas y compras pendientes.
- Traslado desde excedente a demanda.
- Stock estancado sin demanda en ningún almacén.
- Falta de costes o historial suficiente.
- Restricciones de presupuesto, margen y permisos.
- Respuesta inválida o caída del modelo.
- Duplicados, concurrencia y reintentos.
- Aprobación de propuestas con datos caducados.
- Conservación del inventario y coherencia de movimientos.
- Rechazo de reglas y herramientas desconocidas.

Usa dobles del proveedor de IA en pruebas; no dependas de llamadas
pagadas para verificar comportamiento.

Entrega código, migraciones siguiendo el patrón del proyecto,
configuración documentada y pruebas ejecutadas.

Incluye un ejemplo reproducible de extremo a extremo:
detección → comparación → propuesta → aprobación o ejecución autorizada
→ registro → evaluación posterior.

Señala qué funciona con los datos actuales y qué necesita datos o
integraciones adicionales. No declares terminadas capacidades simuladas.

11. PÁGINA NUEVA: CENTRO DE CONTROL DE AGENTES

Desarrolla una página integrada en el frontend existente, accesible desde
la navegación principal, para entender qué hacen los agentes, por qué
actúan y qué resultados obtienen.

Inspecciona primero el framework, componentes, autenticación y estilos
del proyecto. Reutilízalos y conecta la interfaz con datos reales del
backend. No entregues una maqueta con métricas inventadas.

VISTA GENERAL

Muestra:
- Agentes disponibles y responsabilidad de cada uno.
- Estado: inactivo, programado, analizando, esperando aprobación,
  ejecutando, completado, degradado o error.
- Modo de autonomía y reglas activas.
- Última ejecución, próxima ejecución y duración.
- Propuestas pendientes y acciones ejecutadas.
- Alertas que requieren intervención.
- Disponibilidad del proveedor de IA.

Distingue agentes reales, servicios auxiliares y reglas programadas.
No representes cada regla como un agente independiente si no lo es.

ACTIVIDAD Y FUNCIONAMIENTO

Incluye un diagrama del flujo:
observación → análisis → herramientas → propuesta → validación
→ aprobación o ejecución → evaluación.

Destaca el paso actual a partir de eventos reales.

Añade una línea temporal por ejecución con:
- Agente, regla, producto y almacén.
- Datos consultados y fecha de actualización.
- Herramientas utilizadas y resultado resumido.
- Alternativas consideradas y motivo de la decisión.
- Validaciones superadas o rechazadas.
- Aprobación, ejecución y resultado posterior.
- Errores, reintentos y uso de respuestas de respaldo.

Permite filtrar por fecha, agente, regla, estado, producto y almacén.
Desde cada actividad debe poder abrirse su propuesta y su trazabilidad.

Actualiza la actividad mediante el mecanismo adecuado para la arquitectura
existente: SSE, WebSocket o sondeo controlado. Incluye estados de conexión,
carga, vacío y error. No simules progreso que el backend no pueda observar.

12. MÉTRICAS Y FIABILIDAD DE LOS AGENTES

Dentro del centro de control, incorpora una vista de métricas con filtros
por agente, regla, periodo y versión de modelo o configuración.

MÉTRICAS OPERATIVAS

Instrumenta y muestra:
- Número de ejecuciones y tareas evaluables.
- Tasa de éxito técnico.
- Tasa de cumplimiento del objetivo, cuando exista evaluación verificable.
- Latencia mediana y percentil 95.
- Llamadas a herramientas y tasa de errores.
- Respuestas del modelo que cumplen el esquema.
- Reintentos, ejecuciones degradadas y fallos del proveedor.
- Consumo de tokens y coste, cuando el proveedor los facilite.
- Coste por tarea completada.
- Propuestas aprobadas, rechazadas, modificadas y pendientes.
- Acciones revertidas y correcciones humanas.
- Intentos de acción bloqueados por políticas y violaciones efectivas.

Distingue éxito técnico de calidad de decisión: completar una ejecución
no demuestra que la recomendación fuera acertada.

MÉTRICAS DE CALIDAD Y RESULTADO

Para previsiones, muestra MAE, WAPE y sesgo cuando haya datos suficientes.
Gestiona denominadores cero y explica las limitaciones de cada métrica.

Para decisiones, registra:
- Cumplimiento de restricciones de negocio.
- Validez de los datos y evidencias utilizadas.
- Resultado observado frente al objetivo declarado.
- Beneficio neto observado cuando pueda calcularse con costes reales.
- Frecuencia y motivo de intervención humana.

Las métricas de negocio deben incluir roturas de stock, cobertura,
rotación, margen y capital inmovilizado, con su periodo y referencia
de comparación.

No presentes la aprobación humana como prueba de acierto ni atribuyas
causalidad a una comparación antes/después sin una evaluación adecuada.

FIABILIDAD DE LAS DECISIONES

Separa claramente:
a) Calidad y actualidad de los datos.
b) Incertidumbre de la estimación.
c) Cumplimiento de políticas.
d) Fiabilidad histórica en decisiones ya evaluadas.

No utilices la confianza declarada por el modelo como probabilidad
de acierto.

Muestra la fiabilidad histórica por tipo de decisión y horizonte,
acompañada de:
- Definición explícita de “decisión acertada”.
- Número de decisiones evaluadas.
- Periodo, cobertura y método de evaluación.
- Resultados pendientes, excluidos y no evaluables.
- Intervalos de incertidumbre cuando el método los permita.
- Versión del agente, modelo y reglas.

Si no existe muestra suficiente, muestra “Evidencia insuficiente”.
No asignes porcentajes ficticios ni un 100 % por ausencia de errores.

Si se utiliza una puntuación agregada, documenta sus componentes,
ponderaciones y limitaciones. Permite consultar las métricas originales.
No mezcles decisiones de reposición, traslados y promociones en una
única tasa de acierto sin mostrar su desglose.

Para probabilidades de éxito, implementa primero una evaluación de
calibración sobre resultados históricos suficientes; si no existe,
presenta indicadores descriptivos, sin llamarlos probabilidades.

VISUALIZACIÓN

Incluye:
- Tarjetas de indicadores con tendencia y tamaño de muestra.
- Gráficos temporales de errores, latencia, coste y resultados.
- Comparación de previsión y resultado real.
- Tabla de decisiones con resultado esperado, observado y evaluación.
- Explicaciones accesibles de fórmulas, unidades y denominadores.

Permite abrir desde cada métrica las ejecuciones que la originan.
Los valores no disponibles deben mostrarse como tales, nunca como cero.

13. PÁGINA NUEVA: EDITOR DE REGLAS

Desarrolla una página para crear, editar, validar, simular, activar,
desactivar y versionar reglas sin modificar código.

Usa formularios comprensibles para usuarios de negocio. No expongas
SQL, código ejecutable ni prompts sin restricciones como editor de reglas.

CAMPOS CONFIGURABLES

Incluye, según el tipo de regla:
- Nombre, descripción y objetivo.
- Tipo de regla y agente responsable.
- Productos, categorías y almacenes afectados.
- Frecuencia, zona horaria y ventana de ejecución.
- Condiciones y umbrales, con unidades explícitas.
- Días sin ventas y cobertura máxima para stock estancado.
- Cobertura objetivo y stock de seguridad para reposición.
- Acciones permitidas y alternativas que deben evaluarse.
- Modo de autonomía.
- Presupuesto por acción y periodo.
- Margen mínimo y cobertura mínima del almacén de origen.
- Requisitos de aprobación.
- Caducidad, enfriamiento entre acciones y límites de ejecución.
- Métrica objetivo y plazo de revisión.

Permite grupos de condiciones “todas” y “cualquiera” mediante un esquema
declarativo tipado, limitado a campos y operadores permitidos.

VALIDACIÓN Y SIMULACIÓN

Valida en frontend y backend:
- Rangos, unidades, referencias y campos obligatorios.
- Condiciones contradictorias.
- Acciones incompatibles con el modo de autonomía.
- Frecuencias o límites excesivos.
- Solapamientos con otras reglas y posibles acciones contradictorias.

Antes de activar una versión, permite simularla sobre una instantánea
de datos e indicar:
- Entidades afectadas.
- Propuestas que generaría.
- Acciones autorizadas y bloqueadas.
- Datos ausentes y supuestos.
- Coste estimado, solo cuando sea calculable.

La simulación no debe crear pedidos, movimientos, campañas ni reservas.
Identifica la fecha de los datos utilizados y aclara que una simulación
no garantiza el comportamiento futuro.

VERSIONADO Y PERMISOS

Mantén borradores y versiones publicadas con:
- Autor, fecha y motivo del cambio.
- Diferencias entre versiones.
- Historial de activaciones y desactivaciones.
- Restauración de una versión anterior como nueva versión.

Cada ejecución debe quedar vinculada a la versión exacta de la regla.
Editar una regla no debe cambiar silenciosamente una ejecución en curso.

Aplica permisos del lado del servidor para consultar, editar, activar,
aprobar y ejecutar. Ampliar la autonomía requiere autorización explícita;
guardar un borrador no concede permisos operativos.

Define qué sucede con propuestas pendientes al cambiar una regla:
revalidarlas, invalidarlas o mantenerlas bajo condiciones documentadas.
Revalida siempre las políticas vigentes antes de ejecutar.

14. ENTREGA Y PRUEBAS DE LAS PÁGINAS

Entrega ambas páginas conectadas con API y persistencia reales,
incluyendo navegación, migraciones y documentación.

Añade pruebas relevantes para:
- Visualización de una ejecución y su evolución de estado.
- Correspondencia entre métricas y eventos persistidos.
- Datos insuficientes y denominadores cero.
- Creación, edición, simulación y activación de reglas.
- Versionado y edición concurrente.
- Restricciones de permisos.
- Garantía de ausencia de efectos operativos en simulación.
- Cambio de reglas con propuestas pendientes.

Verifica navegación por teclado, etiquetas de formularios, contraste,
diseño adaptable y estados de carga, vacío, error y desconexión.
No comuniques estados únicamente mediante colores.

Incluye una demostración reproducible:
crear regla → simular → activar → observar ejecución → revisar propuesta
→ aprobar una acción autorizada → consultar su evaluación posterior.

Cualquier dato de demostración debe estar identificado y separado
de los indicadores reales.