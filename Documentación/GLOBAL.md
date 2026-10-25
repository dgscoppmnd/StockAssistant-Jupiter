
# StockAssistant — Proyecto Júpiter

  

## Memoria global técnica y de negocio

  

### **Máster en Inteligencia Artificial, Cloud Computing y DevOps**

  

### **Trabajo de Fin de Máster 

  

  

**Equipo:** 

| Nombre y Apellido | Tutor           | Convocatoria |
| ----------------- | --------------- | ------------ |
| Diego Gil Sánchez | Carlo M. Morera | Febrero 2026 |
| German Dario      | Carlo M. Morera | Febrero 2026 |
| Said Elkhababi    | Carlo M. Morera | Febrero 2026 |
| Javier Ortega     | Carlo M. Morera | Febrero 2026 |

  

### Página 1 de 20 · Resumen ejecutivo y criterios de lectura

  

StockAssistant es un MVP de asistencia a la gestión de inventario y cadena de suministro. Combina una aplicación web, una API de negocio, almacenamiento relacional, recuperación semántica de documentación e inteligencia artificial generativa. Su finalidad es facilitar la consulta de información y la interpretación de indicadores, manteniendo los cálculos y las operaciones sensibles bajo controles deterministas y, cuando corresponde, aprobación humana.

  

El proyecto comprende dos entornos diferenciados: desarrollo local con Docker Compose y servicios persistentes, y despliegue AWS con frontend en S3/CloudFront, backend FastAPI en Lambda, PostgreSQL en RDS y almacenamiento vectorial en S3 Vectors. El cómputo de la API es serverless, pero **el conjunto de la solución no lo es completamente**, porque RDS mantiene una instancia aprovisionada.

  

La contribución generativa más directamente acreditable es el asistente documental RAG: recupera fragmentos relevantes, construye un contexto y solicita una respuesta con fuentes. También existe agentes de asistencia comercial, explicación de previsiones y coordinación de propuestas operativas. Estas capacidades no deben confundirse con un sistema que compra autónomamente ni con un predictor entrenado integrado en todas las pantallas.


  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 2 de 20 · Caso de negocio, oportunidad y viabilidad

  

### Problema y usuarios

  

La gestión de inventario reúne datos que suelen consultarse por separado: catálogo, existencias, reservas, pedidos, movimientos y documentación. La fragmentación dificulta responder preguntas operativas y puede favorecer decisiones basadas en información incompleta. StockAssistant propone una interfaz común para consultar estos datos, interpretar alertas y acceder a explicaciones documentadas.

  

El usuario objetivo propuesto es una persona responsable de inventario, compras o administración comercial en una organización con varios productos y almacenes. La solución también contempla perfiles de supervisión que necesitan revisar propuestas y su evidencia.

El sector al que la solución va destinada es todo aquel que tenga unas necesidades de gestión de stokc en almacenes de pequeño/mediano tamaño. La solución no pretende competir con grandes sistemas de forecasting ya existentes en el mercado.
Que si pretende la solución:
	-Ofrecer una centralización de la información contenida en los distintos sistemas del almacén.
	-Ofrecer un análisis de todos los datos contenidos.
	-Proporcionar al pequeño/mediano almacén una herramienta de ayuda a la decisión.
	-Proporcionar una base de conocimiento sobre la información histórica y disponible de las operaciones.

  

  

### Propuesta de valor

| Necesidad               | Respuesta propuesta                                 |
| ----------------------- | --------------------------------------------------- |
| Encontrar documentación | Preguntas en lenguaje natural con citas             |
| Entender indicadores    | Explicaciones sobre datos calculados                |
| Revisar reposiciones    | Escenarios y propuestas trazables                   |
| Evitar acciones opacas  | Separación entre sugerencia, aprobación y ejecución |

  

  

### Mercado y viabilidad

El coste potencial se reparte entre infraestructura, consumo de modelos, mantenimiento e incorporación de datos. El retorno puede estimarse como horas ahorradas por coste horario menos coste total, pero debe medirse con tareas equivalentes y usuarios representativos.






  

## Página 3 de 20 · Objetivos, alcance y cumplimiento de las bases

  

### Objetivos

  

1. Implementar un asistente generativo con recuperación de evidencia.

2. Mantener datos de inventario y operaciones en una base relacional.

3. Ofrecer una aplicación web que conecte consultas, indicadores y herramientas.

4. Proporcionar despliegue contenedorizado, control de versiones y automatización.

5. Registrar errores y actividad para facilitar diagnóstico y trazabilidad.

