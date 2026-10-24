# Contenido, funcionalidades y esquema de Proyecto Jupiter

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

Proyecto Jupiter es una aplicación web de gestión de inventario y cadena de suministro,
presentada con la marca **stockassistant**. Integra catálogo, compras, ventas, clientes,
proveedores, análisis comercial y asistentes de inteligencia artificial.

Esta descripción refleja el código y el esquema SQL del repositorio revisados el **23 de
octubre de 2026**. Describe capacidades implementadas; no certifica que estén
desplegadas o configuradas en una instalación concreta. Para el arranque, consulta
[Instalación y actualización](readmeIntalacion.md).

## Funcionalidades del portal

| Área | Funcionalidades actuales | Rutas del portal |
| --- | --- | --- |
| Resumen ejecutivo | Indicadores por período, alertas, prioridades de compra, gráficos, exportación CSV y asistente de consulta. | `/dashboard` |
| Catálogo | Listado paginado, búsqueda, alta y edición, desactivación, imágenes e imagen principal, configuración de inventario, importación CSV con progreso y sincronización vectorial. | `/productlist` |
| Inventario | Existencias por bodega, movimientos, compras, recepciones, reservas, despachos, devoluciones, transferencias y conversiones de unidad. | `/inventario` |
| Pedidos de stock | Creación, consulta, edición y gestión de estados de pedidos de compra; preparación desde propuestas. | `/inventario/pedidos` |
| Pedidos de venta | Gestión de cabeceras y líneas, reserva, despacho, cancelación y devolución, con efectos sobre inventario. | `/ventas/pedidos` |
| Facturas de venta | Creación, edición, emisión, anulación y consulta de documentos y líneas. | `/ventas/facturas` |
| Agentes de operaciones | Alertas de stock, recomendaciones de compra, previsión de ventas, resumen financiero, riesgos y análisis de lotes de reseñas. | `/agentes` |
| Marketing | Competencia, tendencias de mercado, oportunidades y generación de contenido comercial. | `/marketing` |
| Ejecutivo | Enrutamiento de consultas, decisiones registradas, propuestas de compra e historial de automatizaciones. | `/ejecutivo` |
| Control y reglas | Control global, editor de reglas, versiones, simulación, alcance por productos y bodegas, propuestas, ejecuciones, eventos, métricas e interpretación de trazas. | `/agentes/control`, `/agentes/reglas` |
| Consultas de IA | Chat con OpenAI/Ollama y asistente operativo; conversaciones y mensajes persistidos en el chat con memoria. | `/jupiter`, `/chat` |
| Asistente RAG | Preguntas sobre conocimiento indexado, selección de área, respuestas con citas, página, puntuación y avisos de ingesta. | `/rag` |
| Clientes | Clientes y tipos, códigos textuales que conservan ceros iniciales, fichas, direcciones e importación CSV. | `/maestros/clientes`, `/maestros/clientes/:clientId`, `/maestros/tipos-cliente` |
| Proveedores | Gestión de proveedores, direcciones e importación CSV. | `/maestros/proveedores` |
| Datos maestros | Unidades, monedas, bodegas, conversiones y direcciones globales, con validación de referencias. | `/maestros/unidades`, `/maestros/monedas`, `/maestros/bodegas`, `/maestros/conversiones`, `/maestros/direcciones-globales` |
| Base de conocimiento | Documentos con texto o archivo, procesamiento PDF y OCR, estado de indexación, actualización y reindexación. | `/maestros/conocimiento` |
| Usuarios y acceso | Acceso por correo y contraseña, integración opcional con Google, caducidad de sesiones, usuarios y permisos operativos. | Acceso inicial, `/users` |
| Configuración | Estado de integraciones y consulta/aplicación del esquema SQL incluido en el servidor, con progreso e historial. | `/configuracion` |

El portal dispone de menú lateral contraíble y temas diurno y nocturno. Las funciones de
IA, búsqueda web y servicios externos dependen de sus modelos, credenciales y
disponibilidad. Los indicadores y previsiones dependen del historial cargado.

## Operaciones, agentes y automatizaciones

Las operaciones de almacén mantienen existencias, reservas y movimientos auditables. Los
pedidos y facturas de venta tienen líneas y eventos documentales propios; el flujo
comercial utiliza los servicios de inventario para reservar, despachar, cancelar y
devolver mercancía.

