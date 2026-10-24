# Frontend Proyecto Jupiter

## Resumen

El frontend es una aplicación React 18 + TypeScript construida con Vite. Su código vive en `Frontend/` y consume la API FastAPI del backend mediante rutas relativas con prefijo `/api`.

```text
Navegador
   |
   | /api/* y /media/*
   v
Vite (desarrollo :5173) o Nginx (producción :8080)
   |
   | proxy interno
   v
FastAPI (:8000)
   |
   +--> PostgreSQL (:5433 desde el host)
   +--> Qdrant (:6333)
```

## Estructura relevante

| Ruta | Responsabilidad |
| --- | --- |
| `Frontend/src/App.tsx` | Rutas de React, menú y protección visual de la sesión. |
| `Frontend/src/api.ts` | Cliente HTTP, autenticación, manejo de errores y llamadas a la API. |
| `Frontend/src/auth.tsx` | Contexto de sesión, login, logout y expiración del token. |
| `Frontend/src/types.ts` | Contratos TypeScript de las respuestas y payloads. |
| `Frontend/src/pages/` | Pantallas del portal. |
| `Frontend/vite.config.ts` | Proxy de `/api` y `/media` durante desarrollo. |
| `Frontend/nginx.conf` | Proxy de `/api` y `/media` en la imagen compilada. |
| `BackEnd/apps/MonoliticDataStructure/app/src/api/main.py` | Aplicación FastAPI, routers, CORS, salud y documentación OpenAPI. |
| `BackEnd/apps/MonoliticDataStructure/app/docker/docker-compose.yml` | Servicios integrados del entorno local. |

## Cómo conectar frontend y backend

### Desarrollo local

El cliente no apunta directamente a una URL configurable en cada llamada. `Frontend/src/api.ts` usa:

```ts
const API_BASE = "/api";
```

Vite reenvía ese prefijo a `http://localhost:8000` por defecto. También reenvía `/media`, usado para imágenes de productos. Para cambiar el destino:

```powershell
$env:API_PROXY_TARGET = "http://localhost:8000"
npm run dev
```

La API se registra en FastAPI con dos grupos principales:

- `/api`: autenticación, usuarios, productos operativos, inventario, agentes, ejecutivo, datos maestros y análisis.
- `/api/v1`: rutas analíticas heredadas de productos, inventario, ventas, proveedores, logística, métricas y analytics.

Documentación interactiva:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`
- `http://localhost:8000/health`

### Docker Compose

En `docker-compose.yml`, el servicio frontend define `API_PROXY_TARGET=http://backend:8000`. El navegador entra por `http://localhost:5173`, Vite resuelve `backend` dentro de la red Docker y FastAPI queda disponible en `http://localhost:8000` desde el host.

La imagen Nginx usa el mismo patrón: `/api/*` y `/media/*` se proxyfican a `http://backend:8000`, mientras que el resto sirve la aplicación React y aplica fallback a `index.html`.

### Autenticación

El flujo actual es:

1. El frontend puede validar una API key con `GET /api/` usando `X-API-Key`.
2. El login local usa `POST /api/auth/password`; Google usa `POST /api/auth/google`.
3. La API devuelve un JWT. El frontend lo guarda en `localStorage` como `stockassistant-session-token`.
4. Las siguientes peticiones usan `Authorization: Bearer <token>`.
5. Si no existe sesión, el cliente intenta usar `X-API-Key` desde `VITE_STOCKASSISTANT_API_KEY` o desde la clave guardada localmente.

Para desarrollo, la clave debe coincidir con `STOCKASSISTANT_API_KEYS` del backend y `VITE_STOCKASSISTANT_API_KEY` del frontend. Compose trae por defecto `dev-jupiter-key`.

> No usar una API key real en `VITE_*` en producción: las variables Vite quedan incorporadas al bundle y son visibles para el navegador. En producción debe preferirse login con sesión y HTTPS.

## Cómo levantar el proyecto

### Opción recomendada: todo con Docker

Desde la raíz del repositorio, en PowerShell:

```powershell
$compose = "BackEnd/apps/MonoliticDataStructure/app/docker/docker-compose.yml"
docker compose -f $compose up -d --build
```

Direcciones:

| Servicio | URL |
| --- | --- |
| Portal Nginx compilado | http://localhost:8080 |
| Frontend Vite en desarrollo | http://localhost:5173 |
| FastAPI | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| PostgreSQL desde el host | `localhost:5433` |
| pgAdmin | http://localhost:5050 |
| Qdrant | http://localhost:6333 |

Comandos útiles:

