# Proyecto Jupiter

<!-- Presentación en pantalla e impresión A4; sin cambios de contenido. -->
<style>
body {
  max-width: 180mm;
  margin-inline: auto;
  padding-inline: 1rem;
  line-height: 1.5;
}
p, li, td, th {
  overflow-wrap: anywhere;
}
table {
  width: 100%;
  max-width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
}
th, td {
  white-space: normal;
  vertical-align: top;
  padding: 0.4em;
}
@page {
  size: A4 portrait;
  margin: 15mm;
}
@media print {
  body {
    max-width: none;
    margin: 0;
    padding: 0;
    font-size: 10pt;
  }
  h1, h2, h3, h4 {
    break-after: avoid-page;
  }
  p, li {
    orphans: 3;
    widows: 3;
  }
  thead {
    display: table-header-group;
  }
  tr {
    break-inside: avoid;
  }
}
</style>

**stockassistant** es un portal de gestión de inventario y cadena de suministro con:
catálogo, compras, ventas,
clientes, proveedores,
análisis y asistentes de inteligencia artificial.

Estado documentado a **24 de octubre de 2026**, contrastado con el código y el esquema
del repositorio.

Las capacidades implementadas requieren los datos, servicios y credenciales
correspondientes.

La etiqueta **Versión futura** identifica ampliaciones pendientes; no indica que estén
disponibles en la aplicación.

- [Instalación y actualización](readmeIntalacion.md).
- [Contenido, arquitectura y esquema de datos](readmeContenido.md).
- [Agentes operativos, centro de control, reglas y pruebas](Documentación/Agentes-Operativos.md).
- [Historial de integración y verificaciones](Documentación/Integracion-Proyecto-Jupiter.md).
- [Unificación del catálogo](infra/PRODUCTS-UNIFICATION.md) y
  [migraciones PostgreSQL](infra/sql/migrations/README.md).

## Funcionalidades actuales

| Área | Capacidades implementadas |
| --- | --- |
| Resumen ejecutivo | Indicadores por período, alertas, prioridades de compra, gráficos, exportación CSV y asistente de consulta. |
| Productos | Catálogo paginado, búsqueda, altas, edición, desactivación, imágenes, configuración de inventario, importación CSV y sincronización vectorial con progreso. |
| Inventario y compras | Existencias por bodega, pedidos de stock, recepciones, reservas, despachos, devoluciones, transferencias, unidades y movimientos auditables. |
| Ventas | Pedidos con líneas, reserva, despacho, cancelación y devolución; facturas con edición, emisión y anulación. |
| Clientes y proveedores | Fichas, direcciones, tipos de cliente e importación CSV. |
| Datos maestros | Unidades, monedas, bodegas, conversiones y direcciones globales. |
| Agentes y análisis | Recomendaciones de compra, previsión estadística de ventas, resumen financiero, reseñas, competencia, tendencias, oportunidades de marketing, contenido comercial y atención al cliente. |
| Ejecutivo | Selección de agente por reglas de código o elección explícita y registro de decisiones. Su servicio de consulta es de solo lectura. |
| Automatizaciones | Reglas versionadas, objetivos, condiciones, horarios, presupuestos, simulación, control global, propuestas, decisiones, ejecuciones, eventos, métricas e interpretación de trazas. |
| Conversación y conocimiento | Chat OpenAI/Ollama, chat con memoria, documentos y archivos, PDF/OCR, indexación, reindexación y RAG con citas. |
| Acceso y configuración | Sesiones con caducidad, acceso por contraseña y Google opcional, usuarios, permisos operativos, estado de integraciones y actualización del esquema incluido en el servidor. |

El portal incluye temas diurno/nocturno y menú lateral contraíble. No se garantiza un
historial comercial ni un índice vectorial precargados: los resultados dependen de los
datos de cada instalación.

## Arquitectura de la aplicación

```text
Usuario → Portal React + TypeScript
             │ /api
             ▼
          FastAPI
             ├─ Operaciones: productos, inventario, compras, ventas y maestros
             ├─ Ejecutivo de consulta: enrutamiento por reglas
             │    ├─ Stock y compras
             │    ├─ Ventas y finanzas
             │    ├─ Clientes y atención al cliente
             │    └─ Competencia, marketing, riesgos y tendencias
             ├─ Automatizaciones: reglas → propuestas → decisión/ejecución
             ├─ Chat con memoria y conocimiento documental / RAG
             └─ Persistencia e integraciones
                  ├─ PostgreSQL
                  ├─ Qdrant local / S3 Vectors según configuración
                  ├─ Archivos locales / S3 según configuración
                  └─ Ollama / OpenAI / Google / SerpAPI
         
        ▼
PostgreSQL
Ollama
APIs externas                 
```

