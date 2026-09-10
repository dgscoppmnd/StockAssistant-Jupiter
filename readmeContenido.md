# Contenido y funcionalidad de Proyecto Jupiter

Proyecto Jupiter es una aplicación web de gestión de inventario y cadena de suministro, presentada con la marca **stockassistant**. Combina operaciones de almacén, gestión comercial, indicadores y asistentes de inteligencia artificial en un portal local.

Para ponerla en marcha, consulta [Instalación local](readmeIntalacion.md).

## Funcionalidades

| Área | Funcionalidad |
| --- | --- |
| Resumen ejecutivo | Indicadores por período, alertas, compras prioritarias, gráficos, exportación CSV y asistente de consulta. |
| Productos | Consulta, creación y edición del catálogo operativo, imágenes y configuración de inventario por producto. |
| Búsqueda vectorial | Indexación CSV del catálogo analítico en Qdrant, embeddings multilingües, búsqueda por similitud, límite de resultados y filtro por categoría mediante API. |
| Inventario | Compras, recepciones, reservas, despachos, devoluciones, transferencias entre bodegas, conversiones de unidades y movimientos auditables. |
| Clientes | Gestión de clientes y tipos, códigos textuales que conservan ceros iniciales, fichas y direcciones asociadas. |
| Proveedores | Gestión de proveedores y sus direcciones. |
| Datos maestros | Unidades, monedas, bodegas, conversiones, direcciones globales y documentos de conocimiento, con validación de referencias. |
| Usuarios y acceso | Inicio de sesión con correo y contraseña, sesiones con caducidad, gestión de usuarios e integración opcional con Google. |
| Chat y agentes | Integración con OpenAI y Ollama; consultas y análisis de compras, stock, ventas, finanzas, reseñas, competencia, contenido comercial y atención al cliente. |
| Centro ejecutivo | Enrutamiento de consultas a agentes, registro de decisiones, propuestas de compra y gestión de automatizaciones. |
| Automatizaciones | Informes diarios, alertas de riesgos y propuestas de reposición; activación, ejecución manual e historial. Las reglas iniciales están pausadas y las propuestas requieren aprobación; no se generan pedidos definitivos automáticamente. |
| Configuración | Estado de integraciones y configuración del acceso a las funciones de stockassistant. |

Las funciones que consultan modelos o fuentes externas requieren sus servicios y credenciales. Los indicadores dependen de los datos cargados: una instalación nueva no equivale a una demostración con historial comercial completo.

## Arquitectura

```text
Navegador
  ├─ Portal compilado: Nginx, puerto 8080
  └─ Portal de desarrollo: Vite, puerto 5173
         │ /api y /media
         ▼
      API FastAPI, puerto 8000
         ├─ PostgreSQL 15: base supply_chain
         ├─ Qdrant 1.19.1: colección vectorial products, puertos 6333/6334
         ├─ Archivos de imágenes en data/uploads
         ├─ Servicios de inventario, maestros y agentes
         ├─ Trabajador de automatizaciones
         └─ Ollama / OpenAI / fuentes externas opcionales

pgAdmin, puerto 5050 → PostgreSQL
```

El frontend utiliza React 18, TypeScript, Vite 5 y Bootstrap. El backend utiliza Python, FastAPI, SQLAlchemy y psycopg2. Las imágenes Docker usan Node.js 20 para el frontend y Python 3.11 para la API.

Nginx sirve el frontend compilado y reenvía `/api/` y `/media/` a la API. Vite también dispone de esos proxies para desarrollo. Docker Compose coordina seis servicios: `postgres`, `backend`, `frontend`, `nginx`, `pgadmin` y `qdrant`.

## Organización del repositorio

```text
Frontend/
  src/
    App.tsx                 Rutas, menú y estructura del portal
    auth.tsx                Estado de autenticación
    api.ts                  Comunicación con el backend
    pages/                  Pantallas funcionales
    pages/components/       Formularios, selectores y componentes
    types.ts                Tipos compartidos del frontend
    styles.css              Estilos
  public/                   Recursos públicos
  package.json              Dependencias y comandos npm
  vite.config.ts            Desarrollo, proxies y compilación
  Dockerfile                Compilación y servicio con Nginx
  nginx.conf                Proxy HTTP y navegación de la SPA
  nginx.tls.conf            Configuración HTTPS opcional
BackEnd/apps/MonoliticDataStructure/
  app/
    src/
      api/                  Aplicación FastAPI y API analítica
      endpoints/            Rutas operativas, autenticación y agentes
      DataBaseManagement/   Acceso a datos y extensiones del esquema
      database/             Modelos, conexión y carga de datos
      generators/           Generadores de datos sintéticos
      vector_store/         Embeddings, indexación CSV y búsqueda Qdrant
      utils/                Utilidades de configuración y datos
      *_service.py          Lógica de negocio e integraciones
    docker/                 Compose, PostgreSQL, pgAdmin e inicialización SQL
    requirements/           Dependencias de API y desarrollo
    scripts/                Arranque, generación, carga y mantenimiento
    notebooks/              Análisis exploratorio
    docs/qdrant.md           Referencia de la integración vectorial
    tests/                  Pruebas unitarias y de integración
    data/                   Datos y archivos persistidos; se crea según uso
    Dockerfile              Imagen de la API
    pyproject.toml          Metadatos y configuración Python
  DB-Definition/DataFiles/   Dataset CSV de referencia
Documentación/              Notas de integración y diagrama de la aplicación
docs/                       Referencias locales, excluidas de Git y de ejecución
```