```powershell
docker compose -f $compose ps
docker compose -f $compose logs -f backend
docker compose -f $compose logs -f frontend
docker compose -f $compose down
```

El Compose inicia PostgreSQL antes que el backend, y el frontend de desarrollo instala dependencias y arranca Vite dentro del contenedor. El portal Nginx y el frontend Vite son dos entradas distintas: para trabajar con hot reload usar `5173`; para probar el bundle final usar `8080`.

### Arranque manual del frontend

Requisitos: Node.js 20 o compatible y el backend accesible en el puerto 8000.

```powershell
Set-Location Frontend
npm ci --legacy-peer-deps
npm run dev
```

Abrir `http://localhost:5173`. Para comprobar la compilación:

```powershell
npm run build
npm run preview
```

### Arranque manual del backend

La opción más estable es levantar primero PostgreSQL y las dependencias con Compose, y ejecutar solo la API desde el entorno Python del backend. Alternativamente, todo el backend se inicia con:

```powershell
Set-Location BackEnd/apps/MonoliticDataStructure/app
make build
make up
```

En Windows sin `make`, el equivalente es:

```powershell
docker compose -f docker/docker-compose.yml up -d --build
```

La API arranca con `uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload`. Las credenciales de base de datos, API key, secreto de sesión e integraciones externas se configuran mediante variables de entorno o un archivo `.env` junto al Compose.

## Comprobaciones rápidas

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/
Test-NetConnection localhost -Port 8000
Test-NetConnection localhost -Port 5173
```

Si el portal carga pero las peticiones fallan:

1. Revisar que el backend responda en `/health`.
2. Revisar la consola del navegador y la pestaña Network para confirmar que la petición va a `/api/...`.
3. Revisar logs de `backend` y `frontend`.
4. Confirmar que la API key coincide en ambos servicios o iniciar sesión para obtener el JWT.
5. Confirmar que no se está mezclando `localhost:5173` con un backend detenido, o `localhost:8080` con una configuración Nginx que no tenga el servicio `backend` disponible.

## Estado funcional del frontend

Las pantallas principales ya están cableadas a funciones del cliente HTTP:

- Dashboard ejecutivo: métricas y evolución del stock.
- Asistente Jupiter: consultas a agentes y proveedores de IA.
- Agentes: alertas, previsiones, compras, competencia, reseñas y soporte.
- Centro ejecutivo: decisiones, automatizaciones, ejecuciones y propuestas.
- Usuarios: CRUD de usuarios.
- Productos: CRUD de productos e imágenes.
- Inventario: almacenes, existencias, recepciones y transferencias.
- Configuración: integraciones y datos maestros.

## Sugerencias de avance

### Prioridad alta

- Añadir pruebas de integración del frontend para login, expiración de sesión, errores `401/403` y una operación CRUD representativa.
- Generar o mantener un contrato OpenAPI compartido para reducir divergencias entre `types.ts` y los modelos Pydantic.
- Crear una capa de estados de carga, error y reintento común para evitar lógica repetida en las páginas.
- No entregar secretos mediante variables `VITE_*`; definir una estrategia de sesión segura para despliegue y rotación de credenciales.
- Añadir una verificación CI de `npm ci`, `tsc --noEmit` y `npm run build`.

### Prioridad media

- Centralizar la URL de API solo si se necesita consumir un backend remoto; mientras el frontend y backend compartan origen, conservar `/api` evita problemas de CORS.
- Versionar explícitamente las llamadas nuevas y decidir si deben vivir bajo `/api` o `/api/v1`.
- Añadir cancelación de peticiones y paginación para listados grandes de productos, usuarios y movimientos.
- Mejorar la observabilidad del cliente: identificador de petición, mensajes de error accionables y estado visible de la API.
- Revisar accesibilidad del menú, tablas, formularios y avisos de error con teclado y lector de pantalla.

### Prioridad de producto

- Definir permisos por rol en frontend y backend; ocultar un menú no sustituye la autorización de la API.
- Completar estados de aprobación para propuestas de compra antes de conectarlas con operaciones reales.
- Incorporar validación de formularios alineada con las restricciones del backend.
- Añadir pruebas end-to-end contra un Compose aislado para cubrir login, navegación, CRUD e inventario.

## Referencias del repositorio

- [[Integracion-Proyecto-Jupiter]]
- [[../BackEnd/apps/MonoliticDataStructure/app/README]]
- [[../BackEnd/apps/MonoliticDataStructure/app/src/api/main.py]]
- [[../Frontend/src/api.ts]]
- [[../Frontend/vite.config.ts]]
- [[../Frontend/nginx.conf]]
