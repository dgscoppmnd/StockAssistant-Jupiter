# Implementación e integración de asistentes especializados

Este documento describe la contribución relativa a los asistentes de **Compras, Clientes, Ventas, Tendencias y Marketing**, su integración con el Ejecutivo y las pruebas utilizadas para comprobar su funcionamiento. Reúne el alcance funcional, las decisiones técnicas y las evidencias disponibles para facilitar su revisión y demostración.

La implementación utiliza los servicios compartidos del proyecto: PostgreSQL, el servicio de IA, los conectores externos, el Ejecutivo y la interfaz web. La contribución comprende funcionalidades e integración sobre esa estructura, incluyendo el servicio específico de oportunidades de Marketing. El desarrollo global de la infraestructura AWS, el asistente documental RAG y las automatizaciones operativas se documenta en sus respectivos apartados del proyecto.

**Estado de las evidencias:** las funcionalidades descritas se integraron en el repositorio y se comprobaron en entornos locales. Las pruebas locales no acreditan por sí mismas su funcionamiento en una versión concreta desplegada en AWS. Los resultados numéricos recogidos aquí corresponden a ejecuciones documentadas, no a una medición continua de la última versión.

## Contenido

1. [Arquitectura e integración con el Ejecutivo](#arquitectura-e-integración-con-el-ejecutivo)
2. [Asistente de Compras](#asistente-de-compras)
3. [Asistente de Clientes](#asistente-de-clientes)
4. [Asistente de Ventas](#asistente-de-ventas)
5. [Asistente de Tendencias](#asistente-de-tendencias)
6. [Asistente de Marketing](#asistente-de-marketing)
7. [Validación y escenarios sintéticos](#validación-y-escenarios-sintéticos)
8. [Resultados y límites](#resultados-y-límites)
9. [Capturas de pantalla](#capturas-de-pantalla)
10. [Referencias de implementación](#referencias-de-implementación)

## Arquitectura e integración con el Ejecutivo

Un asistente especializado es un componente que combina una función, datos o herramientas y, cuando corresponde, instrucciones para un modelo de lenguaje. No implica disponer de un LLM entrenado independientemente para cada tarea.

El Ejecutivo recibe la pregunta y los identificadores seleccionados en la interfaz. Las reglas de la aplicación eligen el servicio especializado y registran la consulta y su resultado. En el flujo documentado, la selección se realiza mediante reglas de palabras clave; no se delega al modelo de lenguaje la elección libre de herramientas.

El recorrido común comprende:

1. El usuario escribe una consulta y selecciona un producto o cliente si la función lo requiere.
2. El Ejecutivo determina la ruta y llama al servicio correspondiente.
3. El servicio recupera los datos y calcula las cantidades o métricas mediante código.
4. Cuando procede, un modelo de lenguaje elabora una explicación o propuesta a partir de la evidencia recibida.
5. La interfaz presenta el resultado y permite consultar sus detalles técnicos.
6. La decisión y el resultado se guardan para su trazabilidad.

| Asistente | Ruta identificada en el resultado | Entrada principal | Evidencia utilizada |
|---|---|---|---|
| Compras | `purchasing` | Producto seleccionado. | Inventario y parámetros de reposición; ofertas externas cuando están disponibles. |
| Clientes | `clients` | Cliente seleccionado o identificador en la petición. | Datos maestros del cliente en PostgreSQL. |
| Ventas | `sales_forecast` | Producto seleccionado; horizonte en la API específica. | Movimientos de inventario de tipo despacho. |
| Tendencias | `market_intelligence` | Término de producto o categoría. | Google Trends mediante SerpAPI. |
| Marketing | `marketing` | Solicitud de oportunidades; no requiere producto seleccionado. | Crecimiento de despachos, stock y evidencia externa. |

El acceso común documentado es **Resumen → Compras y automatizaciones → Consulta ejecutiva**, con el botón **Consultar al Ejecutivo**. La tarjeta puede mostrarse con el título «Enrutamiento trazable». Estos nombres corresponden a la interfaz revisada y pueden variar con posteriores cambios del menú.

La política de estas consultas permite consultar y recomendar, sin ejecutar por sí mismas compras, movimientos de stock ni campañas. La escritura de auditoría o de caché externa forma parte de su funcionamiento técnico. Las automatizaciones y las operaciones comerciales con aprobación son flujos diferentes.

La organización de las reglas puede afectar a consultas que mezclan varias intenciones. Las preguntas de prueba siguientes mantienen una intención principal para comprobar cada asistente de manera reproducible.

## Asistente de Compras

### Función y funcionamiento

El asistente reúne el stock disponible del producto —existencias físicas menos reservas—, su punto de reposición, la cantidad de reposición configurada y la unidad base. La recomendación se calcula con esos parámetros. El modelo de lenguaje recibe el resultado para explicarlo, en lugar de inventar las cantidades.

Si SerpAPI está configurada, puede consultar ofertas mediante Google Shopping e incorporar precios y referencias externas. La consulta externa no equivale a conectar con el sistema comercial del proveedor ni a confirmar una compra. Si no hay ofertas disponibles, la respuesta debe reflejar esa limitación.

La consulta requiere que el producto disponga de la configuración y existencias necesarias para elaborar la recomendación. Una recomendación no crea un pedido definitivo ni incrementa el stock; tampoco demuestra por sí sola que se deba comprar en ese momento.

### Consulta de prueba

**Pregunta:** ¿Cuánto debería comprar de este producto y por qué?

**Pasos:** acceder a la consulta del Ejecutivo, seleccionar un producto, escribir la pregunta y pulsar **Consultar al Ejecutivo**.

**Comprobación documentada:** con 5 unidades disponibles, punto de reposición de 10 y cantidad de reposición configurada de 20, se comprobó una recomendación de 20 unidades basada en los parámetros de inventario. Esa cantidad corresponde a ese caso; no es la respuesta esperada para cualquier producto.

**Límites:** las ofertas no garantizan disponibilidad comercial, precio final o condiciones de entrega. El usuario debe revisar la recomendación antes de una operación de compra.

<!-- CAPTURA COMPRAS: añadir aquí ![Recomendación de Compras](capturas/compras.png) -->

## Asistente de Clientes

### Función y funcionamiento

El asistente recibe el identificador interno del cliente y consulta sus datos maestros en PostgreSQL: ID, código, nombre e identificador de tipo. Los datos recuperados se proporcionan al componente de respuesta del asistente para contextualizar la consulta.

Si no se proporciona identificador, solicita el dato necesario. Si no encuentra el registro, informa de ello. Estas dos respuestas no requieren generar una explicación con el modelo. Cuando existe un cliente, las instrucciones delimitan la respuesta a la información realmente consultada.

Este flujo no revisa tickets, facturas, pagos ni devoluciones. Que existan esos módulos en el sistema no significa que sus datos formen parte de la consulta del asistente de Clientes.

### Consulta de prueba

**Pregunta:** ¿Qué datos básicos están registrados para este cliente?

**Pasos:** acceder a la consulta del Ejecutivo, buscar y seleccionar un cliente existente en el selector, escribir la pregunta y pulsar **Consultar al Ejecutivo**. El selector envía su identificador interno. En las interfaces anteriores que muestran un campo ID, se introduce allí ese identificador; no basta con escribirlo dentro de la pregunta.

**Comprobaciones:** cliente existente, ausencia de identificador y registro inexistente. Para comprobar el último caso debe utilizarse un ID cuya ausencia se haya verificado; no asumir que un número concreto está libre en cualquier base.

<!-- CAPTURA CLIENTES: añadir aquí ![Consulta de datos maestros del cliente](capturas/clientes.png) -->

## Asistente de Ventas

### Datos y objetivo de la previsión

El asistente estima unidades despachadas a partir de los movimientos de inventario `dispatch` del producto. Se diferencia ese objetivo de la demanda potencial: un producto sin stock puede tener demanda sin registrar despachos, y un historial incompleto puede omitir operaciones.

La implementación inicial aplicaba únicamente la media histórica de 90 días. La versión integrada añade la comparación de cuatro métodos estadísticos y conserva la fórmula heredada como respaldo cuando no hay condiciones suficientes para la selección temporal.

| Método | Funcionamiento |
|---|---|
| Media de 90 días | Multiplica el promedio diario de los 90 días anteriores por el horizonte solicitado. |
| Media de 30 días | Proyecta el promedio diario de los 30 días más recientes. |
| Repetición semanal | Repite la secuencia de los últimos siete días durante el horizonte. |
| Tendencia lineal de 90 días | Ajusta una recta por mínimos cuadrados y proyecta valores diarios, limitando a cero los negativos. |

### Comparación y selección del método

Se comparan hasta cinco ventanas históricas no solapadas del tamaño del horizonte solicitado. En cada ventana, cada método recibe exclusivamente los 90 días anteriores; su previsión se contrasta con los despachos registrados después. Se calcula el error absoluto medio, o MAE, y se selecciona el método de menor error, con un orden estable de desempate.

Para activar esa selección se requieren al menos 30 días con despachos positivos, 90 días iniciales y tres ventanas completas de validación. Los candidatos se utilizan con horizontes de hasta 90 días. La herramienta admite horizontes de hasta 365 días en su API específica, pero los superiores a 90 conservan el respaldo. El Ejecutivo revisado utiliza un horizonte de 30 días; no interpreta de forma general cualquier número de días escrito en la pregunta.

El histórico consultado se limita a 540 días. La selección utiliza días completos UTC y excluye el día en curso. Las fechas sin movimientos se representan como cero despachos registrados, sin afirmar que la demanda haya sido cero. El MAE sirve para seleccionar el método con evidencia histórica: no es una garantía de precisión futura ni un intervalo de confianza.

La respuesta técnica identifica el método en `forecast_method`, el resultado en `forecast_qty` y la comparación en `forecast_validation`. El resumen descriptivo de la ventana heredada no debe confundirse con la media futura del método seleccionado.

### Papel de la IA

El backend calcula la previsión. El LLM recibe las cifras, el método, su evaluación y los límites de la evidencia para generar una explicación en español. No se entrena un modelo de lenguaje con las ventas. Tampoco se utiliza ML Factory para este cálculo: la previsión integrada es estadística y la explicación es generativa.

Si falla el proveedor de IA, se conserva la previsión numérica y se informa de que no pudo ampliarse el análisis. Una estimación fraccionaria no constituye una orden de compra.

### Consulta de prueba

**Pregunta:** Calcula la previsión de ventas de este producto para los próximos 30 días y explica el método utilizado y sus limitaciones.

**Pasos:** acceder a la consulta del Ejecutivo, seleccionar un producto con histórico de despachos, escribir la pregunta y consultar. Comprobar la ruta `sales_forecast`, la cifra, el método, las métricas disponibles y la explicación.

Los productos S01–S06 del sandbox permiten comprobar patrones y límites diferentes. No debe exigirse una cifra o método fijo en cualquier fecha: los datos originales no se actualizan automáticamente con nuevos despachos.

La descripción detallada y los resultados numéricos sintéticos están en [Selección temporal del predictor](../../BackEnd/apps/MonoliticDataStructure/app/docs/sales-forecast-validation.md).

<!-- CAPTURA VENTAS: añadir aquí ![Previsión de Ventas y método seleccionado](capturas/ventas.png) -->

## Asistente de Tendencias

### Consulta externa y métricas

El servicio consulta Google Trends mediante SerpAPI para un término de producto o categoría. En las pruebas se utilizó España y el periodo de los últimos doce meses. Puede consultar un término que no exista en el catálogo interno.

Se obtienen la serie temporal y las consultas relacionadas mediante peticiones diferenciadas. La serie se normaliza al índice relativo de 0 a 100, se ordena y deduplica, y se descartan observaciones no válidas o marcadas como parciales. El valor cero es válido.

Se infiere la duración de los intervalos a partir de sus marcas temporales. Se comparan los últimos cuatro intervalos terminados con los cuatro anteriores, si son consecutivos. Se calculan sus medias, la diferencia en puntos, los extremos históricos y las fechas de los máximos. El intervalo en curso puede aparecer en el gráfico sin participar en la comparación.

La IA recibe la serie y la evidencia calculada para explicar lo observado y sugerir comprobaciones. Un pico cercano a Navidad no demuestra que esa fecha sea su causa ni que el patrón se repita cada año. El interés de búsqueda tampoco mide ventas o volumen absoluto de búsquedas.

### Interfaz y respuesta ante fallos

La tarjeta presenta gráfico, tabla de valores desplegable, consultas relacionadas, explicación y detalles técnicos. Durante la carga muestra **Consultando…** y bloquea envíos duplicados.

- `ok`: existen observaciones válidas; la IA o las consultas relacionadas pueden no estar disponibles.
- `no_data`: no hay observaciones válidas; no se inventa una serie ni se llama a la IA.
- `source_unavailable`: falta configuración o falla la fuente externa.
- `needs_clarification`: el Ejecutivo necesita un término concreto o una petición menos ambigua.

Si hay serie pero falla la IA, se conserva un resumen calculado. Si falla la consulta de relacionadas, aún puede mostrarse la serie temporal recibida.

### Consulta de prueba

**Pregunta al Ejecutivo:** Analiza las tendencias de "auriculares inalámbricos".

**Pasos:** escribir la pregunta sin seleccionar producto ni cliente y pulsar **Consultar al Ejecutivo**. Comprobar la ruta `market_intelligence`.

**Acceso desde la tarjeta:** Resumen → Alertas, análisis y agentes de compras → tarjeta de Tendencias. Introducir `auriculares inalámbricos` y pulsar **Consultar SerpAPI Trends**.

También se comprobó la interpretación de preguntas sin comillas y con una comilla de apertura sin cierre. Una petición sin término concreto solicita aclaración.

En una ejecución local documentada se recibieron 53 observaciones y una comparación de 45 a 49,5 puntos, diferencia de 4,5. Se obtuvo análisis con OpenAI desde la tarjeta y desde el Ejecutivo. Son resultados fechados, no valores de referencia permanentes de Google Trends.

Más detalle: [Análisis de Tendencias](../../BackEnd/apps/MonoliticDataStructure/app/docs/market-trends-analysis.md).

<!-- CAPTURA TENDENCIAS: añadir aquí ![Gráfico y análisis de Tendencias](capturas/tendencias.png) -->

## Asistente de Marketing

### Selección automática de candidatos

El servicio busca hasta tres oportunidades sin que el usuario seleccione un producto. Compara los últimos 30 días completos UTC con los 30 anteriores usando despachos de cantidad firmada negativa. Cada candidato debe cumplir todos estos mínimos:

- Diez unidades recientes y cinco anteriores.
- Crecimiento entre ambos periodos.
- Despachos recientes en al menos tres días distintos.
- Stock disponible mayor que cero, descontando las reservas.

Se prioriza el aumento absoluto de unidades, después el porcentaje y finalmente el ID. El cálculo es determinista. La lista puede contener menos de tres candidatos y no se completa artificialmente. Si no hay candidatos, devuelve `no_candidates` y no consume consultas de Trends ni peticiones de propuestas a la IA.

Este filtro identifica crecimiento interno; no descubre por sí solo productos que únicamente estén de moda en el mercado ni productos nuevos sin la base anterior requerida. El ranking por unidades tampoco equivale a una optimización económica entre productos con distintos precios o unidades de medida.

### Contraste externo y generación de propuestas

Cada candidato utiliza su nombre como término de Google Trends y reutiliza el servicio de Tendencias sin generar un análisis de IA separado por cada serie. La evidencia interna y externa se entrega en una petición inicial de Marketing para redactar los borradores de todos los candidatos.

Cada propuesta incluye **objetivo, hipótesis de público, canal, mensaje y motivo**. Se comprueban los IDs y canales admitidos, la estructura y restricciones básicas del mensaje, como descuentos, importes o superlativos no autorizados. El prompt prohíbe inventar prestaciones y exige ignorar consultas externas no relacionadas. Estas comprobaciones no sustituyen la revisión humana de todo el contenido.

Si se rechaza formato o contenido, se permite un único intento correctivo. Los detalles `ai_attempts` registran aceptación, rechazo o error de proveedor. Si no se consigue una respuesta válida, se mantienen plantillas identificadas como tales. Un fallo de SerpAPI puede dejar una propuesta basada solo en crecimiento interno, sin afirmar que exista interés externo demostrado.

Se distingue `campaign_origin: ai` de `campaign_origin: template`. Las propuestas quedan en `draft_requires_review`. No se publican campañas, envían correos, aplican descuentos ni reservan existencias. El stock es una instantánea y debe revisarse junto con el margen y la adecuación del público.

### Consulta de prueba

**Pregunta al Ejecutivo:** Busca oportunidades de marketing.

**Pasos:** escribirla sin seleccionar producto ni cliente y pulsar **Consultar al Ejecutivo**. Comprobar la ruta `marketing`.

**Acceso directo:** Resumen → Análisis de Marketing → **Buscar oportunidades de Marketing**. La página propia utiliza el mismo servicio que el Ejecutivo; durante la espera muestra **Analizando…**.

El caso positivo documentado usa «auriculares inalámbricos» con despachos simulados de 30 a 60 unidades y stock de 500. Se comprobó una propuesta de IA aceptada con OpenAI y otra respuesta de plantilla, diferenciadas en la interfaz. En el principal se comprobó también la respuesta sin candidatos. Esta última no significa que el usuario deba seleccionar un producto.

Más detalle: [Asistente de Marketing](../../BackEnd/apps/MonoliticDataStructure/app/docs/marketing-opportunities.md).

<!-- CAPTURA MARKETING: añadir aquí ![Oportunidad de Marketing y borrador de IA](capturas/marketing.png) -->

## Validación y escenarios sintéticos

### Entornos utilizados

| Entorno local documentado | Acceso habitual a GUI | Uso |
|---|---|---|
| Principal | `http://localhost:8080/` | Comprobar la integración de la versión actualizada y las consultas disponibles. |
| Sandbox | `http://localhost:5174/` | Pruebas aisladas con los escenarios simulados de Ventas y Marketing. |

El puerto 5173 da acceso directo al frontend principal; no constituye un tercer entorno. El sandbox utiliza su propia base `jupiter_sales_sandbox` y mantiene desactivado el trabajador de automatizaciones. Los puertos y nombres identifican las instalaciones locales utilizadas, no direcciones de AWS ni requisitos fijos para todos los desarrolladores.

### Histórico controlado

Se prepararon seis escenarios de 240 días para comprobar el comportamiento numérico y los casos de evidencia insuficiente:

| Producto | Despachos generados | Comportamiento que se comprueba |
|---|---|---|
| S01 | Tres unidades cada día. | Estabilidad. |
| S02 | Una unidad diaria inicial, aumentando una cada 20 días. | Crecimiento progresivo. |
| S03 | Doce unidades diarias iniciales, disminuyendo una cada 20 días hasta un mínimo de una. | Descenso y límites de la extrapolación. |
| S04 | Seis unidades los sábados, cuatro los domingos y cero entre semana. | Patrón semanal. |
| S05 | Sin despachos, con stock. | Ausencia de evidencia de ventas. |
| S06 | Una única unidad despachada al final del historial. | Historial insuficiente. |

Se añadió un séptimo producto para Marketing con 30 unidades en el periodo anterior, 60 en el reciente y despachos recientes en diez días. Todos los productos conservan un saldo de 500 unidades sin reservas, con entradas iniciales que cubren los despachos.

El evaluador numérico utiliza ventanas posteriores excluidas del cálculo de cada previsión. Para la evaluación sintética se generó además una continuación artificial de 30 días fuera de la base, no utilizada para seleccionar el método. En la evaluación fijada a la fecha original se seleccionaron la media de 90 días para el caso constante, la recta para crecimiento y descenso y la repetición semanal para el patrón semanal. Los escenarios escasos se comprobaron mediante las condiciones de respaldo del servicio integrado.

Las pruebas numéricas no llaman a OpenAI; las comprobaciones de la GUI y de las explicaciones se realizaron por separado. Los escenarios permiten detectar errores y limitaciones, pero no demuestran precisión sobre operaciones comerciales reales.

### Casos funcionales

| Área | Caso | Resultado comprobado |
|---|---|---|
| Compras | Stock 5, punto 10 y cantidad configurada 20. | Recomendación de 20 unidades basada en inventario. |
| Clientes | Registro existente, ausente e inexistente. | Datos maestros o solicitud/corrección del identificador. |
| Ventas | Patrones y evidencia escasa. | Método y cifra identificados, explicación y respaldo cuando corresponde. |
| Ventas | Fallo de IA simulado. | Conservación de la cifra calculada y aviso. |
| Tendencias | Consulta real y variantes con comillas. | Datos externos, análisis y extracción del término. |
| Tendencias | Fuente o IA no disponible. | Estado explícito y resumen calculado cuando hay serie. |
| Marketing | Sin candidatos. | Lista vacía sin generación de propuestas. |
| Marketing | Candidato con crecimiento y stock. | Contraste externo y propuesta de IA pendiente de revisión. |
| Marketing | Respuesta de IA rechazada o proveedor no disponible. | Evidencia conservada y borrador de plantilla identificado. |

### Resultados de pruebas registrados

| Ejecución documentada | Resultado |
|---|---|
| Suite completa tras Tendencias | 242 superadas y 22 omitidas. |
| Regresión dirigida tras el ajuste de Marketing | 107 superadas. |
| Suite completa tras Marketing | 307 superadas, 37 omitidas y 13 advertencias. |
| Frontend de las entregas | `npm run build` y `npx tsc --noEmit` finalizaron sin errores. |

Los recuentos corresponden a versiones y selecciones de pruebas diferentes; no se suman. La suite completa incluye pruebas de otros componentes del proyecto y no debe denominarse exclusivamente unitaria. Las pruebas omitidas no se consideran superadas. El aviso de tamaño de bundle de Vite no impidió compilar.

Para repetir una selección de pruebas sin confundirla con el recuento histórico, desde la raíz del proyecto y con la dependencia de desarrollo instalada en el entorno del backend:

```powershell
Push-Location .\BackEnd\apps\MonoliticDataStructure\app
.\.venv\Scripts\python.exe -c "import sys, pytest; sys.path[:0]=['src','.']; raise SystemExit(pytest.main(['tests/test_executive_rules.py','tests/test_sales_forecasting.py','tests/test_sales_forecast_ai.py','tests/test_sales_forecast_weekly.py','tests/test_market_trends.py','tests/test_marketing_opportunities.py','tests/test_external_connectors.py','-q']))"
Pop-Location
```

La ejecución de la suite completa con pruebas de base de datos requiere la configuración del entorno de prueba correspondiente. Las comprobaciones con proveedores reales dependen de sus credenciales y pueden consumir cuota.

### Datos para demostraciones compartidas

Se preparó y compartió un archivo de carga con siete productos, dos almacenes, configuraciones, saldos y 816 movimientos: siete entradas y 809 despachos. La adaptación resuelve los IDs del destino, comprueba saldos y detiene la carga si detecta identificadores del lote ya existentes.

Su SQL se mantiene como material técnico separado. Fue probado en PostgreSQL embebido con un esquema representativo; no se ha confirmado aquí su ejecución en AWS. Conserva las fechas originales y no contiene clientes, pedidos, facturas ni devoluciones. Su propósito es facilitar estos escenarios de Ventas y Marketing y el inventario asociado, no completar todos los módulos comerciales.

## Resultados y límites

La contribución integra consultas a datos internos, previsión estadística, información externa y generación de explicaciones o propuestas. Los cálculos y filtros de negocio se mantienen en código y los resultados muestran su procedencia y las limitaciones aplicables.

- **Demanda y despachos:** las previsiones y el crecimiento se basan en movimientos registrados; no acreditan demanda sin restricciones de stock.
- **Interés externo:** Google Trends describe búsquedas relativas y no prueba ventas, estacionalidad, causas o rentabilidad.
- **Calidad generativa:** las validaciones reducen errores concretos, pero no garantizan la corrección de todo el texto ni resultados comerciales de una campaña.
- **Enrutamiento:** la elección por reglas puede necesitar aclaraciones o ajustes cuando se mezclan intenciones; no equivale a comprensión general ilimitada.
- **Datos y fechas:** el histórico simulado tiene fechas fijas; los resultados pueden cambiar con el día de consulta.
- **Disponibilidad:** cada función necesita datos, permisos y, cuando corresponde, proveedores configurados. Los respaldos disponibles se describen por asistente, sin asumir que todos gestionen cualquier fallo igual.
- **Alcance de la evidencia:** pruebas locales, código integrado y despliegue AWS son evidencias distintas; no se presenta una como demostración automática de las otras.

El proyecto también contiene RAG documental y ML Factory. El cálculo de Ventas descrito no utiliza RAG ni modelos XGBoost de ML Factory. Estos componentes tienen flujos y objetivos distintos y su existencia no debe confundirse con el método de previsión realmente seleccionado.

## Capturas de pantalla

Las imágenes se incorporan por separado a `capturas/`. No se incluyen capturas inventadas ni se presenta como prueba una pantalla que aún no se ha adjuntado. Los marcadores de cada asistente están comentados para evitar imágenes rotas hasta añadir los archivos.

| Nombre recomendado | Contenido que debe quedar legible |
|---|---|
| `compras.png` | Producto y recomendación con su evidencia. |
| `clientes.png` | Respuesta de datos maestros; usar un cliente de prueba. |
| `ventas.png` | Producto, previsión, método y explicación. |
| `tendencias.png` | Término, gráfico y análisis de IA. |
| `marketing.png` | Métricas internas y propuesta identificada como IA o plantilla. |

Cuando se añada una imagen, sustituir su marcador comentado por el enlace Markdown. Ejemplo:

```markdown
![Oportunidad de Marketing y borrador de IA](capturas/marketing.png)
```

Si una captura no basta, utilizar nombres como `marketing-01.png` y `marketing-02.png`, con un pie específico para cada una. Mostrar solo lo necesario para acreditar el resultado; mantener los detalles técnicos cerrados cuando dificulten la lectura y evitar claves, tokens o datos personales reales.

Cada evidencia debe identificar entorno, fecha y caso utilizado, y si los datos internos son simulados. Las cifras de los casos deben describir la ejecución mostrada. Para Marketing, diferenciar claramente datos internos simulados, evidencia externa y propuesta generativa.

## Referencias de implementación

### Servicios y contratos

- [Agente Ejecutivo](../../BackEnd/apps/MonoliticDataStructure/app/src/executive_service.py): selección de herramienta, llamada al servicio y auditoría.
- [Servicios de Compras y Clientes](../../BackEnd/apps/MonoliticDataStructure/app/src/agent_service.py): consulta de maestros, inventario y recomendación.
- [Servicio comercial](../../BackEnd/apps/MonoliticDataStructure/app/src/commercial_agent_service.py): previsión y análisis de Tendencias.
- [Métodos de previsión](../../BackEnd/apps/MonoliticDataStructure/app/src/sales_forecasting.py): candidatos y validación temporal.
- [Tratamiento de Tendencias](../../BackEnd/apps/MonoliticDataStructure/app/src/market_trends.py): normalización, comparación y extracción del término.
- [Servicio de Marketing](../../BackEnd/apps/MonoliticDataStructure/app/src/marketing_service.py): selección, evidencia, propuestas y validación.
- [Conectores externos](../../BackEnd/apps/MonoliticDataStructure/app/src/external_connectors.py) y [servicio de IA](../../BackEnd/apps/MonoliticDataStructure/app/src/ai_service.py).
- [Endpoints comerciales](../../BackEnd/apps/MonoliticDataStructure/app/src/endpoints/endpointsCommercialAgents.py) y [endpoints del Ejecutivo](../../BackEnd/apps/MonoliticDataStructure/app/src/endpoints/endpointsExecutive.py).

### Instrucciones al modelo

- [Clientes](../../BackEnd/apps/MonoliticDataStructure/app/src/SystemPrompts/clients_agent.py).
- [Ventas](../../BackEnd/apps/MonoliticDataStructure/app/src/SystemPrompts/sales_forecast_agent.py).
- [Marketing](../../BackEnd/apps/MonoliticDataStructure/app/src/SystemPrompts/marketing_agent.py).
- Las instrucciones de Tendencias se definen en el módulo [market_trends.py](../../BackEnd/apps/MonoliticDataStructure/app/src/market_trends.py).

### Interfaz y pruebas

- [Página del Ejecutivo](../../Frontend/src/pages/ExecutivePage.tsx).
- [Página de agentes](../../Frontend/src/pages/AgentsOperationsPage.tsx) y [tarjeta de Tendencias](../../Frontend/src/pages/components/MarketTrendsCard.tsx).
- [Página de Marketing](../../Frontend/src/pages/MarketingAnalysisPage.tsx) y [tarjeta de oportunidades](../../Frontend/src/pages/components/MarketingOpportunitiesCard.tsx).
- [Pruebas de Ejecutivo y Clientes](../../BackEnd/apps/MonoliticDataStructure/app/tests/test_executive_rules.py).
- [Previsión](../../BackEnd/apps/MonoliticDataStructure/app/tests/test_sales_forecasting.py), [explicación de Ventas](../../BackEnd/apps/MonoliticDataStructure/app/tests/test_sales_forecast_ai.py) y [patrón semanal](../../BackEnd/apps/MonoliticDataStructure/app/tests/test_sales_forecast_weekly.py).
- [Tendencias](../../BackEnd/apps/MonoliticDataStructure/app/tests/test_market_trends.py), [Marketing](../../BackEnd/apps/MonoliticDataStructure/app/tests/test_marketing_opportunities.py) y [conectores](../../BackEnd/apps/MonoliticDataStructure/app/tests/test_external_connectors.py).

### Trazabilidad de entregas

Los commits de las entregas de previsión, Tendencias y Marketing incluyen `78dbb57`, `4936ec1` y `2ba436c`, respectivamente. Permiten localizar esos cambios dentro del historial; no sustituyen la identificación de la versión final desplegada ni incluyen por sí solos toda la contribución a Compras y Clientes.

La documentación de configuración, instalación y despliegue del proyecto sigue siendo la referencia para arrancar cada entorno. Este documento explica la contribución de los asistentes y enlaza sus documentos especializados para ampliar los detalles.