El ejecutivo de consulta se complementa con un servicio de automatización operativa. Las
reglas iniciales cubren reposición, informe diario, riesgos y stock estancado. Se crean
desactivadas y admiten configuración versionada, horarios, zona horaria, objetivos,
condiciones, alcance y límites de ejecución.

Hay tres modos: `observation`, `assisted` y `limited_auto`. El modo automático
limitado solo admite las acciones `replenish` y `suspend_reorder` dentro de la política
y los presupuestos configurados. Los informes y las alertas solo observan datos. Las
operaciones físicas y la publicación externa requieren confirmación específica. Activar,
decidir y ejecutar son acciones sujetas a permisos del usuario web.

Las propuestas permiten revisión, decisión, ejecución y confirmación de recepción.
También se preparan borradores de pedidos de stock agrupados para su confirmación. Las
cantidades, cobertura, importes y límites se calculan en código; las respuestas del
modelo se validan mediante contratos estructurados. Las trazas registran fases y
resultados para revisar cada ejecución.

Consulta [Agentes operativos](Documentación/Agentes-Operativos.md) para ampliar el
funcionamiento de los asistentes y el centro de control.

## Arquitectura local

```text
Navegador: React + TypeScript
  ├─ Portal compilado: Nginx, puerto 8080 por defecto
  └─ Desarrollo: Vite, puerto 5173
         │ /api y /media
         ▼
      FastAPI, puerto 8000
         ├─ PostgreSQL 15: supply_chain, puerto local 5433
         │    ├─ Catálogo único products y vista productos
         │    ├─ Inventario, compras, ventas y maestros
         │    └─ Usuarios, chats, conocimiento, reglas y trazas
         ├─ Qdrant: HTTP 6333 / gRPC 6334
         │    ├─ Índice de productos
         │    └─ Índices de conocimiento documental
         ├─ Archivos locales: imágenes y conocimiento
         ├─ Worker de conocimiento
         ├─ Worker de automatizaciones
         └─ OpenAI / Ollama / Google / SerpAPI según configuración

pgAdmin, puerto 5050 → PostgreSQL
```

El frontend utiliza React 18, TypeScript, Vite 5 y Bootstrap 5. El backend utiliza
Python, FastAPI, SQLAlchemy y psycopg2. Las imágenes locales utilizan Node.js 20 y
Python 3.11. Nginx sirve la SPA y reenvía `/api/` y `/media/` a la API; Vite también
dispone de ambos proxies.

Docker Compose define seis servicios: `postgres`, `backend`, `frontend`, `nginx`,
`pgadmin` y `qdrant`. PostgreSQL y Qdrant guardan sus datos en volúmenes; el backend
monta `app/data` para archivos. Qdrant está fijado en `1.19.1`. El arranque local
inicializa el esquema y pone en marcha los workers; el de automatizaciones se controla
con `AUTOMATION_WORKER_ENABLED`.

## Arquitectura y despliegue AWS

```text
Navegador → CloudFront
              ├─ SPA compilada → S3 privado
              └─ /api/* → Lambda Function URL → FastAPI
                                                 ├─ PostgreSQL / RDS
                                                 ├─ S3: imágenes y documentos
                                                 ├─ S3 Vectors: índices vectoriales
                                                 ├─ SSM: configuración y secretos
                                                 └─ Proveedores de IA externos

GitHub Actions → ECR → Migraciones PostgreSQL → Actualización Lambda
              └─ Publicación del frontend en S3 / CloudFront
```

`Dockerfile.lambda` prepara la API para Lambda. En ese entorno el arranque omite la
inicialización DDL y los workers persistentes; el procesamiento pendiente de
conocimiento puede dispararse mediante invocación asíncrona protegida con un secreto
compartido. Los archivos persistentes utilizan S3 cuando está configurado y `/tmp` sirve
de almacenamiento temporal.

Terraform define recursos de CloudFront, archivos e índices S3 Vectors y referencia
recursos existentes. El workflow [Deploy AWS](.github/workflows/deploy-aws.yml)
despliega desde `master`, con destinos `all`, `backend`, `frontend` y `migrations`.
El flujo de backend aplica el esquema y las migraciones pendientes antes de actualizar
Lambda. Estos archivos describen el despliegue previsto y no confirman el estado de los
recursos remotos.

## Esquema de datos actual

La fuente canónica es
[init.sql](BackEnd/apps/MonoliticDataStructure/app/docker/init-scripts/init.sql). Los
módulos de esquema leen sus bloques desde ese archivo, en lugar de mantener copias
independientes del DDL.

### Catálogo unificado

