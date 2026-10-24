# Instalación y actualización de Proyecto Jupiter

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

Esta guía utiliza el Docker Compose incluido en el proyecto. Los comandos están escritos
para **PowerShell en Windows**, desde la raíz del repositorio. Docker ejecuta la API,
PostgreSQL y los dos modos del frontend; no hace falta instalar Python ni Node.js en el
equipo para este arranque.

Para conocer los módulos y la estructura, consulta
[Contenido del proyecto](readmeContenido.md).

Guía contrastada con los archivos del repositorio el **23 de octubre de 2026**. La
instalación principal es local con Docker; al final se describen HTTPS y los requisitos
del despliegue AWS. No se necesita AWS para utilizar el portal local.

## 1. Preparar el equipo

1. Instala Docker Desktop con soporte para contenedores Linux y WSL 2, y abre Docker
   Desktop.
2. Instala Git si vas a obtener el código mediante clonación; también puedes utilizar
   una copia del proyecto ya descargada.
3. Necesitas conexión a Internet en el primer arranque para descargar imágenes y
   dependencias.
4. Comprueba que los puertos `8080`, `5173`, `8000`, `5433`, `5050`, `6333` y
   `6334` estén disponibles.

Verifica Docker en PowerShell:

```powershell
docker --version
docker compose version
docker info
```

`docker info` debe conectar con el motor. Si falla, inicia Docker Desktop y espera a que
esté listo.

## 2. Abrir el proyecto

Si aún no tienes el código, clona la URL de tu repositorio o extrae la copia descargada.
Abre PowerShell en la carpeta que contiene `Frontend`, `BackEnd` y `README.md`.

En esta instalación la ruta es:

```powershell
Set-Location 'D:\MasterPontiaIA\ProyectoupiterV3'
$compose = 'BackEnd/apps/MonoliticDataStructure/app/docker/docker-compose.yml'
Test-Path $compose
$envFile = 'BackEnd/apps/MonoliticDataStructure/app/docker/.env'
```

Adapta la ruta a tu equipo. `Test-Path $compose` debe devolver `True`. Si abres otra
terminal, vuelve a situarte en la raíz y a definir `$compose` y `$envFile`.

## 3. Revisar la configuración local

Compose tiene valores predeterminados de desarrollo, pero configura tus propias claves
antes del arranque. Esta guía carga explícitamente el archivo `.env` mediante
`--env-file`; su ubicación es:

```text
BackEnd/apps/MonoliticDataStructure/app/docker/.env
```

Si ya existe, conserva su contenido y modifica solo las variables necesarias. Si no
existe, crea un archivo de texto `.env` con este ejemplo local. **Sustituye los
marcadores `REEMPLAZA_...` antes de arrancar; no son claves utilizables.**

```dotenv
POSTGRES_USER=admin
POSTGRES_PASSWORD=admin123
POSTGRES_DB=supply_chain
PGADMIN_DEFAULT_EMAIL=admin@jupiter.example.com
PGADMIN_DEFAULT_PASSWORD=admin123
HTTP_PORT=8080
TZ=Europe/Madrid
STOCKASSISTANT_API_KEYS=REEMPLAZA_CON_TU_CLAVE_API_LOCAL
VITE_STOCKASSISTANT_API_KEY=REEMPLAZA_CON_TU_CLAVE_API_LOCAL
STOCKASSISTANT_SESSION_SECRET=REEMPLAZA_CON_TU_SECRETO_DE_SESION
STOCKASSISTANT_SESSION_TTL_MINUTES=120
AUTOMATION_WORKER_ENABLED=true
AUTOMATION_WORKER_POLL_SECONDS=60
AI_PROVIDER=auto
OLLAMA_URL=http://host.docker.internal:11434/api/generate
OLLAMA_MODEL=qwen3:14b
OLLAMA_TIMEOUT_SECONDS=60
OLLAMA_THINK=false
OPENAI_MODEL=gpt-4.1-mini
OPENAI_API_KEY=
SERPAPI_API_KEY=
GOOGLE_CLIENT_ID=
VITE_GOOGLE_CLIENT_ID=
RAG_EMBEDDING_PROVIDER=local
RAG_OLLAMA_EMBEDDING_MODEL=embeddinggemma
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
RAG_MIN_SCORE=0.5
RAG_OCR_LANGUAGES=spa+eng
```