6. Separar resultados demostrados, capacidades experimentales y trabajo futuro.

  

### Matriz de requisitos

  

| Requisito del TFM              | Evidencia disponible                                          |
| ------------------------------ | ------------------------------------------------------------- |
| IA generativa                  | Servicio OpenAI/Ollama y chat RAG                             |
| Base vectorial                 | Adaptadores Qdrant/S3 Vectors y búsquedas                     |
| MVP funcional                  | Frontend y endpoints conectados; pruebas previas documentadas |
| API fundacional o modelo local | OpenAI Responses y Ollama                                     |
| DevOps automatizado            | Workflows de integración y despliegue AWS                     |
| Monitorización y logging       | Eventos de aplicación y CloudWatch documentados               |
| Arquitectura documentada       | Código, IaC y guías                                           |

  

### Fronteras del MVP

  

El núcleo defendible comprende acceso al portal, consultas a los datos disponibles y RAG sobre documentos indexados. Existen módulos operativos más amplios, pero su disponibilidad depende del entorno y de que tengan datos y permisos.

  

**¡¡¡REVISAR!!!:**  Quedan fuera del MVP: promoción automática de modelos, integración con proveedores, predicción de demanda validada en producción y ejecución de todos los agentes en AWS.

  

**¡¡¡REVISAR!!! Fijar el alcance exacto de la demo:** qué recorrido se mostrará en AWS y qué funcionalidades solo se acreditarán con código o pruebas locales. Evitar un listado de capacidades que prometa más de lo demostrable.

  

  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 4 de 20 · Arquitectura general y decisiones técnicas

  

### Arquitectura AWS consolidada

  

```text

Navegador

   |

CloudFront

   +-- aplicación estática --> S3 frontend privado mediante OAC

   |

   +-- /api/* -------------> Function URL --> Lambda + Web Adapter

                                                 |

                                                 +--> RDS PostgreSQL

                                                 +--> S3 Vectors

                                                 +--> S3 de documentos/imágenes

                                                 +--> OpenAI

                                                 +--> SSM Parameter Store

                                                 +--> CloudWatch Logs

```

  ![[Pasted image 20261020201222.png]]

El navegador utiliza rutas relativas de API. CloudFront permite servir interfaz y API bajo el mismo dominio; el origen de API se configura sin caché. El backend conserva FastAPI/Uvicorn y se ejecuta como imagen de contenedor mediante Lambda Web Adapter.

  

En local, Docker Compose organiza PostgreSQL, backend, Qdrant, pgAdmin y frontend de desarrollo o Nginx. Ollama, si se utiliza, requiere un servidor accesible. Ejecutando Compose no se instala y descarga automáticamente Ollama.

**¡¡¡REVISAR!!!**: Imagen de arquitectura con docker en local.
  

### Justificación de componentes

  

| Componente           | Motivo de uso                                   |
| -------------------- | ----------------------------------------------- |
| React y TypeScript   | Interfaz modular y contratos tipados            |
| FastAPI y Pydantic   | API documentada y validación de entradas        |
| PostgreSQL           | Transacciones, relaciones y agregaciones        |
| RAG y base vectorial | Recuperar contexto por significado              |
| Lambda en contenedor | Reutilización del backend y pago por invocación |
| S3 Vectors           | Evitar servidor vectorial permanente en AWS     |

  

Se ha priorizado una única aplicación backend frente a dividir prematuramente el sistema en microservicios. Esto facilita la integración del MVP, aunque exige separar internamente responsabilidades y controlar el tamaño de la imagen.



  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 5 de 20 · Modelo de datos, integridad y procedencia

  

### Dos dominios de información

El dominio analítico se organiza alrededor de siete entidades: `products`, `suppliers`, `warehouses`, `inventory`, `sales`, `logistics` y `supply_chain_metrics`. Sus identificadores y campos sirven para análisis y generación de datasets.

  

El dominio operativo incorpora `productos`, usuarios, clientes, direcciones, unidades, documentos comerciales, movimientos, reservas, conocimiento y automatización. La relación producto-almacén, las claves foráneas y las transacciones permiten conservar invariantes operativas.

  

**¡¡¡REVISAR!!! No existe equivalencia automática entre `products` y `productos`.** Las notas de AWS describen una vista `productos_catalogo` para mostrar el catálogo analítico con la forma esperada por el frontend y una política de solo lectura.


  
### Generación y carga

El proyecto dispone de generadores sintéticos y scripts CSV. La guía AWS registra una carga aproximada de 2,8 millones de filas y 245 MB mediante `COPY`, con orden de carga por dependencias y transacción por tabla. Se trata de datos para pruebas y defensa, no de observaciones de una empresa real.

