# Instalación local de Proyecto Jupiter

Esta guía utiliza el Docker Compose incluido en el proyecto. Los comandos están escritos para **PowerShell en Windows**, desde la raíz del repositorio. Docker ejecuta la API, PostgreSQL y los dos modos del frontend; no hace falta instalar Python ni Node.js en el equipo para este arranque.

Para conocer los módulos y la estructura, consulta [Contenido del proyecto](readmeContenido.md).

## 1. Preparar el equipo

1. Instala Docker Desktop con soporte para contenedores Linux y WSL 2, y abre Docker Desktop.
2. Instala Git si vas a obtener el código mediante clonación; también puedes utilizar una copia del proyecto ya descargada.
3. Necesitas conexión a Internet en el primer arranque para descargar imágenes y dependencias.
4. Comprueba que los puertos `8080`, `5173`, `8000`, `5433` y `5050` estén disponibles.

Verifica Docker en PowerShell:

```powershell
docker --version
docker compose version
docker info
```

`docker info` debe conectar con el motor. Si falla, inicia Docker Desktop y espera a que esté listo.

## 2. Abrir el proyecto

Si aún no tienes el código, clona la URL de tu repositorio o extrae la copia descargada. Abre PowerShell en la carpeta que contiene `Frontend`, `BackEnd` y `README.md`.

En esta instalación la ruta es:

```powershell
Set-Location 'D:\MasterPontiaIA\ProyectoupiterV3'
$compose = 'BackEnd/apps/MonoliticDataStructure/app/docker/docker-compose.yml'
Test-Path $compose
```

Adapta la ruta a tu equipo. El último comando debe devolver `True`. Si abres otra terminal, vuelve a situarte en la raíz y a definir `$compose`.

## 3. Revisar la configuración local

Compose tiene valores predeterminados suficientes para el acceso local con contraseña. Lee sus variables desde el archivo `.env` situado junto a `docker-compose.yml`:

```text
BackEnd/apps/MonoliticDataStructure/app/docker/.env
```

Si ya existe, conserva su contenido y modifica solo las variables necesarias. Si no existe, puedes arrancar con los valores predeterminados o crear un archivo de texto `.env` con este ejemplo local:

```dotenv
POSTGRES_USER=admin
POSTGRES_PASSWORD=admin123
POSTGRES_DB=supply_chain
PGADMIN_DEFAULT_EMAIL=admin@jupiter.example.com
PGADMIN_DEFAULT_PASSWORD=admin123
HTTP_PORT=8080
TZ=Europe/Madrid
STOCKASSISTANT_API_KEYS=dev-jupiter-key
VITE_STOCKASSISTANT_API_KEY=dev-jupiter-key
STOCKASSISTANT_SESSION_SECRET=proyecto-jupiter-dev-secret
STOCKASSISTANT_SESSION_TTL_MINUTES=120
AUTOMATION_WORKER_ENABLED=true
AUTOMATION_WORKER_POLL_SECONDS=60
```

Estos son valores de desarrollo. Para una instalación compartida, utiliza contraseñas y un secreto de sesión propios; no publiques el `.env`. Cambiar las variables de PostgreSQL después de crear el volumen no modifica automáticamente las credenciales de la base existente.

No necesitas claves de OpenAI, SerpAPI ni configuración de Google para iniciar sesión con el usuario local.

## 4. Construir y arrancar

Desde la raíz del proyecto:

```powershell
docker compose -f $compose config --quiet
docker compose -f $compose up -d --build
docker compose -f $compose ps
```

El primer arranque puede tardar varios minutos. Compose crea PostgreSQL y espera a que esté saludable; después inicia la API y, cuando esta responde, los frontends. También inicia pgAdmin.

En un volumen nuevo, PostgreSQL ejecuta automáticamente `docker/init-scripts/init.sql` para crear el esquema y la cuenta inicial. No es necesario ejecutar generadores ni cargadores para entrar al portal.

## 5. Verificar los servicios

```powershell
docker compose -f $compose ps
docker compose -f $compose logs --tail 80 backend postgres
Invoke-RestMethod 'http://localhost:8000/health'
```