En local, Docker Compose levanta seis servicios: PostgreSQL 15, backend Python
3.11/FastAPI, Vite, Nginx, pgAdmin y Qdrant `1.19.1`.
El frontend utiliza React 18, TypeScript, Vite 5 y Bootstrap 5. Nginx sirve la SPA
compilada y conserva los prefijos `/api/` y `/media/`;
Vite también configura esos proxies.

El repositorio incluye una variante AWS con CloudFront/S3 para el frontend, Lambda y ECR
para la API, RDS, S3 para archivos, S3 Vectors y SSM. Terraform referencia también
recursos existentes; no constituye una instalación completa de todos los recursos desde
cero. GitHub Actions permite desplegar desde `master` y aplicar el esquema y las
migraciones antes de actualizar Lambda. Esta descripción no certifica el estado del
despliegue remoto.

## Integración a 8 de septiembre de 2026

El resumen de integración está en
[Documentación de integración](Documentación/Integracion-Proyecto-Jupiter.md). El
commit `3369c4082bb2194550df90641c97e049f0f1d94b` está integrado: incorpora Qdrant,
embeddings multilingües, indexación de productos desde CSV y el endpoint
`/api/v1/products/semantic-search`.

La búsqueda vectorial utiliza el catálogo analítico y no se sincroniza automáticamente
con los productos operativos del portal. No hay una pantalla específica de búsqueda
semántica en el frontend actual. Es necesario indexar un CSV propio para obtener
resultados; la instalación no precarga un catálogo vectorial.

## Esquema, búsqueda y RAG

Existe **una única tabla física de productos: `public.products` **. La vista
actualizable `public.productos` mantiene el contrato operativo.
Las relaciones operativas utilizan `products.id`; las analíticas conservan el código
textual único y opcional `products.product_id`.
Los maestros analíticos y operativos de proveedores y bodegas siguen diferenciados.
Compartir catálogo no genera automáticamente stock ni historial analítico.

El esquema canónico está en
[init.sql](BackEnd/apps/MonoliticDataStructure/app/docker/init-scripts/init.sql).
Incluye inventario, compras, ventas, maestros, usuarios, chats, conocimiento y
automatizaciones.
El backend local aplica el esquema al arrancar; la pantalla de Configuración y el
ejecutor AWS permiten aplicar versiones con control de checksum e historial.
Consulta las guías de migración antes de actualizar una base existente.

La búsqueda semántica se expone en `GET /api/v1/products/semantic-search`, con `q`,
`limit` y categoría opcional. Las altas, ediciones,
cambios de estado y cargas CSV del portal intentan sincronizar sus vectores. **Lista de
productos → Sincronizar Qdrant** permite reindexar
desde PostgreSQL con progreso. La indexación directa desde CSV sigue disponible como
operación independiente y no importa sus filas a SQL.
Un fallo vectorial puede dejar cambios guardados pendientes de sincronizar.

La base de conocimiento gestiona documentos, archivos, extracción PDF/OCR, fragmentos y
reindexación. El chat RAG utiliza `POST /api/rag/ask`
y devuelve citas y avisos de ingesta. Los embeddings documentales admiten proveedores
local, Ollama y OpenAI, además de selección automática;
los perfiles de modelo e índice deben ser compatibles.

## Automatizaciones y límites actuales

Las reglas iniciales están desactivadas y cubren reposición, informes diarios, riesgos y
stock estancado.
Admiten modos `observation`, `assisted` y `limited_auto`. El automático limitado solo
permite `replenish` y `suspend_reorder`
bajo los límites configurados; informes y alertas solo observan datos. Las operaciones
físicas y la publicación externa necesitan confirmación específica.

La ejecución operativa utiliza permisos del usuario, contratos estructurados, cálculos
en código y trazas. El ejecutivo de consulta no aprueba compras ni modifica inventario.
En Lambda el arranque omite DDL y workers persistentes; el conocimiento dispone de
disparo asíncrono, mientras que la ejecución periódica de automatizaciones necesita un
mecanismo específico para ese entorno.

# Datos de backend para modelos sugeridos

Se conservan los agentes y modelos Ollama propuestos, y se añade una recomendación
OpenAI por tipo de trabajo.
**Son sugerencias de diseño y evaluación, no asignaciones activas ni modelos probados en
esta instalación.**
Los nombres y etiquetas locales deben existir en tu servidor Ollama.