La semilla inicial para la generación de datos procede de Kaggle.

  

  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 6 de 20 · Frontend y experiencia de usuario

  

El frontend utiliza React 18, TypeScript, Vite y React Router. La estructura separa páginas, componentes compartidos, cliente de API, contexto de autenticación y tipos. El portal reúne catálogo, inventario, ventas, proveedores, datos maestros, asistentes y centro de control.

  

### Interacción con el backend

El cliente usa el prefijo `/api`. Durante desarrollo, Vite reenvía las peticiones a FastAPI; en Compose, Nginx sirve el bundle y actúa como proxy. En AWS, CloudFront dirige las rutas de API al backend y las rutas de aplicación a S3.

  

La autenticación dispone de acceso con contraseña y código para validación de identidad Google. El frontend conserva el token de sesión y lo adjunta a solicitudes posteriores.

  

**¡¡¡REVISAR!!! El login Google pendiente.

  

### Asistente documental

La página RAG permite introducir una pregunta y seleccionar una zona temática. Muestra respuesta, fuentes, página cuando existe, proveedor y avisos de documentos pendientes. También presenta estado de carga y errores en lugar de dejar una respuesta aparentemente correcta cuando falla la consulta.

  

Este recorrido permite demostrar el valor de la IA sin depender de ejecutar movimientos reales. La respuesta debe contrastarse con el documento original.

  

**¡¡¡REVISAR!!!**: Imagen del front.

  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 7 de 20 · Backend y reglas de negocio

  

### Organización

FastAPI integra dos familias principales: `/api/v1` para recursos analíticos y `/api` para autenticación, catálogo operativo, inventario, ventas, maestros y agentes. Los módulos de endpoints delegan en servicios y acceso a PostgreSQL.

  

### Operaciones

El código y la documentación describen compras, recepciones, reservas, despachos, devoluciones, conversiones y traslados. La emisión de un pedido y su recepción física se tratan como hechos diferentes:

  
1. Una propuesta aprobada puede convertirse en pedido pendiente.

2. Emitir el pedido no incrementa existencias.

3. La recepción confirmada registra movimientos y actualiza cantidades.

4. La repetición de una solicitud debe evitar movimientos duplicados.

  

Esta separación reduce el riesgo de confundir una recomendación del modelo con una operación realizada.

  

**¡¡¡REVISAR!!! Separar en la memoria lo comprobado en pruebas locales de lo habilitado en AWS.** Un catálogo analítico mostrado en pantalla no demuestra un ciclo operativo completo de compra y recepción.

  

  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 8 de 20 · Diseño de la solución generativa

  

### Proveedores y modelos

AIService encapsula generación, errores y metadatos. Permite `AI_PROVIDER=openai`, `ollama` o `auto`. El modo automático intenta Ollama y puede recurrir a OpenAI ante determinados errores reintentables; aplica un periodo de enfriamiento para evitar intentos locales repetidos.


| Función            | Configuración de referencia                | Naturaleza                       |
| ------------------ | ------------------------------------------ | -------------------------------- |
| Generación OpenAI  | `OPENAI_MODEL`, por defecto `gpt-4.1-mini` | API de modelo preentrenado       |
| Generación Ollama  | `OLLAMA_MODEL`, por defecto `qwen3:14b`    | Servidor de inferencia accesible |
| Embeddings AWS     | `text-embedding-3-small`                   | Representación semántica         |
| Embeddings locales | MiniLM multilingüe                         | Modelo local de embeddings       |

  
### Construcción de la respuesta RAG

El sistema recupera evidencia antes de generar. El prompt instruye a responder en español, usar únicamente la información suministrada, citar fuentes y no inventar cifras, políticas ni funcionalidades. La documentación se trata como contenido, no como instrucciones del sistema.

  

Si no se recupera evidencia, no se consulta el modelo. Cuando sí hay contexto, se devuelven respuesta, citas, proveedor, modelo y uso de fallback. El chat advierte que los documentos no confirman stock operativo en tiempo real.



  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 9 de 20 · Almacenamiento vectorial y recuperación

  

### Finalidad

La base vectorial almacena representaciones numéricas de documentos y productos. La pregunta se transforma con el mismo perfil de embeddings y se compara por similitud para recuperar candidatos relevantes, aunque no compartan exactamente las mismas palabras.

  

PostgreSQL conserva el contenido documental y su vigencia. S3 Vectors permite encontrar identificadores de fragmentos; el backend recupera y revalida los textos antes de construir el contexto. El índice complementa, no sustituye, la fuente relacional.

  