Existe **una única tabla física de productos: `public.products` **. `public.productos`
es una vista actualizable que conserva los nombres del contrato operativo. Ya no son dos
catálogos independientes.

| Elemento | Función |
| --- | --- |
| `products.id` | Clave primaria interna `BIGINT`; conserva los antiguos `productos.pk_product`. |
| `products.product_id` | Código externo textual, único y opcional, usado por los contratos analíticos. |
| `product_name`, `description` | Nombre y descripción compartidos por ambos contratos. |
| `product_category`, `brand`, `sku` | Atributos estructurados del catálogo; SKU es único. |
| `product_cost_usd`, `selling_price_usd` | Importes analíticos explícitos en USD. |
| `price`, `final_price`, `discount`, `fk_currency` | Precio, descuento y moneda del flujo operativo, separados de los importes en USD. |
| `disabled`, `created_at`, `updated_at` | Estado y fechas del producto. |
| Vista `productos` | Traduce campos como `pk_product` y `name_product` a la tabla única; sus escrituras actualizan `products`. |

Las relaciones operativas apuntan a `products.id`. Las tablas analíticas `inventory`,
`sales`, `logistics` y `supply_chain_metrics` conservan sus códigos textuales y
referencian `products.product_id`. Un producto sin código externo puede utilizarse
operativamente sin disponer de registros analíticos. Compartir catálogo no convierte
automáticamente las operaciones del almacén en series históricas analíticas.

La migración conserva los IDs operativos y la identidad vectorial `operational:{id}`.
El procedimiento y la compatibilidad se detallan en
[Unificación del catálogo](infra/PRODUCTS-UNIFICATION.md).

### Tablas y relaciones por dominio

| Dominio | Tablas y vistas principales |
| --- | --- |
| Catálogo e imágenes | `products`, vista `productos`, `products_images`, `product_inventory_config`. |
| Analítica original | `suppliers`, `warehouses`, `inventory`, `sales`, `logistics`, `supply_chain_metrics`; vistas `v_critical_stock`, `v_product_performance` y `v_supplier_efficiency`. |
| Maestros de almacén | `inventory_units`, `inventory_currencies`, `inventory_exchange_rates`, `inventory_unit_conversions`, `inventory_warehouses`, `inventory_suppliers`. |
| Stock y compras | `inventory_stock_levels`, `purchase_orders`, `purchase_order_lines`, `goods_receipts`, `goods_receipt_lines`. |
| Ventas | `sales_orders`, `sales_order_lines`, `inventory_reservations`, `sales_dispatches`, `sales_dispatch_lines`, `sales_invoices`, `sales_invoice_lines`, `sales_returns`, `sales_return_lines`, `sales_document_events`. |
| Transferencias y auditoría | `inventory_transfers`, `inventory_transfer_lines`, `inventory_movements`. |
| Clientes y direcciones | `type_client`, `clients`, `globlal_addresses`, `clients_addresses`, `inventory_suppliers_addresses`. `globlal_addresses` conserva la grafía del esquema. |
| Usuarios y conversación | `users`, `chat_conversations`, `chat_messages`, `proms`. |
| Inteligencia comercial | `external_data_cache`, `review_batches`, `product_reviews`. |
| Conocimiento | `knowledge_documents`, `knowledge_chunks`, `knowledge_vector_deletions`. |
| Ejecutivo y automatización | `agent_decisions`, `automation_rules`, `automation_rule_versions`, `automation_runs`, `automation_events`, `automation_control`, `purchase_proposals`, `agent_action_proposals`. |
| Evolución del esquema | `app_schema_updates`, `app_schema_update_history`; el ejecutor de migraciones añade `schema_migrations`. |
| Estructuras auxiliares | `properties`, `currency`, `type_catalog`, `type_funding_source`, `catalogues`, `catalogues_products`, `markets`, `markets_catalogues`, `error_log`. |

Los maestros operativos de proveedores y bodegas siguen diferenciados de `suppliers` y
`warehouses` analíticos. La unificación de productos no implica una unificación de esos
dominios.

### Actualización del esquema

En local, `init_db()` aplica el esquema canónico. Configuración permite consultar su
checksum y ejecutar la versión incluida en el servidor mediante
`/api/setup/database/status` y `/api/setup/database/update`, con progreso NDJSON e
historial de hashes. Actualmente exige una sesión válida y una cuenta activa no
caducada; `SCHEMA_ADMIN_USER_IDS` no restringe la autorización en ese endpoint.