La configuración de generación actual se comparte mediante `AI_PROVIDER`,
`OLLAMA_MODEL` y `OPENAI_MODEL`, con valores
predeterminados `auto`, `qwen3:14b` y `gpt-4.1-mini`. OpenAI se consume mediante
Responses API.
La elección independiente por agente figura como **Versión futura**.

| Agente | Modelo recomendado Ollama | Modelo recomendado OpenAI | Nota |
| --- | --- | --- | --- |
| Compras inteligente | `qwen3:14b` | `gpt-6.1-sol` | Comparar ofertas, interpretar fichas y justificar recomendaciones. Precios, descuentos y costes se calculan en código. |
| Gestión de stock | Predictor estadístico + `qwen3:4b-instruct` | SQL/reglas + `gpt-6-luna` | El modelo explica alertas y sugerencias. Las cantidades proceden del servicio operativo; el predictor ML integrado es **Versión futura**. |
| Predicción de ventas | Predictor estadístico + `qwen3:8b` | Predictor estadístico + `gpt-6-luna` | La previsión procede de SQL/Python y se explica con IA. La selección y validación estadística ya existen; la integración de modelos MLflow es **Versión futura**. |
| Financiero | SQL/código + `qwen3:4b-instruct` | SQL/código + `gpt-6-luna` | Márgenes, beneficios y rentabilidad deben ser cálculos deterministas. |
| Valoraciones | `qwen3:8b` o `qwen3:14b` | `gpt-6-luna` | Actualmente hay lotes y clasificación por heurísticas; la síntesis y clasificación mediante LLM de esta propuesta son **Versión futura**. |
| Competencia | `qwen3:4b-instruct` | `gpt-6-luna` | Consulta fuentes disponibles mediante conectores y caché. La recolección periódica con scrapers propios es **Versión futura**. |
| Comercial | `qwen3:14b` | `gpt-6.1-sol` | Generación de contenido para canales comerciales. Un agente SEO independiente y la publicación automática son **Versión futura**. |
| Atención al cliente | `qwen3:14b` + `embeddinggemma` | `gpt-6.1-sol` + `text-embedding-3-small` | RAG sobre documentos vigentes, catálogo y stock operativo cuando se proporciona contexto de producto. Los embeddings se configuran por separado. |
| Compras automáticas | Reglas deterministas + `qwen3:4b-instruct` | Reglas deterministas + `gpt-6-luna` | El código controla aprobación, límites y creación del pedido; las reglas permiten automatización limitada, con confirmación específica de la operación física. |
| Riesgos | Detección de anomalías + `qwen3:8b` | Reglas SQL + `gpt-6-luna` | Actualmente se detectan señales mediante reglas, como tasa de devoluciones. Un detector de anomalías aprendido y su síntesis LLM son **Versión futura**. |
| Inteligencia de mercado | `qwen3:14b` | `gpt-6.1-sol` | Analiza tendencias y fuentes externas y propone oportunidades con evidencia, sujeto a conectores y credenciales. |
| Ejecutivo / Manager IA | `qwen3:14b` | `gpt-6.1-sol`; `gpt-6-astra` para análisis especialmente complejos | Actualmente enruta por reglas de código y registra resultados. La orquestación decidida autónomamente por el LLM es **Versión futura**; el ejecutivo no ejecuta compras. |