### Perfiles y compatibilidad

| Entorno | Almacenamiento                | Dimensión de referencia |
| ------- | ----------------------------- | ----------------------: |
| Local   | Qdrant con MiniLM multilingüe |          **REVISAR**384 |
| AWS     | S3 Vectors con OpenAI         |         **REVISAR**1536 |


No se deben mezclar vectores de distintos modelos o dimensiones. El código documental registra proveedor/modelo por fragmento y consulta el perfil correspondiente. Cambiar de modelo exige una estrategia de reindexación.

  

El adaptador S3 utiliza `float32`, lotes de hasta 500 escrituras y consultas de hasta 100 vecinos. La similitud se expresa como `1 - distancia`. Para la búsqueda documental filtra `chunk_id` en grupos de 50 identificadores y aplica el umbral configurado; esa agrupación es una decisión del código, no una garantía universal sobre límites del servicio.
**¡¡¡REVISAR!!!**: informar esta configuración del código.

  

### Productos

La indexación de productos emplea claves estables y `upsert`. El código local incluye sincronización de altas y cambios; no equivale a sincronizar todos los modelos de catálogo entre sí.

  

**¡¡¡REVISAR!!! Documentar el funcionamiento final de productos.

  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 10 de 20 · Ingesta documental y ciclo de vida

  

### Pipeline

El ciclo de vida documental combina almacenamiento de archivos, registro relacional e indexación:

  

1. Se crea o actualiza un documento con título, contenido y referencia.

2. Los archivos se conservan en disco local o en S3 según el entorno.

3. Se extrae el texto y se mantiene la página de origen cuando existe.

4. Se fragmenta en bloques; el servicio usa 900 caracteres con solapamiento de 120.

5. Se generan embeddings en lotes y se escriben en el backend vectorial.

6. Se confirma la revisión y sus fragmentos en PostgreSQL.

7. Las consultas excluyen documentos inactivos, caducados o de revisiones antiguas.

  

El servicio registra progreso y estados como pendiente, procesando, disponible o error. Los bloqueos por documento evitan indexaciones simultáneas de la misma revisión; hay mecanismos de retirada de vectores no publicados.

  

### Local frente a Lambda

En local, un worker persistente procesa pendientes. En Lambda no se mantiene ese hilo: después de los cambios, la aplicación puede autoinvocarse asíncronamente. Lambda Web Adapter dirige el evento a `/internal/index`, que valida un secreto compartido antes de procesar.

  

### Dos límites prioritarios

**¡¡¡REVISAR!!! Tamaño de subida:** la aplicación anuncia un máximo de archivo de 20 MiB, pero la vía actual de petición a Lambda está limitada por el payload de invocación. La referencia documental es 6 MB y el envoltorio/base64 puede reducir el tamaño útil. No prometer 6 MB de archivo neto sin medirlo.

  

**¡¡¡REVISAR!!! PDF/OCR en AWS:** [knowledge_pdf.py](../BackEnd/apps/MonoliticDataStructure/app/src/knowledge_pdf.py) importa `pypdfium2` y utiliza Tesseract; [requirements/lambda.txt](../BackEnd/apps/MonoliticDataStructure/app/requirements/lambda.txt) y [Dockerfile.lambda](../BackEnd/apps/MonoliticDataStructure/app/Dockerfile.lambda) no incorporan todos esos componentes. Los éxitos documentados con TXT/JSON no validan PDF/OCR en esa imagen.

  

<div style="page-break-after: always; break-after: page;"></div>





  

## Página 11 de 20 · Agentes operativos y supervisión humana

  

El coordinador de automatización combina evidencia de inventario, escenarios deterministas y una decisión generativa acotada. Se han definido modos de observación, asistido y automatico. Su propósito no es conceder al modelo acceso libre a SQL o a operaciones de mutación.

  

### Ciclo controlado

El proceso reclama una regla, registra su versión, consulta existencias y operaciones pendientes, calcula alternativas y guarda la evidencia. Después solicita al modelo una selección o priorización dentro de un contrato validado. Las herramientas permitidas operan sobre entidades observadas.

  

Los permisos distinguen lectura, edición, activación, aprobación, ejecución y autorización. Una nueva versión se guarda pausada; los cambios pueden invalidar propuestas pendientes. Existe una parada global y una variable de emergencia.

  

Para reposición, el cálculo considera disponible físico menos reservado, demanda observada, cobertura, plazo, seguridad y compras pendientes. El resultado se redondea según la configuración. La IA no inventa precios ni confirma recepción.

  