Genera una clave local propia y un secreto de sesión diferente.
`STOCKASSISTANT_API_KEYS` admite varias claves separadas por comas;
`VITE_STOCKASSISTANT_API_KEY`, si se utiliza, debe contener una sola clave aceptada por
el backend. El acceso habitual del portal utiliza la sesión del usuario. El Dockerfile
de Nginx solo recibe `VITE_GOOGLE_CLIENT_ID` como argumento: la variable de clave Vite
se transmite al servicio de desarrollo, no automáticamente al portal compilado. En
Configuración también puede introducirse una clave local para ese navegador.

Los valores de PostgreSQL y pgAdmin son los predeterminados locales. Para una
instalación compartida, utiliza contraseñas propias; conserva el `.env` fuera de Git.
Cambiar las variables de PostgreSQL después de crear el volumen no modifica
automáticamente las credenciales de la base existente. La cuenta inicial del portal se
mantiene como se indica en el apartado 6.

No necesitas claves de OpenAI, SerpAPI ni configuración de Google para iniciar sesión
con el usuario local.

## 4. Construir y arrancar

Desde la raíz del proyecto:

```powershell
docker compose --env-file $envFile -f $compose config --quiet
docker compose --env-file $envFile -f $compose up -d --build
docker compose --env-file $envFile -f $compose ps
```

El primer arranque puede tardar varios minutos. Compose crea PostgreSQL y espera a que
esté saludable; después inicia la API y, cuando esta responde, los frontends. También
inicia pgAdmin y Qdrant. La imagen de la API instala PyTorch `2.8.0` para CPU, por lo
que no necesita GPU. La descarga del modelo de embeddings se realiza al primer uso
vectorial, no al iniciar sesión.

En un volumen nuevo, PostgreSQL ejecuta automáticamente `docker/init-scripts/init.sql`
para crear el esquema y la cuenta inicial. Además, el backend local aplica el bloque
canónico de esquema al arrancar y pone en marcha los workers de conocimiento y
automatizaciones. En una instalación existente, realiza el respaldo y la revisión del
apartado 9 **antes de arrancar la versión nueva**, ya que ese arranque puede migrar la
base. No es necesario ejecutar generadores ni cargadores para entrar al portal.

## 5. Verificar los servicios

```powershell
docker compose --env-file $envFile -f $compose ps
docker compose --env-file $envFile -f $compose logs --tail 80 backend postgres
Invoke-RestMethod 'http://localhost:8000/health'
```

La API debe devolver `status: healthy`. Confirma además que PostgreSQL y el backend
aparecen saludables y prueba el inicio de sesión: `/health` por sí solo no comprueba
todas las operaciones de la base ni las integraciones externas.