La distribución por agente es una propuesta del proyecto basada en el tipo de tarea:
OpenAI presenta `gpt-6-luna` para volumen y eficiencia, `gpt-6.1-sol` para equilibrio
entre capacidad y coste y `gpt-6-astra` para trabajos exigentes. Referencia consultada
el 24 de octubre de 2026:
[catálogo oficial de modelos OpenAI](https://developers.openai.com/api/docs/models).
Verifica disponibilidad en tu cuenta y evalúa calidad, latencia, límites de salida y
coste antes de cambiar `OPENAI_MODEL`; no se han probado aquí esas combinaciones.

Para embeddings OpenAI se propone
[text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small), que ya contempla la configuración del proyecto. Los embeddings locales de productos
usan por defecto `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` y 384
dimensiones.
Cambiar de perfil requiere un índice compatible y reindexación.

## Especificaciones pendientes

Las siguientes ampliaciones conservan el objetivo funcional sin presentarlo como una
capacidad terminada:

| Especificación | Estado y alcance pendiente |
| --- | --- |
| Modelos distintos por agente | **Versión futura:** selector y configuración de proveedor/modelo por agente; hoy las llamadas de generación comparten configuración. |
| Ejecutivo autónomo | **Versión futura:** planificación y elección de herramientas decididas por el modelo. El ejecutivo actual utiliza enrutamiento por reglas. |
| ML Factory integrada | **Versión futura:** pipeline completo y conexión de modelos registrados al portal. Hay módulos de features, entrenamiento y evaluación, pero falta `ml_factory.data.DataLoader` y Compose no levanta MLflow. |
| Anomalías aprendidas y reseñas con LLM | **Versión futura:** sustituir o complementar heurísticas con modelos evaluados; las reglas y el procesamiento básico actuales sí están implementados. |
| Scrapers de competencia y publicación SEO | **Versión futura:** recolección autónoma propia y publicación comercial. Actualmente existen conectores externos y generación de contenido. |
| Automatizaciones periódicas en Lambda | **Versión futura:** mecanismo de programación equivalente al worker local; el arranque Lambda no mantiene ese worker. |

## Resumen de arranque local

Requisitos: Docker Desktop con contenedores Linux/WSL 2 en Windows, código del proyecto
y conexión para descargar imágenes y dependencias.
No necesitas instalar Python o Node.js en el equipo para el arranque con Docker.

Primero prepara `BackEnd/apps/MonoliticDataStructure/app/docker/.env` siguiendo
[Instalación](readmeIntalacion.md),
con **tu propia clave API local y un secreto de sesión independiente**.
Deja sin credencial los proveedores que no uses y configura claves propias de OpenAI o
SerpAPI cuando los habilites.
No incluyas credenciales de proveedores en el frontend.

Desde la raíz del repositorio, en PowerShell:

```powershell
$compose = 'BackEnd/apps/MonoliticDataStructure/app/docker/docker-compose.yml'
$envFile = 'BackEnd/apps/MonoliticDataStructure/app/docker/.env'
docker compose --env-file $envFile -f $compose config --quiet
docker compose --env-file $envFile -f $compose up -d --build
docker compose --env-file $envFile -f $compose ps
```

| Servicio | Dirección local |
| --- | --- |
| Portal compilado | [http://localhost:8080](http://localhost:8080) |
| Desarrollo Vite | [http://localhost:5173](http://localhost:5173) |
| API y documentación | [Swagger](http://localhost:8000/docs), [ReDoc](http://localhost:8000/redoc) |
| PostgreSQL | `localhost:5433` |
| pgAdmin | [http://localhost:5050](http://localhost:5050) |
| Qdrant | [Dashboard](http://localhost:6333/dashboard); HTTP 6333 y gRPC 6334 |

Si cambias `HTTP_PORT`, adapta la dirección del portal. El modelo local de embeddings
se descarga al primer uso; Compose no instala ni inicia Ollama.

Cuenta inicial del portal:

- **Correo:** `admin@stockassistant.app`
- **Contraseña:** `Jupiter!2026Stock`

Para una instalación existente, respalda y ensaya la migración **antes de arrancar el
backend nuevo**: aplica el esquema al iniciar.
Las instrucciones de actualización, persistencia, HTTPS y AWS están en
[Instalación](readmeIntalacion.md).
No ejecutes pruebas de integración sobre la base de trabajo.

## Verificación y documentación técnica

Las pruebas cubren inventario, ventas, maestros, importaciones, catálogo unificado,
sincronización vectorial, RAG, chats, agentes,
automatización y migraciones, con requisitos distintos según la suite. Las integraciones
PostgreSQL necesitan bases aisladas;
la prueba vectorial requiere Qdrant y embeddings. `/health` comprueba el proceso, no
todos los servicios externos.

Comprobación local del 8 de septiembre de 2026:

- Compilación del frontend completada correctamente.
- Login por el portal 8080, sesión, productos e inventario con respuesta HTTP 200.
- 14 pruebas de reglas y una prueba de integración vectorial superadas.
- Embeddings reales, indexación por lotes, reindexación sin duplicados, búsqueda por
  similitud, filtro de categoría y
validación de consultas comprobados con datos temporales; la colección de prueba se
eliminó al terminar.

Qdrant está fijado en `1.19.1` y su cliente Python en `1.19.0`. La imagen utiliza
PyTorch `2.8.0`
para CPU y NumPy `1.26.4` compatible con pandas `2.1.0`. La carga vectorial se realiza
al invocar su ruta,
sin bloquear el arranque del login. Si la colección aún no existe, la búsqueda devuelve
`items: []`.

Consulta los comandos y requisitos en [Instalación](readmeIntalacion.md) y la
descripción de módulos y tablas en [Contenido](readmeContenido.md).
Esta revisión del README no ejecuta pruebas funcionales, evalúa los modelos sugeridos ni
valida recursos AWS.