### Alcance operativo

| Acción     | Límite                                                           |
| ---------- | ---------------------------------------------------------------- |
| Reposición | Requiere política y, cuando procede, aprobación y oferta vigente |
| Recepción  | Confirmación física; no duplica el pedido                        |
| Traslado   | Revalidación, permisos y confirmación física                     |
| Promoción  | Recomendación condicionada; no campaña publicada                 |
| Esperar    | Decisión registrada sin movimiento                               |

  
Si el proveedor falla o devuelve una salida inválida, se conserva el análisis determinista y la ejecución queda degradada. No se fabrica una decisión de IA para aparentar éxito.

  

### Límite específico de AWS

La entrada de FastAPI omite los workers persistentes en Lambda. La migración SQL de automatización documentada no resuelve por sí sola su programación periódica.

  

**¡¡¡REVISAR!!! Confirmar si existe un scheduler externo realmente desplegado.** Si no lo hay, describir ejecución manual o capacidad local y dejar EventBridge como trabajo futuro.

  

La evaluación de despachos posteriores a una decisión tampoco demuestra que la acción haya causado una mejora comercial.

  



<div style="page-break-after: always; break-after: page;"></div>

  
**¡¡¡REVISAR!!!** Mantenemos??
## Página 12 de 20 · ML Factory y previsión: alcance real

  

### Fábrica de modelos

ml_factory separa construcción de variables, entrenamiento, evaluación y predicción. El pipeline contiene tareas `stockout` y `reorder`, utiliza XGBoost y registra parámetros, métricas y modelo en MLflow.

  

`stockout` puede derivarse de `stockout_risk >= 50` o de stock por debajo del punto de pedido. `reorder` puede usar `predicted_reorder_quantity` o una diferencia no negativa entre punto de pedido y stock.

  

El entrenador reserva el tramo final de las filas recibidas como test. Registra MAE/RMSE y, para clasificación, F1 y accuracy. La documentación incluye promoción y rollback como estrategia, pero no debe atribuirse una promoción automática a producción sin evidencia.


  
### Validez de la evaluación

El constructor ordena por producto, almacén y fecha antes del corte por posición. Eso **no garantiza un corte cronológico global**. También deben revisarse las variables derivadas del target y el preprocesamiento anterior al split para descartar fuga de información.

  

Los lags 7/14/30 cuentan observaciones, no días si faltan fechas. No interpretar un score alto sobre datos sintéticos como precisión demostrada ante roturas futuras.

  

### Previsión que sí utiliza el servicio comercial

El código operativo estima unidades como despachos confirmados de 90 días divididos por 90 y multiplicados por el horizonte. El LLM explica ese cálculo y sus limitaciones; **no es inferencia XGBoost ni demuestra estacionalidad**. Días sin registro no equivalen a demanda cero observada.

  

**¡¡¡REVISAR!!! La carpeta `ml_factory/data` existe localmente, pero sus fuentes no aparecieron en el inventario Git revisado; la regla global `data/` puede afectar a su entrega.** Comprobar una copia limpia antes de presentar el pipeline como reproducible.






  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 13 de 20 · Infraestructura cloud, persistencia y costes

  

La migración a AWS responde a tráfico reducido y restricciones presupuestarias del TFM. Busca reducir cómputo permanentemente encendido y evitar componentes con coste fijo elevado para este escenario.

  

### Componentes y operación

La documentación reciente registra región `eu-west-1`, RDS PostgreSQL 16 en `db.t4g.micro`, 20 GB gp3, cifrado, backups de siete días y protección frente a borrado. El frontend utiliza S3 privado con CloudFront/OAC. La API se distribuye mediante imagen ECR y Lambda Web Adapter.

  

Terraform cubre bootstrap de estado/OIDC, S3 Vectors, archivos y CloudFront. Parte de RDS, IAM operativo y migraciones se describe mediante comandos manuales.

  

**¡¡¡REVISAR!!! No toda la infraestructura puede reconstruirse con un único `terraform apply`.**

  

La Lambda no realiza DDL al arrancar. Su disco persistente se sustituye por S3 y utiliza `/tmp` como almacenamiento temporal. La pérdida de una instancia no debe significar pérdida del archivo fuente.

  

### Costes

Se estiman aproximadamente 20–25 USD mensuales para AWS bajo uso bajo, más consumo variable de OpenAI. Es una estimación, no una factura comprobada; RDS y almacenamiento mantienen coste aunque no se hagan consultas.

  