AWS utiliza `infra/scripts/migrate.py`: valida el historial, aplica el bloque
`JUPITER SCHEMA` si su hash está pendiente y después ejecuta los SQL versionados de
`infra/sql/migrations/`. Comparte historial y bloqueo asesor con Configuración. Cada
aplicación se confirma en su propia transacción; volver a una imagen anterior no
revierte las migraciones confirmadas.

El modelo de permisos PostgreSQL definido el 21 de octubre comparte la propiedad
mediante `migrator`: `app` hereda ese rol y sus conexiones nuevas lo usan como rol
efectivo. Los permisos de base de datos y los de automatización del usuario web son
controles distintos. Consulta los requisitos administrativos, checksums y reglas para
nuevas versiones en [Migraciones PostgreSQL](infra/sql/migrations/README.md).

## Búsqueda semántica y conocimiento documental

### Productos

`GET /api/v1/products/semantic-search` recibe `q` de al menos dos caracteres, `limit`
entre 1 y 50 y `category` opcional. Devuelve la consulta y resultados con puntuación y
metadatos del producto. La implementación selecciona Qdrant o S3 Vectors según la
configuración.

El proveedor local utiliza `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, vectores normalizados de 384 dimensiones y ejecución en CPU. También hay embeddings de
productos mediante OpenAI. El modelo, la dimensión y el índice deben corresponder al
mismo perfil de embeddings.

Puede indexarse un CSV mediante `vector_store/product_indexer.py`. Además, las altas,
ediciones y cambios de estado operativos intentan actualizar su vector; el borrado
intenta retirarlo. La importación CSV del portal guarda productos y comunica el
resultado de indexación por separado. Hay una sincronización completa desde PostgreSQL
expuesta como `POST /api/products/sync-qdrant`, con progreso en el portal. Un fallo
vectorial puede dejar cambios guardados pendientes de sincronizar.

`product_bulk_indexer.py` añade carga CSV por lotes para S3 Vectors con checkpoints
reanudables. Los índices son estructuras derivadas: un upsert no implica eliminar los
elementos ausentes del CSV. La instalación no garantiza que el catálogo vectorial esté
precargado.

### Documentos y RAG

La base de conocimiento permite guardar documentos, extraer texto y procesar PDF con OCR
cuando es necesario, dividir contenido en fragmentos e indexarlo. PostgreSQL conserva
documentos, fragmentos y tareas de eliminación vectorial; archivos y vectores utilizan
los proveedores configurados.

Los embeddings documentales admiten `local`, `ollama`, `openai` y `auto`. Se
mantienen perfiles para separar índices incompatibles. La generación de respuestas
utiliza la capa compartida de IA.

El chat `/rag` utiliza `POST /api/rag/ask`, con selección automática o explícita del
área de consulta. Devuelve respuesta, citas, proveedor/modelo y avisos de ingesta.
También existen `GET /api/v1/knowledge/search` y `GET /api/v1/knowledge/answer`. La
gestión documental dispone de estado y reindexación bajo
`/api/master-data/knowledge-documents`.

## API e integraciones

| Familia | Responsabilidad |
| --- | --- |
| `/api/auth` | Acceso por contraseña o Google, sesión actual y cierre de sesión. |
| `/api/products`, `/api/users`, `/api/master-data` | Catálogo operativo, imágenes, CSV, usuarios y maestros. |
| `/api/inventory`, `/api/sales` | Inventario, pedidos de stock, pedidos de venta y facturas. |
| `/api/agents`, `/api/executive`, `/api/automation` | Asistentes, análisis, decisiones, reglas, propuestas y ejecuciones. |
| `/api/chat`, `/api/rag/ask` | Conversación persistida y consulta RAG. |
| `/api/setup/database` | Estado y aplicación del esquema del servidor. |
| `/api/v1/products`, `/api/v1/inventory`, `/api/v1/sales`, `/api/v1/suppliers` | Consulta analítica y búsqueda semántica de productos. |
| `/api/v1/logistics`, `/api/v1/metrics`, `/api/v1/analytics`, `/api/v1/knowledge` | Logística, indicadores, análisis y recuperación documental. |

La capa de seguridad admite claves API y sesiones; las acciones operativas aplican
comprobaciones adicionales según su endpoint. Los conectores incluyen OpenAI, Ollama,
Google y SerpAPI. La configuración procede del entorno y, en AWS, puede cargarse desde
SSM.

Con la API local iniciada, [Swagger](http://localhost:8000/docs) y
[ReDoc](http://localhost:8000/redoc) muestran los contratos. `/health` comprueba el
proceso; no acredita por sí solo el acceso a PostgreSQL, los índices o los proveedores
externos.

## Organización del repositorio

```text
Frontend/
  src/
    App.tsx                    Rutas, menú, temas y estructura del portal
    api.ts, auth.tsx, types.ts  Cliente API, autenticación y tipos
    pages/                     Pantallas funcionales
    pages/components/          Formularios, asistentes, tablas y trazas
    components/                Componentes comunes y actualización SQL
    utils/                     CSV, sincronización, reglas y conversaciones
    *.css                      Estilos generales y espacios de trabajo
  public/                      Recursos públicos
  Dockerfile, nginx*.conf       Compilación, proxy HTTP y HTTPS opcional
  package.json, vite.config.ts  Dependencias y desarrollo