La API debe devolver `status: healthy`. Confirma además que PostgreSQL y el backend aparecen saludables y prueba el inicio de sesión: `/health` por sí solo no comprueba todas las operaciones de la base ni las integraciones externas.

| Servicio | Dirección local | Uso |
| --- | --- | --- |
| Portal Nginx | [http://localhost:8080](http://localhost:8080) | Uso habitual de la app compilada. |
| Frontend Vite | [http://localhost:5173](http://localhost:5173) | Desarrollo con recarga de cambios. |
| API Swagger | [http://localhost:8000/docs](http://localhost:8000/docs) | Consultar y probar endpoints. |
| API ReDoc | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Documentación alternativa. |
| pgAdmin | [http://localhost:5050](http://localhost:5050) | Administración de PostgreSQL. |
| PostgreSQL | `localhost:5433` | Conexión desde clientes del equipo. |

Si cambias `HTTP_PORT`, adapta la dirección del portal Nginx.

## 6. Entrar y realizar la configuración inicial

Abre el portal Nginx e inicia sesión con la cuenta de desarrollo documentada en el repositorio:

- **Correo:** `admin@stockassistant.app`
- **Contraseña:** `Jupiter!2026Stock`

Después del acceso, revisa los datos maestros, crea o comprueba bodegas, proveedores y productos, y registra las operaciones de inventario que necesites. Los indicadores se irán alimentando de los datos reales. El catálogo analítico `/api/v1` y el operativo del portal no se sincronizan automáticamente.

Las automatizaciones iniciales están pausadas. Puedes revisarlas desde el centro ejecutivo antes de activarlas.

Para pgAdmin, los valores predeterminados son `admin@jupiter.example.com` y `admin123`, salvo cambios en `.env`. Al registrar una conexión desde pgAdmin utiliza servidor `postgres`, puerto `5432`, base `supply_chain`, usuario `admin` y la contraseña de PostgreSQL configurada. Desde una herramienta instalada en Windows utiliza `localhost` y puerto `5433`.

## 7. Configurar IA y servicios externos, si los necesitas

La configuración Docker contempla estas variables opcionales en su `.env`:

| Variable | Finalidad |
| --- | --- |
| `OPENAI_API_KEY` | Credencial para las funciones que usan OpenAI. |
| `SERPAPI_API_KEY` | Credencial para las búsquedas externas compatibles con SerpAPI. |
| `OLLAMA_URL` | URL del servidor Ollama; por defecto `http://host.docker.internal:11434/api/generate`. |
| `GOOGLE_CLIENT_ID` | Identificador de cliente Google que utiliza el backend. |
| `VITE_GOOGLE_CLIENT_ID` | Identificador correspondiente para el frontend. |

Para Ollama necesitas un servidor accesible desde el contenedor y el modelo que solicite la función utilizada. `ai_service.py` establece `qwen3:14b` como modelo predeterminado; los recursos necesarios dependen del modelo. Compose no instala ni inicia Ollama.

El inicio de sesión Google requiere configurar también los orígenes autorizados en el proveedor. El acceso local con contraseña puede seguir utilizándose.

Tras modificar variables de la API o del frontend de desarrollo:

```powershell
docker compose -f $compose up -d backend frontend
```

Si modificas `VITE_GOOGLE_CLIENT_ID`, reconstruye el portal compilado:

```powershell
docker compose -f $compose up -d --build nginx
```

La sección de configuración del portal permite revisar el estado de las integraciones. Poner una variable en `.env` solo llega al contenedor si Compose la declara: por ejemplo, el Compose actual no transmite `OLLAMA_MODEL`.

## 8. Detener, reiniciar y conservar datos

Para detener temporalmente y volver a iniciar los contenedores existentes:

```powershell
docker compose -f $compose stop
docker compose -f $compose start
```

Para retirar los contenedores conservando los volúmenes:

```powershell
docker compose -f $compose down
```

Para volver a crearlos:

```powershell
docker compose -f $compose up -d
```

PostgreSQL y pgAdmin guardan sus datos en volúmenes Docker. Los archivos de la aplicación se guardan en `BackEnd/apps/MonoliticDataStructure/app/data`, montado como `/app/data` en el backend. No añadas `-v` a `down` si quieres conservar los volúmenes y la base de datos.

## 9. Actualizar una instalación existente

Antes de aplicar cambios de esquema, crea un respaldo. Este ejemplo utiliza los nombres de servicio y las credenciales predeterminadas; adapta usuario y base si los cambiaste:

```powershell
$backupDir = 'BackEnd/apps/MonoliticDataStructure/app/data/backups'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$backupFile = Join-Path $backupDir ('jupiter-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump')
docker compose -f $compose exec -T postgres pg_dump -U admin -d supply_chain -Fc -f /tmp/jupiter-backup.dump
docker compose -f $compose cp postgres:/tmp/jupiter-backup.dump $backupFile
```

Comprueba que ambos comandos Docker terminan correctamente y que el respaldo se ha copiado. Los scripts de inicialización no se ejecutan otra vez sobre un volumen ya creado. Si la versión incorporada requiere aplicar el esquema completo, utiliza:

```powershell
docker compose -f $compose cp BackEnd/apps/MonoliticDataStructure/app/docker/init-scripts/init.sql postgres:/tmp/jupiter-init.sql
docker compose -f $compose exec -T postgres psql -U admin -d supply_chain -v ON_ERROR_STOP=1 -f /tmp/jupiter-init.sql
docker compose -f $compose up -d --build
```

Reaplicar `init.sql` restablece las credenciales y el estado activo del administrador inicial. Consulta las [notas de integración](Documentación/Integracion-Proyecto-Jupiter.md) antes de migrar datos existentes.

## 10. Desarrollo del frontend fuera de Docker, opcional

Para editar con Vite instalado en el equipo, utiliza Node.js 20, la misma versión principal que las imágenes del proyecto. Mantén PostgreSQL y la API en Docker y detén el Vite del contenedor para liberar su puerto:

```powershell
docker compose -f $compose up -d postgres backend
docker compose -f $compose stop frontend
Set-Location Frontend
npm ci --legacy-peer-deps
npm run dev -- --host 127.0.0.1 --port 5173
```

Vite reenvía `/api` y `/media` a `http://localhost:8000` por defecto. El parámetro `--legacy-peer-deps` reproduce la instalación del Dockerfile para las dependencias heredadas.

En otra terminal, situada en `Frontend`, puedes comprobar tipos y compilar:

```powershell
npx tsc --noEmit
npm run build
```

La compilación local genera `Frontend/dist`. Para actualizar el portal Nginx de Docker, vuelve a la raíz y ejecuta `docker compose -f $compose up -d --build nginx`. La API también monta su código fuente y utiliza recarga automática en el Compose incluido.

## Problemas habituales

| Problema | Comprobación o solución |
| --- | --- |
| Docker no conecta | Inicia Docker Desktop y comprueba `docker info`. |
| Puerto ocupado | Detén el proceso que lo usa; para Nginx puedes cambiar `HTTP_PORT` en `.env`. Los demás puertos están definidos directamente en Compose. |
| Vite todavía no abre | Revisa `docker compose -f $compose logs --tail 80 frontend`; en el primer inicio debe instalar dependencias. |
| API no saludable o error 502 | Revisa los logs de `backend` y `postgres`, su estado y las credenciales. |
| El usuario inicial no puede entrar | Comprueba si estás usando un volumen anterior sin la inicialización correspondiente. Sigue el apartado de actualización con respaldo antes de aplicar SQL. |
| Error 401 al consumir rutas protegidas | Inicia sesión de nuevo o revisa la clave API configurada. La clave local predeterminada es `dev-jupiter-key`. |
| No aparecen cambios en el portal 8080 | Reconstruye `nginx`; el puerto 5173 corresponde al frontend con recarga de desarrollo. |
| IA o fuentes externas no responden | Revisa credenciales, disponibilidad del proveedor y conectividad de Ollama desde Docker. |
| Hay tablas sin datos o indicadores vacíos | Carga datos operativos o registra operaciones; los datos del catálogo analítico no se copian al operativo. |

Esta guía describe el arranque HTTP local. El repositorio también incluye `docker-compose.https.yml` para HTTPS con certificados propios, documentado en las notas de integración.