El gasto de embeddings depende de tokens procesados y reindexaciones, no solo de la cantidad de productos. Conviene limitar las cargas por ejecución y conservar checkpoints protegidos. Las consultas generativas añaden coste por entrada y salida.

  

**¡¡¡REVISAR!!! Añadir captura fechada de Cost Explorer, coste de OpenAI y supuestos de tráfico.** 

  

En un uso empresarial habría que reevaluar disponibilidad, red privada, conexiones, recuperación y protección de entrada. El dimensionamiento del TFM no acredita capacidad productiva a escala.

  



  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 14 de 20 · Seguridad, identidad y gestión de secretos

  

### Controles implementados

El backend incorpora autenticación por contraseña, sesiones y soporte de Google. Las operaciones de automatización consultan permisos persistidos, no solo la presencia de una clave API. La conexión a RDS se configura con TLS y verificación del certificado; se separan roles de administración, migración y aplicación.

  

La Lambda puede cargar secretos desde SSM Parameter Store al arrancar, antes de importar los módulos que leen configuración. Los parámetros se solicitan con descifrado y no se sobrescriben variables ya presentes.

  

La política [ssm-policy.json](../infra/iam/ssm-policy.json) concede `ssm:GetParameters` sobre el prefijo del proyecto. Esa acotación reduce acceso frente a una política de administración, aunque no acredita por sí sola la totalidad de permisos efectivos del rol.

  
| Secreto lógico           | Parámetro relativo a `/stockassistant/prod` |
| ------------------------ | ------------------------------------------- |
| Credencial OpenAI        | `openai_api_key`                            |
| Claves de API            | `api_keys`                                  |
| Firma de sesión          | `session_secret`                            |
| Contraseña de aplicación | `db/app_password`                           |

  
Los valores no forman parte de esta memoria. Un Client ID de Google es un identificador público, no equivalente a un secreto de cliente.

  

### Riesgos y reservas

**RDS público:** Lambda sin VPC necesita conectividad pública adicional; permitir solo la IP del desarrollador no resuelve esa conectividad. TLS, contraseñas fuertes y roles limitados no eliminan la exposición. Definir el control asumido para la defensa sin cerrar el acceso y romper el servicio inadvertidamente.

  

La configuración `VITE_*` se publica en el navegador; nunca debe contener credenciales privadas.

  

<div style="page-break-after: always; break-after: page;"></div>



## Página 15 de 20 · DevOps, versionado y despliegue

  

### Integración y entrega

[integration.yml](../.github/workflows/integration.yml) configura PostgreSQL, inicializa el esquema e invoca la suite backend con cobertura e informe JUnit. Se activa en pull requests a las ramas configuradas y manualmente.

  

[deploy-aws.yml](../.github/workflows/deploy-aws.yml) despliega en push a `master` o ejecución manual. Detecta cambios para separar backend y frontend:

  

- Backend: construye imagen Linux/amd64, publica en ECR con etiqueta SHA, actualiza Lambda y realiza un smoke test.

- Frontend: instala dependencias, compila, sincroniza el bundle con S3 e invalida CloudFront.

- GitHub se autentica mediante OIDC, sin una clave AWS estática almacenada en el workflow.

  
El despliegue no cambia automáticamente variables de Lambda **¡¡¡REVISAR!!!**ni aplica migraciones SQL**..

  

### Desajustes que afectan a la entrega

**¡¡¡REVISAR!!! Confianza OIDC:** los jobs utilizan `environment: production`, mientras que el bootstrap local revisado conserva un subject por rama. Las guías registran la corrección aplicada en AWS hacia el subject del entorno. Reaplicar IaC antigua podría deshacerla.

  

**¡¡¡REVISAR!!! Dependencias frontend:** las guías mencionan una política `legacy-peer-deps` para el conflicto React 16/18. Confirmar que el archivo de configuración y el lockfile necesarios están en el commit final.

  

**¡¡¡REVISAR!!! Workflows heredados:** [build.yml](../.github/workflows/build.yml) invoca rutas de entrenamiento que no corresponden a la organización actual. No presentarlo como pipeline ML vigente sin adaptarlo o justificar su carácter histórico.

  

### Trazabilidad

La entrega debe identificar commit/tag final, SHA de imagen y fecha. Conservar la versión anterior permite preparar rollback de código; **no revierte automáticamente cambios de datos o esquema**.



  



<div style="page-break-after: always; break-after: page;"></div>

  

## Página 16 de 20 · Monitorización, logging y trazabilidad

  

### Capas de observación

El proyecto dispone de eventos de aplicación, registros de ejecución de agentes y documentación de CloudWatch para Lambda/RDS. Se distinguen fallos de proveedor, validación, indexación y sincronización vectorial.

  