| Servicio | Dirección local | Uso |
| --- | --- | --- |
| Portal Nginx | [http://localhost:8080](http://localhost:8080) | Uso habitual de la app compilada. |
| Frontend Vite | [http://localhost:5173](http://localhost:5173) | Desarrollo con recarga de cambios. |
| API Swagger | [http://localhost:8000/docs](http://localhost:8000/docs) | Consultar y probar endpoints. |
| API ReDoc | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Documentación alternativa. |
| pgAdmin | [http://localhost:5050](http://localhost:5050) | Administración de PostgreSQL. |
| PostgreSQL | `localhost:5433` | Conexión desde clientes del equipo. |
| Qdrant | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) | Colecciones vectoriales; HTTP en 6333 y gRPC en 6334. |

Si cambias `HTTP_PORT`, adapta la dirección del portal Nginx.

## 6. Entrar y realizar la configuración inicial

Abre el portal Nginx e inicia sesión con la cuenta de desarrollo documentada en el
repositorio:

- **Correo:** `admin@stockassistant.app`
- **Contraseña:** `Jupiter!2026Stock`

Después del acceso, revisa los datos maestros, crea o comprueba bodegas, proveedores y
productos, y registra las operaciones de inventario que necesites. Puedes importar
productos, clientes y proveedores desde sus pantallas. Las áreas de ventas incluyen
pedidos y facturas; las consultas incluyen chat con memoria y asistente RAG.

El catálogo está unificado en `public.products`; `public.productos` es una vista
actualizable de compatibilidad. Las operaciones utilizan el ID interno y las relaciones
analíticas el código textual `product_id`. Compartir catálogo no genera automáticamente
historial analítico, existencias ni ventas.

Las automatizaciones iniciales están desactivadas. Revisa objetivos, alcance, horarios,
presupuestos y permisos desde el centro de control y el editor de reglas. Existen modos
de observación, asistido y automático limitado; la confirmación de operaciones físicas
sigue siendo específica. Consulta
[Agentes operativos](Documentación/Agentes-Operativos.md).

Para pgAdmin, los valores predeterminados son `admin@jupiter.example.com` y `admin123`,
salvo cambios en `.env`. Al registrar una conexión desde pgAdmin utiliza servidor
`postgres`, puerto `5432`, base `supply_chain`, usuario `admin` y la contraseña de
PostgreSQL configurada. Desde una herramienta instalada en Windows utiliza `localhost` y
puerto `5433`.

## 7. Configurar IA y servicios externos, si los necesitas

La configuración Docker contempla estas variables opcionales en su `.env`:

| Variable | Finalidad |
| --- | --- |
| `OPENAI_API_KEY` | Credencial para las funciones que usan OpenAI. |
| `SERPAPI_API_KEY` | Credencial para las búsquedas externas compatibles con SerpAPI. |
| `OLLAMA_URL` | URL del servidor Ollama; por defecto `http://host.docker.internal:11434/api/generate`. |
| `GOOGLE_CLIENT_ID` | Identificador de cliente Google que utiliza el backend. |
| `VITE_GOOGLE_CLIENT_ID` | Identificador correspondiente para el frontend. |
| `AI_PROVIDER` | `auto`, `ollama` u `openai` para generación. |
| `OLLAMA_MODEL`, `OPENAI_MODEL` | Modelos de generación del proveedor correspondiente. |
| `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_THINK` | Espera y opción de razonamiento de Ollama. |
| `RAG_EMBEDDING_PROVIDER` | `local`, `ollama`, `openai` o `auto` para embeddings documentales. |
| `RAG_OLLAMA_EMBEDDING_MODEL`, `OPENAI_EMBEDDING_MODEL` | Modelos de embeddings remotos. |
| `RAG_MIN_SCORE`, `RAG_OCR_LANGUAGES` | Umbral RAG e idiomas OCR; la imagen incluye español e inglés. |

Para habilitar servicios externos, reemplaza únicamente las variables necesarias con
**claves de tus propias cuentas**. Deja vacías las de los servicios que no utilices.
Ejemplo de marcadores, no credenciales reales:

```dotenv
OPENAI_API_KEY=REEMPLAZA_CON_TU_CLAVE_OPENAI
SERPAPI_API_KEY=REEMPLAZA_CON_TU_CLAVE_SERPAPI
```

No introduzcas claves de OpenAI o SerpAPI en variables `VITE_*`: estas se entregan al
navegador. La clave local de StockAssistant es distinta de las claves de los
proveedores.

Para Ollama necesitas un servidor accesible desde el contenedor y el modelo que solicite
la función utilizada. `ai_service.py` establece `qwen3:14b` como modelo predeterminado;
los recursos necesarios dependen del modelo. Compose no instala ni inicia Ollama.

El inicio de sesión Google requiere configurar también los orígenes autorizados en el
proveedor. El acceso local con contraseña puede seguir utilizándose.

Tras modificar variables de la API o del frontend de desarrollo:

```powershell
docker compose --env-file $envFile -f $compose up -d backend frontend
```

Si modificas `VITE_GOOGLE_CLIENT_ID`, reconstruye el portal compilado:

```powershell
docker compose --env-file $envFile -f $compose up -d --build nginx
```

La sección de configuración permite revisar el estado de las integraciones. El Compose
actual sí transmite `OLLAMA_MODEL`, `OPENAI_MODEL`, `AI_PROVIDER` y las opciones RAG
de la tabla. Otras variables solo llegan al contenedor si se declaran en `environment`;
no basta con añadirlas al `.env`. Un `restart` no actualiza el entorno: utiliza `up -d`
para recrear los servicios afectados.

### Preparar la base de conocimiento

Con Qdrant disponible, abre **Configuración → Base de conocimiento**, crea documentos o
carga sus archivos y comprueba el estado de indexación. El worker recupera documentos
pendientes. La imagen instala los paquetes PDF y Tesseract necesarios para OCR en
español e inglés. Después consulta **Asistente RAG** y comprueba las citas de la
respuesta.

Con `RAG_EMBEDDING_PROVIDER=local`, el primer uso descarga el modelo local. Para
`ollama`, instala también el modelo de embeddings indicado; para `openai`, configura
tu propia clave. Al cambiar de proveedor o modelo, revisa el estado y reindexa los
documentos para el nuevo perfil. Cambiar el modelo no convierte los vectores existentes.

## 8. Detener, reiniciar y conservar datos

Para detener temporalmente y volver a iniciar los contenedores existentes:

```powershell
docker compose --env-file $envFile -f $compose stop
docker compose --env-file $envFile -f $compose start
```

Para retirar los contenedores conservando los volúmenes:

```powershell
docker compose --env-file $envFile -f $compose down
```

Para volver a crearlos:

```powershell
docker compose --env-file $envFile -f $compose up -d
```

PostgreSQL, pgAdmin y Qdrant guardan sus datos en volúmenes Docker; los vectores
utilizan `qdrant_data`. Los archivos de la aplicación se guardan en
`BackEnd/apps/MonoliticDataStructure/app/data`, montado como `/app/data` en el backend.
No añadas `-v` a `down` si quieres conservar los volúmenes y la base de datos. La caché
del modelo de embeddings está dentro del contenedor de la API: recrearlo puede requerir
descargar el modelo de nuevo.

## 9. Actualizar una instalación existente

El backend local aplica el esquema al arrancar. Antes de iniciar una versión nueva,
detén los escritores y crea un respaldo. Desde la raíz y con PostgreSQL en ejecución:

```powershell
docker compose --env-file $envFile -f $compose stop nginx frontend backend
$backupDir = 'BackEnd/apps/MonoliticDataStructure/app/data/backups'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$backupFile = Join-Path $backupDir ('jupiter-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump')
docker compose --env-file $envFile -f $compose exec -T postgres pg_dump -U admin -d supply_chain -Fc -f /tmp/jupiter-backup.dump
docker compose --env-file $envFile -f $compose cp postgres:/tmp/jupiter-backup.dump $backupFile
docker compose --env-file $envFile -f $compose exec -T postgres pg_restore -l /tmp/jupiter-backup.dump
```

Adapta el usuario y la base si cambiaste los predeterminados. Comprueba el código de
salida de cada comando Docker y que el archivo se haya copiado. Leer el índice del
volcado no verifica su recuperación: ensaya la restauración en una base aislada antes de
una migración importante. Respalda también `app/data`, los archivos de conocimiento y
los índices si necesitas recuperarlos. Obtén después la versión de código que vayas a
instalar, conservando `.env` y datos locales.

### Migración del catálogo y esquema canónico

La versión actual unifica las tablas antiguas en `products` y transforma `productos` en
una vista. Revisa [Unificación del catálogo](infra/PRODUCTS-UNIFICATION.md) y ensaya
sobre una copia. La migración conserva IDs operativos y códigos analíticos; conflictos o
dependencias no previstas causan error y rollback. Requiere propiedad o permisos DDL
sobre los objetos afectados.

Para ensayar y aplicar desde Windows, utiliza Python 3.11 en un entorno con `psycopg2`,
como el entorno de migraciones del apartado AWS. Configura `JUPITER_MIGRATION_DSN` de
forma privada para la base correcta, con `localhost:5433` desde Windows. El script no
carga automáticamente el `.env` de Compose. Desde la raíz:

```powershell
python infra/scripts/apply-schema.py --legacy-timezone UTC --check-only
python infra/scripts/apply-schema.py --legacy-timezone UTC
```

Sustituye `UTC` por la zona en la que se escribieron realmente las fechas históricas
`TIMESTAMP`. `--check-only` ejecuta el esquema y revierte la transacción; no sustituye
el respaldo ni las pruebas funcionales. La segunda orden confirma los cambios. Detente
si el ensayo falla. Mantén los escritores parados durante ambas operaciones. Para usar
únicamente Docker, el documento de unificación describe la alternativa mediante `psql`,
configurando la misma zona histórica en la conexión.

Después de aplicar y verificar el esquema:

```powershell
docker compose --env-file $envFile -f $compose up -d --build
docker compose --env-file $envFile -f $compose ps
Invoke-RestMethod 'http://localhost:8000/health'
```

Reaplicar el esquema conserva las credenciales y el estado de los usuarios existentes;
no restablece su contraseña. Revisa login, productos, inventario, compras y ventas antes
de reabrir el servicio. Volver a una imagen anterior no revierte los cambios de datos;
la recuperación debe planificarse con el respaldo.

### Actualización desde Configuración

Una instalación que ya arranca permite consultar y aplicar el `init.sql` incluido en el
servidor desde **Estado de integraciones**, con checksum, progreso e historial. El
endpoint exige sesión válida y cuenta activa no caducada; actualmente
`SCHEMA_ADMIN_USER_IDS` no restringe esa autorización. La conexión necesita permisos
sobre el esquema; puede configurarse `JUPITER_MIGRATION_DSN` para migrar la misma base.
En AWS utiliza el proceso de despliegue descrito más adelante.

### Actualizar las dependencias vectoriales

La recarga automática del código no instala paquetes Python nuevos. Tras los cambios de
`requirements/api.txt` o del Dockerfile, reconstruye y recrea el backend. Actualiza
también Qdrant y refresca el proxy si cambia la dirección interna de la API:

```powershell
docker compose --env-file $envFile -f $compose build backend
docker compose --env-file $envFile -f $compose up -d --no-deps backend qdrant
docker compose --env-file $envFile -f $compose ps
Invoke-RestMethod 'http://localhost:8000/health'
docker compose --env-file $envFile -f $compose exec -T nginx nginx -s reload
docker compose --env-file $envFile -f $compose exec -T backend python -m pip check
```

Espera a que la API responda antes de probar el portal. Las versiones declaradas
actualmente son Qdrant `1.19.1`, `qdrant-client==1.19.0`, `numpy==1.26.4` y
`pandas==2.2.3`. No sustituyas la imagen Qdrant por `latest` sin comprobar la
compatibilidad de su cliente.

## 10. Desarrollo del frontend fuera de Docker, opcional

Para editar con Vite instalado en el equipo, utiliza Node.js 20, la misma versión
principal que las imágenes del proyecto. Mantén PostgreSQL y la API en Docker y detén el
Vite del contenedor para liberar su puerto:

```powershell
docker compose --env-file $envFile -f $compose up -d postgres backend
docker compose --env-file $envFile -f $compose stop frontend
Set-Location Frontend
npm ci --legacy-peer-deps
npm run dev -- --host 127.0.0.1 --port 5173
```

Vite reenvía `/api` y `/media` a `http://localhost:8000` por defecto. El parámetro
`--legacy-peer-deps` reproduce la instalación del Dockerfile para las dependencias
heredadas.

En otra terminal, situada en `Frontend`, puedes comprobar tipos y compilar:

```powershell
npx tsc --noEmit
npm run build
```

La compilación local genera `Frontend/dist`. Para actualizar el portal Nginx de Docker,
vuelve a la raíz y ejecuta
`docker compose --env-file $envFile -f $compose up -d --build nginx`. La API también
monta su código fuente y utiliza recarga automática en el Compose incluido.

## 11. Indexar y consultar productos en Qdrant

La instalación no garantiza un catálogo vectorial precargado. Para los productos del
portal, utiliza **Lista de productos → Sincronizar Qdrant**: indexa desde PostgreSQL y
muestra el progreso. Las altas, ediciones, cambios de estado e importaciones CSV también
intentan sincronizar vectores y comunican si falla esa fase. Un fallo vectorial puede
dejar productos guardados en SQL pendientes de sincronizar.

Como alternativa independiente, puedes indexar un CSV directamente, sin importar sus
filas a PostgreSQL. Prepara un archivo UTF-8 con estas columnas:

```csv
product_id,product_name,description,product_category,brand,sku
DEMO-001,Ordenador portátil,Ordenador con pantalla y teclado para trabajar,Electronics,Demo,DEMO-SKU-001
```

Guárdalo en `BackEnd/apps/MonoliticDataStructure/app/data/generated/products.csv`,
creando las carpetas si no existen. Usa tus datos para indexar el catálogo real. El
fichero queda disponible en `/app/data/generated/products.csv` dentro del backend.

```powershell
docker compose --env-file $envFile -f $compose exec -T backend python -m src.vector_store.product_indexer --csv /app/data/generated/products.csv --batch-size 128
$apiHeaders = @{ 'X-API-Key' = 'REEMPLAZA_CON_TU_CLAVE_API_LOCAL' }
Invoke-RestMethod 'http://localhost:8080/api/v1/products/semantic-search?q=ordenador&limit=5&category=Electronics' -Headers $apiHeaders
```

Sustituye el marcador de `$apiHeaders` por tu clave local configurada en
`STOCKASSISTANT_API_KEYS`. También puedes autenticar la consulta con un token de sesión
válido. Adapta la URL si cambiaste `HTTP_PORT`.

Con el proveedor local, la primera indexación descarga desde Hugging Face el modelo
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Produce vectores
normalizados de 384 dimensiones y utiliza similitud coseno. El comando vuelve a escribir
los mismos identificadores sin duplicarlos; no elimina puntos de productos que hayas
retirado del CSV.

`pyproject.toml` declara también el comando `index-products`, disponible cuando el
proyecto se instala como paquete Python. La imagen Docker actual permite usar
directamente el módulo mostrado arriba.

| Ajuste | Valor actual |
| --- | --- |
| `QDRANT_URL` | `http://qdrant:6333` en Compose; `http://localhost:6333` por defecto fuera de Docker. |
| `QDRANT_COLLECTION` | `products`. |
| `EMBEDDING_DIMENSION` | `384`. |
| `VECTOR_SEARCH_LIMIT` | `10`; la ruta HTTP admite `limit` de 1 a 50. |

Estos ajustes están definidos en `src/api/config.py`. Compose transmite explícitamente
`QDRANT_URL`; para configurar los demás de forma persistente debes declararlos en
`environment` del backend. Cambiar el modelo o la dimensión requiere un índice
compatible; no reutilices vectores de otro modelo.

La consulta necesita `q` de al menos dos caracteres. `category` es un filtro exacto y
opcional. La respuesta contiene `query` e `items`; sin colección devuelve `items: []`.
Indexar este CSV directamente no carga PostgreSQL. Los productos del portal usan la
identidad vectorial `operational:{id}`; evita representar los mismos productos mediante
cargas independientes con identidades distintas.

## 12. Repetir las comprobaciones

Desde la raíz, copia las pruebas al contenedor; la imagen de ejecución no las incluye.
Para comprobar reglas de inventario sin servicios adicionales:

```powershell
docker compose --env-file $envFile -f $compose cp BackEnd/apps/MonoliticDataStructure/app/tests backend:/app/tests
docker compose --env-file $envFile -f $compose exec -T backend python -m unittest discover -s /app/tests -p test_inventory_rules.py -v
```

La integración vectorial utiliza `TestClient` y necesita `httpx`, declarado en
`requirements/dev.txt` y no explícitamente en `api.txt`. En un contenedor de desarrollo
o pruebas preparado con esas dependencias, y con Qdrant y el modelo local disponibles:

```powershell
docker compose --env-file $envFile -f $compose exec -T -e RUN_VECTOR_INTEGRATION=1 -e RAG_EMBEDDING_PROVIDER=local backend python -m unittest discover -s /app/tests -p test_vector_store.py -v
```

La prueba usa productos ficticios y una colección temporal que elimina al terminar.
Comprueba indexación, idempotencia, ranking, categoría, límite y validación HTTP. No
ejecutes la suite HTTP/SQL completa contra la base de trabajo:
`test_jupiter_integration.py` requiere una base desechable indicada por
`JUPITER_TEST_DB` y terminada en `_test`. Las pruebas de unificación PostgreSQL también
crean bases aisladas y necesitan permisos para ello.

Completa la comprobación entrando al portal, consultando productos e inventario,
revisando pedidos y facturas y, si los has configurado, comprobando IA y RAG con citas.
Pruebas antiguas no certifican esta versión ni tus proveedores externos. Esta
actualización de la guía se basa en los archivos del repositorio; no se ha ejecutado una
instalación nueva para redactarla.

## Problemas habituales

| Problema | Comprobación o solución |
| --- | --- |
| Docker no conecta | Inicia Docker Desktop y comprueba `docker info`. |
| Puerto ocupado | Detén el proceso que lo usa; para Nginx puedes cambiar `HTTP_PORT` en `.env`. Los demás puertos están definidos directamente en Compose. |
| Vite todavía no abre | Revisa `docker compose --env-file $envFile -f $compose logs --tail 80 frontend`; en el primer inicio debe instalar dependencias. |
| API no saludable o error 502 | Revisa los logs de `backend` y `postgres`, su estado y las credenciales. |
| Login tarda minutos y termina en 504 | Nginx tiene un tiempo de espera de respuesta de 300 segundos. Comprueba primero `/health` y los logs de la API; un proceso de recarga activo no garantiza que el backend haya arrancado. |
| `No module named qdrant_client` | Reconstruye y recrea `backend`; reiniciarlo o recargar el código no instala las dependencias. |
| `numpy.dtype size changed` | Usa las versiones de NumPy y pandas fijadas en `requirements/api.txt` y reconstruye la imagen. `pip check` no detecta por sí solo esta incompatibilidad binaria. |
| API funciona en 8000, pero 8080 devuelve 502 tras recrearla | Ejecuta `docker compose --env-file $envFile -f $compose exec -T nginx nginx -s reload` para resolver de nuevo la dirección interna del backend. |
| Búsqueda semántica vacía | Revisa el resultado de indexación, ejecuta Sincronizar Qdrant y comprueba la categoría exacta. Un producto guardado en SQL puede tener su vector pendiente. |
| Primera búsqueda o indexación lenta | El primer uso descarga y carga el modelo. Comprueba la conexión a Hugging Face; la caché puede perderse al recrear el contenedor. |
| El usuario inicial no puede entrar | Comprueba si estás usando un volumen anterior sin la inicialización correspondiente. Sigue el apartado de actualización con respaldo antes de aplicar SQL. |
| Error 401 al consumir rutas protegidas | Inicia sesión de nuevo o utiliza tu propia clave local en `X-API-Key`, aceptada por `STOCKASSISTANT_API_KEYS`. Algunas acciones también exigen permisos específicos. |
| No aparecen cambios en el portal 8080 | Reconstruye `nginx`; el puerto 5173 corresponde al frontend con recarga de desarrollo. |
| IA o fuentes externas no responden | Revisa credenciales, disponibilidad del proveedor y conectividad de Ollama desde Docker. |
| Hay tablas sin datos o indicadores vacíos | Compartir catálogo no crea historial comercial ni stock: importa datos o registra operaciones en el dominio correspondiente. |

Los procedimientos opcionales de HTTPS y AWS se describen a continuación.



## 13. HTTPS local, opcional

Necesitas certificados propios válidos para el nombre que vayas a utilizar. Guarda
`cert.crt` y `private.key` en una carpeta del equipo y añade su ruta absoluta al `.env`
de Compose:

```dotenv
TLS_CERTS_DIR=C:/ruta/a/tus/certificados
```

Adapta la ruta, comprueba que ambos archivos existen y que el puerto `443` está libre.
Desde la raíz:

```powershell
$httpsCompose = 'BackEnd/apps/MonoliticDataStructure/app/docker/docker-compose.https.yml'
docker compose --env-file $envFile -f $compose -f $httpsCompose config --quiet
docker compose --env-file $envFile -f $compose -f $httpsCompose up -d --build nginx
```

El override monta `Frontend/nginx.tls.conf` y los certificados en Nginx. Accede a
[https://localhost](https://localhost) si tu certificado incluye ese nombre, o al nombre
cubierto por el certificado. HTTP redirige a HTTPS en el puerto estándar 443. Utiliza
ambos archivos Compose en las siguientes operaciones de ese despliegue. Si activas
Google, incluye también el origen HTTPS correspondiente en la configuración OAuth.

Para volver a HTTP local, recrea Nginx usando solo el archivo base:

```powershell
docker compose --env-file $envFile -f $compose up -d --force-recreate nginx
```

## 14. Despliegue AWS, opcional

La variante AWS utiliza frontend en S3 privado y CloudFront, API en Lambda mediante
Function URL, imágenes en ECR, PostgreSQL en RDS, archivos en S3, índices en S3 Vectors
y secretos en SSM. **No se instala ejecutando el Compose local.** Terraform referencia
recursos existentes y los scripts contienen nombres de una instalación concreta: adapta
nombres, región y cuenta a tus propios recursos antes de utilizarlos.

### Requisitos y configuración

- Cuenta AWS propia y acceso mediante roles o credenciales de tu cuenta; no copies
  claves de otra instalación.
- RDS y base de aplicación accesibles, roles `app` y `migrator`, Lambda con Function
  URL, repositorio ECR y bucket frontend existentes, además de los recursos definidos
  por Terraform.
- Terraform `>= 1.10` y proveedor AWS `>= 6.0`, como declara `infra/envs/prod/main.tf`; AWS CLI, Docker con Buildx y Node.js 20 para operaciones manuales.
- Backend de estado Terraform configurado a partir de
  `infra/envs/prod/backend.hcl.example`, con valores propios. Revisa los recursos y
  políticas de `infra/bootstrap/`, `infra/envs/prod/` e `infra/iam/`.
- Entorno GitHub `production` con el rol OIDC de despliegue y variables como
  `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `DB_MIGRATION_HOST` y `DB_MIGRATION_DATABASE`,
  además de las variables frontend que consume el workflow. Consulta
  [.github/workflows/deploy-aws.yml](.github/workflows/deploy-aws.yml) para la lista
  vigente.

El backend carga secretos desde `/stockassistant/prod` cuando `SECRETS_FROM_SSM=true` y
se ejecuta en Lambda. Configura los parámetros con valores de tu propia instalación:

| Parámetro bajo `/stockassistant/prod/` | Valor que debes proporcionar |
| --- | --- |
| `api_keys` | Tu clave API local de StockAssistant o varias separadas por comas. |
| `session_secret` | Tu secreto de sesión independiente. |
| `openai_api_key` | Tu clave de OpenAI. |
| `serpapi_api_key` | Tu clave de SerpAPI. |
| `google_client_id` | Tu identificador OAuth de Google. |
| `db/app_password` | Contraseña de tu rol PostgreSQL `app`. |
| `db/migrator_password` | Contraseña del rol de migraciones usada por el despliegue. |
| `db/migration_dsn` | Conexión de migración a la misma base para actualizar desde Configuración. |

El cargador SSM requiere que existan los parámetros que intenta leer y no sobrescribe
variables de entorno que ya estén definidas. Los servicios opcionales pueden mantenerse
sin credencial según la configuración elegida, pero no omitas un parámetro que el
cargador vaya a solicitar. Guarda los secretos como `SecureString` y concede al rol
correspondiente los permisos de lectura y descifrado necesarios. No introduzcas claves
de proveedores en el frontend.

Revisa `infra/scripts/set-lambda-env.py` como referencia de configuración, antes de
ejecutarlo: contiene identificadores concretos. La variante usa
`VECTOR_BACKEND=s3vectors`, `RAG_EMBEDDING_PROVIDER=openai`, `DOCUMENTS_BUCKET` y
`AWS_LWA_PASS_THROUGH_PATH=/internal/index`. Los índices Terraform tienen 1536
dimensiones por defecto para `text-embedding-3-small`; deben coincidir con los
embeddings utilizados. El rol Lambda necesita acceso a SSM, archivos, vectores y
auto-invocación para procesar conocimiento pendiente. El arranque Lambda omite DDL y
workers persistentes; no equivale al proceso local de automatizaciones.

### Preparar y aplicar las migraciones

La preparación administrativa de permisos se realiza una vez como `dbadmin`, conectado
a la base de aplicación, mediante
[05-migration-permissions.sql](infra/sql/05-migration-permissions.sql). Revisa antes
[Migraciones PostgreSQL](infra/sql/migrations/README.md): configura propiedad
compartida mediante `migrator`, herencia para `app`, extensiones y privilegios
futuros. Las conexiones existentes deben reconectarse. El ejecutor de CD no puede
administrar estos roles por sí solo.

Para comprobar los archivos de migración desde Windows, puedes crear un entorno Python
independiente. Desde la raíz:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r infra/scripts/requirements-migrations.txt
.\.venv\Scripts\python.exe infra/scripts/migrate.py --check
```

Esta comprobación valida los archivos sin conectarse a la base; no aplica migraciones.
Para ejecutar `apply-schema.py` del apartado 9 con ese entorno, sustituye `python` por
`.\.venv\Scripts\python.exe` en sus comandos.

El workflow **Deploy AWS** se ejecuta desde `master` y permite los destinos `all`,
`backend`, `frontend` y `migrations`. En el flujo de backend construye y publica la
imagen, valida el historial, aplica el bloque canónico pendiente de `init.sql` y las
migraciones versionadas y después actualiza Lambda. Publica el frontend según los
cambios o el destino elegido.

Los hashes del esquema se comparten con Configuración; las migraciones versionadas
registran checksum y versión. No edites archivos ya aplicados: añade una nueva versión.
Se usa bloqueo asesor y una transacción por aplicación. Si falla una migración
posterior, las anteriores confirmadas permanecen aplicadas. El runner necesita acceso
real a RDS y TLS `verify-full`; no abre puertos ni corrige la red automáticamente.

Tras el despliegue verifica acceso por CloudFront, login, productos, imágenes,
operaciones comerciales y RAG. Comprueba por separado qué automatizaciones tienen un
mecanismo de ejecución en tu entorno Lambda. La instalación AWS y la local son
independientes: no se transfieren automáticamente sus datos, archivos ni vectores.