`Frontend/dist/` se genera al compilar; las dependencias, los datos locales y los archivos `.env` están excluidos mediante `.gitignore`. La carpeta `docs/` puede no existir al clonar el repositorio y no es necesaria para arrancar la aplicación.

## Base de datos y API

La base `supply_chain` contiene dos conjuntos de datos:

- **Analítico original:** `products`, `suppliers`, `warehouses`, `inventory`, `sales`, `logistics` y `supply_chain_metrics`, con rutas bajo `/api/v1`.
- **Operativo:** `productos`, tablas `inventory_*`, clientes, direcciones, documentos comerciales, usuarios, conocimiento, decisiones y automatizaciones, con rutas bajo `/api`.

Los identificadores del catálogo analítico y del operativo son distintos. No existe sincronización automática entre ambos: cargar datos en uno no garantiza que aparezcan en las pantallas del otro.

Los productos analíticos incorporan `product_name` y `description` en el generador, el cargador CSV, los modelos y las respuestas de la API. La búsqueda textual también consulta estos campos. La inicialización SQL actual los incluye y permite añadirlos a tablas anteriores; en filas existentes quedan vacíos hasta completar sus datos.

## Búsqueda semántica de productos

El commit `3369c40` incorpora los siguientes módulos:

| Archivo | Responsabilidad |
| --- | --- |
| `src/vector_store/embeddings.py` | Modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, vectores normalizados de 384 dimensiones y reutilización del modelo por proceso. |
| `src/vector_store/product_indexer.py` | Lee CSV por lotes, combina nombre y descripción, crea la colección si falta y hace upsert con identificadores estables. Reindexar los mismos identificadores no duplica puntos; no elimina productos ausentes del nuevo CSV. |
| `src/vector_store/search.py` | Consulta Qdrant por similitud, aplica filtro exacto de categoría y devuelve puntuación junto con los datos del producto. |
| `src/api/routes/products.py` | Expone `GET /api/v1/products/semantic-search`; carga los módulos vectoriales al usar esta ruta y ejecuta el trabajo síncrono fuera del bucle asíncrono de la API. |

La ruta recibe `q` (mínimo dos caracteres), `limit` (1 a 50, por defecto 10) y `category` opcional. Devuelve `query` e `items`; cada resultado contiene `score`, `product_id`, `product_name`, `product_category`, `brand` y `sku`. Sin colección devuelve una lista vacía.

Qdrant conserva los vectores en el volumen `qdrant_data`. El cliente está fijado en `1.19.0`, compatible con el servidor `1.19.1`. La imagen de la API instala PyTorch para CPU, sin requerir GPU. El modelo se descarga al primer uso; su caché no dispone de un volumen dedicado en el Compose actual.

La indexación es una operación explícita desde CSV: no carga PostgreSQL ni sincroniza el catálogo operativo. El frontend actual no incorpora una pantalla específica para esta ruta. Consulta los comandos en [Instalación](readmeIntalacion.md).

El esquema de instalación está en `BackEnd/apps/MonoliticDataStructure/app/docker/init-scripts/init.sql`. El backend también inicializa tablas operativas faltantes y aplica las extensiones de `src/DataBaseManagement/schema_extensions.sql`.

La documentación interactiva de todos los endpoints está en [Swagger](http://localhost:8000/docs) y [ReDoc](http://localhost:8000/redoc), una vez iniciada la API. `/health` ofrece una comprobación básica del proceso; conviene verificar también PostgreSQL y el acceso real al portal.

## Desarrollo y comprobaciones

El frontend proporciona los comandos `npm run dev`, `npm run build` y `npm run preview`. La API integrada arranca con `uvicorn src.api.main:app`, como define Compose.

La carpeta `tests/` contiene pruebas de reglas de inventario, maestros, agentes, conectores y otros servicios, además de integración HTTP/SQL. `test_jupiter_integration.py` requiere una base desechable cuyo nombre termine en `_test`, indicada mediante `JUPITER_TEST_DB`; no debe apuntar a la base de trabajo.

`test_vector_store.py` se activa con `RUN_VECTOR_INTEGRATION=1` y requiere Qdrant y acceso al modelo de embeddings. Crea una colección temporal, prueba indexación e idempotencia, ranking, filtros, límites y respuestas HTTP, y elimina esa colección al terminar. No modifica los catálogos de trabajo. En la validación local del 8 de septiembre de 2026 pasaron esta prueba y 14 pruebas de reglas; también se verificaron la compilación del frontend y las rutas de acceso, productos e inventario por Nginx.

Los generadores, cargadores y el notebook sirven para experimentación con datos y no son necesarios para iniciar el portal. El historial de integración y sus comprobaciones anteriores se encuentra en [Documentación de integración](Documentación/Integracion-Proyecto-Jupiter.md).