AWS registra exportación de logs PostgreSQL con retención de 14 días y alarmas sobre fallos de autenticación y bloqueos de login. 

  

| Capa           | Señal útil                                | Interpretación                          |
| -------------- | ----------------------------------------- | --------------------------------------- |
| API            | Estado HTTP, errores y tiempo             | Disponibilidad de una petición concreta |
| Modelo         | Proveedor, modelo, uso y errores          | Dependencia y comportamiento técnico    |
| Documentos     | Estado, progreso y error                  | Salud de ingesta por revisión           |
| Vectores       | Escrituras y sincronización               | Cobertura y consistencia del índice     |
| Automatización | Versión, evidencia, propuesta y resultado | Trazabilidad de decisiones              |
| Base de datos  | Conexiones y fallos de acceso             | Diagnóstico de persistencia             |

  
El centro de control documenta latencia mediana/P95, respuestas válidas, herramientas y bloqueos de políticas. Tokens y costes solo deben agregarse donde el proveedor informa uso. El coste por tarea figura no disponible si no se mide.

  

### Límites interpretativos

Una ejecución degradada puede ser técnicamente controlada y, aun así, no haber generado una propuesta útil. HTTP 200 no significa acierto comercial. Requiere aprobación humana.

  

**¡¡¡REVISAR!!! Incorporar una captura de logs de un recorrido y una tabla de métricas reales**, con periodo, número de muestras y versión. Anonimizar usuarios, prompts, documentos y credenciales.

  


  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 17 de 20 · Evaluación técnica y funcional

  

### Evidencias previas y su alcance
**¡¡¡REVISAR!!!** datos de la tabla:

| Evidencia documentada      | Resultado registrado                               | Qué no demuestra                           |
| -------------------------- | -------------------------------------------------- | ------------------------------------------ |
| Integración local          | 19 pruebas unitarias y 3 HTTP/SQL aprobadas        | Estado de la suite final                   |
| Integridad local           | 9 regresiones del inicializador; catálogo auditado | Igualdad completa con RDS                  |
| RAG AWS                    | 2 documentos disponibles y respuesta con cita      | Calidad general sobre muchos documentos    |
| Catálogo vectorial AWS     | Primer resultado esperado, score 0,890146          | Recall global ni confianza de la respuesta |
| Carga analítica AWS        | 200.000 productos y 899.004 filas de ventas        | Datos reales o cobertura vectorial total   |
| API caliente, carga previa | Productos 0,58 s; inventario 0,50 s                | SLA, P95 ni rendimiento bajo concurrencia  |


  
### Protocolo de evaluación propuesto

Para RAG, preparar un conjunto fijo de preguntas respondibles, ambiguas y sin evidencia. Cada caso debe identificar documentos esperados, respuesta de referencia y criterio de aceptación.

  

Medir recuperación con Recall@k y generación con exactitud factual, apoyo de citas y abstención correcta. Registrar latencia por etapa, fallos, tokens y coste cuando estén disponibles. Un score coseno alto no es una probabilidad de veracidad.

  

**¡¡¡REVISAR!!! Completar una evaluación final reproducible, por ejemplo de 20–30 preguntas**, indicando tamaño exacto, versión, documentos y criterio de revisión. El tamaño propuesto no es un requisito oficial ni sustituye representatividad.

  

Para previsiones, comparar con un baseline simple y separar entrenamiento/prueba temporalmente. WAPE no es evaluable si el total observado es cero. Para clasificación, revisar matriz de confusión y recall de roturas, no solo accuracy.

  

**¡¡¡REVISAR!!! No hay métricas consolidadas que permitan afirmar mejora comercial ni precisión predictiva productiva.** Incorporar resultados reales o mantener esa evaluación como limitación.

  

<div style="page-break-after: always; break-after: page;"></div>





## Página 18 de 20 · Configuración y reproducibilidad de la entrega

  

### Configuración sin secretos

| Grupo        | Variables o recursos que deben documentarse                   |
| ------------ | ------------------------------------------------------------- |
| IA           | `AI_PROVIDER`, `OPENAI_MODEL`, `OLLAMA_URL`, `OLLAMA_MODEL`   |
| Embeddings   | `RAG_EMBEDDING_PROVIDER`, `OPENAI_EMBEDDING_MODEL`, dimensión |
| Vectores     | `VECTOR_BACKEND`, `S3_VECTORS_BUCKET`, índices, `QDRANT_URL`  |
| PostgreSQL   | Familias `DB_*` y `POSTGRES_*` usadas por los conectores      |
| Archivos     | `DOCUMENTS_BUCKET`, rutas temporales/locales                  |
| Secretos AWS | `SECRETS_FROM_SSM=true`, nombres de parámetros y permisos     |
| Frontend     | Identificador Google público y variables de despliegue        |

  