BackEnd/apps/MonoliticDataStructure/
  app/
    src/
      api/                     FastAPI, configuración y rutas /api/v1
      endpoints/               API operativa, autenticación y asistentes
      DataBaseManagement/      Acceso a PostgreSQL
      database/                Modelos y carga de datos
      SystemPrompts/           Instrucciones de agentes por dominio
      vector_store/            Embeddings, productos, RAG y S3 Vectors
      generators/              Datos sintéticos
      *_service.py             Servicios de negocio e integraciones
      knowledge_*.py           Ingesta, archivos, recuperación y worker
      automation_*.py          Contratos y operaciones de automatización
      sales_forecasting.py     Previsión estadística de ventas
      schema_update_*.py       Aplicación y control del esquema
    docker/                    Compose, PostgreSQL, pgAdmin e init.sql
    requirements/              Dependencias locales, Lambda y desarrollo
    scripts/, notebooks/       Herramientas de datos y experimentación
    docs/                      Documentación técnica del backend
    tests/                     Pruebas unitarias y de integración
    data/                      Archivos y conocimiento según instalación
    Dockerfile                 Imagen de API local
    Dockerfile.lambda          Imagen de API para AWS
  DB-Definition/DataFiles/      CSV de referencia
infra/
  bootstrap/, envs/prod/, iam/  Infraestructura Terraform y políticas AWS
  sql/                         SQL administrativo y migraciones versionadas
  scripts/                     Migraciones, carga de datos y utilidades AWS
ml_factory/                    Experimentación y entrenamiento ML
.github/workflows/             Integración, compilación y despliegue
Documentación/                 Agentes, auditorías y diagramas de arquitectura
```

`Frontend/dist/` se genera al compilar. Dependencias, entornos virtuales y `.env` están
excluidos de Git. El directorio `docs/` de la raíz es una referencia local ignorada;
`app/docs/` y parte de `app/data/knowledge/` tienen excepciones explícitas en
`.gitignore`.

## Previsión, experimentación y comprobaciones

El backend incorpora previsiones estadísticas de ventas y servicios de análisis; los
modelos de lenguaje explican los resultados y ayudan a formular recomendaciones.
`ml_factory/` contiene módulos de features, entrenamiento, evaluación, predicción y
registro con MLflow, con objetivos `stockout` y `reorder`. Es un componente separado de
experimentación: Compose no levanta MLflow y estos módulos no implican que sus modelos
estén conectados automáticamente al portal. El pipeline referencia
`ml_factory.data.DataLoader`, cuyo módulo no está presente en esta revisión del
repositorio.

El frontend ofrece `npm run dev`, `npm run build` y `npm run preview`. Compose inicia
la API con `uvicorn src.api.main:app`.

Las pruebas del backend cubren inventario, ventas, maestros, CSV, catálogo unificado y
paginación, sincronización vectorial, S3 Vectors, RAG y ciclo documental, chats,
agentes, automatización, previsiones, conectores y actualización del esquema.
`infra/scripts/tests/` contiene pruebas del ejecutor de migraciones y herramientas de
desarrollo; `ml_factory/tests/` incluye pruebas de features.

Las suites con servicios requieren preparación explícita. `test_jupiter_integration.py`
utiliza una base desechable indicada por `JUPITER_TEST_DB` cuyo nombre termina en
`_test`; `test_vector_store.py` requiere `RUN_VECTOR_INTEGRATION=1`, Qdrant y el
modelo de embeddings. Las pruebas de unificación PostgreSQL crean bases aisladas.
Consulta los requisitos de cada suite antes de ejecutarla.