La configuración AWS preparada usa embeddings OpenAI de 1536 dimensiones y backend `s3vectors`. En local, el perfil predeterminado utiliza Qdrant/MiniLM. Confirmar siempre ambos lados antes de reindexar.

  

### Puesta en marcha

La guía [readmeIntalacion.md](../readmeIntalacion.md) describe Compose y configuración local. La [guía para desarrolladores AWS](../docs/AWS_Guia_Desarrolladores.md) detalla publicación y acceso a recursos.



**¡¡¡REVISAR!!!**: Documentación reproducible de puesta en marcha.

  

**¡¡¡REVISAR!!! Inventario Git:** `BackEnd/apps/MLStockPredictTool` figura sin versionar.

  

**¡¡¡REVISAR!!!** El helper [set-lambda-env.py](../infra/scripts/set-lambda-env.py) fusiona configuración y retira secretos del mapa de la función. No ejecutar actualizaciones sin revisar el mapa resultante; algunas operaciones AWS sustituyen toda la configuración.

  

### Verificación previa al cierre

  

- Clonar o exportar el commit final en una ubicación limpia.

- Comprobar archivos indispensables, instalación y permisos del evaluador.

- Registrar imágenes, variables sin valores sensibles y comandos vigentes.

- Preparar restauración y copia de seguridad antes de migraciones.

  

**¡¡¡REVISAR!!! Esta comprobación de copia limpia queda pendiente; no ejecutada.**

  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 19 de 20 · Equipo, ejecución y preparación de la defensa

  

### Contribución individual

  

La evaluación es individual aunque el producto sea conjunto. Una asignación inicial de tareas no demuestra su ejecución: debe acompañarse de entregables, commits, pull requests, pruebas o documentación.

  

| Integrante             | Responsabilidad efectivamente realizada | Evidencia             | Participación en defensa |
| ---------------------- | --------------------------------------- | --------------------- | ------------------------ |
| ¡¡¡REVISAR!!! Nombre 1 | Completar sin atribuciones inferidas    | Commits/PR/artefactos | Bloque y duración        |
| ¡¡¡REVISAR!!! Nombre 2 | Completar sin atribuciones inferidas    | Commits/PR/artefactos | Bloque y duración        |
| ¡¡¡REVISAR!!! Nombre 3 | Completar sin atribuciones inferidas    | Commits/PR/artefactos | Bloque y duración        |
|                        |                                         |                       |                          |


  

### Evolución del proyecto

El proyecto a evolucionado desde modelo relacional y generación sintética hacia integración frontend/backend, búsqueda vectorial, agentes y migración AWS. Los cambios de arquitectura responden a compatibilidad y coste: retirada de dependencias pesadas en Lambda, persistencia S3 y sustitución del worker documental por eventos asíncronos.

  

Los documentos de planificación deben conservarse como historia, no como prueba de terminación. La entrega debe identificar una única versión funcional y distinguir los experimentos.

  

### Propuesta de defensa de 15 minutos

| Bloque                        | Tiempo orientativo |
| ----------------------------- | -----------------: |
| Problema y valor de negocio   |              2 min |
| Arquitectura y decisiones     |              3 min |
| Demo RAG y recorrido elegido  |              5 min |
| DevOps, evaluación y límites  |              3 min |
| Conclusiones y contribuciones |              2 min |


  

**¡¡¡REVISAR!!! Preparar credenciales de demostración limitadas, acceso del tribunal y disponibilidad de OpenAI.** No proyectar terminales que revelen SSM, variables o tokens.

  

<div style="page-break-after: always; break-after: page;"></div>

  

## Página 20 de 20 · Conclusiones, revisión final y referencias

  

### Conclusiones y trabajo futuro

StockAssistant integra una solución generativa con recuperación documental, persistencia relacional y despliegue cloud. El código respalda la separación entre evidencia, cálculo y explicación, RAG con citas y publicación automatizada en AWS.

  

El trabajo futuro incluye evaluación representativa, mejor aislamiento de red, programación compatible con Lambda, integración de ML acreditada y mejora de trazabilidad y costes.



1. **Completar la gestión de infraestructura mediante Terraform**, incorporando los recursos y configuraciones que actualmente requieren preparación externa, para facilitar despliegues reproducibles y la recuperación del entorno.