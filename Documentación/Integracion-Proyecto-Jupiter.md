# Proyecto Jupiter — integración

Integración inicial: 5 de septiembre de 2026. Revisión e integración de nuevas referencias de `docs`: 8 de septiembre de 2026.

## Capacidades

| Área | Resultado |
| --- | --- |
| Backend local | Conserva las rutas `/api/v1` de productos, inventario, ventas, proveedores, logística, métricas y análisis. Se corrige la inicialización de los modelos SQLAlchemy para compartir su `Base`. |
| Operación | Conserva catálogo con imágenes, compras, recepciones, reservas, despachos, devoluciones, transferencias, conversiones y movimientos auditables. |
| Datos maestros | CRUD de unidades, monedas, bodegas, proveedores, conversiones y documentos de conocimiento, con validación y protección de referencias. |
| Ejecutivo | Enrutamiento de consultas a agentes y persistencia de decisiones. |
| Automatizaciones | Informes diarios, alertas de riesgos y propuestas de reposición pendientes de aprobación. Activación, ejecución manual, historial y trabajador interno con cierre de conexiones y registro de errores. No realiza pedidos definitivos. |
| Dashboard | Período configurable, indicadores, alertas, compras prioritarias, gráficos, exportación CSV y asistente. Los indicadores sin datos permanecen sin estimación. |
| IA y conectores | Se conservan OpenAI/Ollama, análisis comercial, previsión, finanzas, reseñas, competencia y fuentes externas. |
| Frontend | Código, configuración, Nginx, Dockerfile y compilación en `Frontend`; salida en `Frontend/dist`. Se retira el antiguo `dist` de la raíz. |
| Identidad | Proyecto Jupiter; marca stockassistant; cuenta local `admin@stockassistant.app`, con la contraseña solicitada almacenada mediante PBKDF2. |

No se integran n8n, sus rutas, credenciales, bases, volúmenes o dependencias; tampoco TaskManager, Gantt, registro de jornadas o costes por hora. Se eliminan además sus pantallas y llamadas residuales del frontend local. `docs` permanece como referencia y no forma parte de los contextos de compilación ni de los montajes de ejecución. Se sustituyeron las referencias textuales a la marca anterior en los archivos de referencia.

## Base de datos

La base configurada es `supply_chain`. El esquema original conserva `products`, `suppliers`, `warehouses`, `inventory`, `sales`, `logistics` y `supply_chain_metrics`, junto con sus vistas y funciones.

El esquema operativo utiliza `productos`, `inventory_*`, documentos de compra/venta, reseñas y conocimiento. Ambos grupos se mantienen en la misma base, respetando sus identificadores y contratos de API. No se presupone equivalencia entre los identificadores alfanuméricos del catálogo analítico y los numéricos del catálogo operativo, ni se introduce una sincronización automática entre ambos.

Se incorporan `agent_decisions`, `automation_rules`, `automation_runs` y `purchase_proposals`, con sus relaciones e índices. `docker/init-scripts/init.sql` contiene el esquema completo y la cuenta inicial dentro de una transacción. Puede aplicarse a una base existente; no elimina tablas ni registros. Al reaplicarlo, restablece las credenciales y el estado activo del administrador solicitado. El inicio del backend también crea las tablas operativas faltantes.

La migración se aplicó a la base local después de crear el respaldo:

`BackEnd/apps/MonoliticDataStructure/app/data/backups/jupiter-before-integration-20260905.dump`

El volumen existente `docker_postgres_data` se conserva. No se cambió el identificador histórico de Compose, para evitar crear otro volumen o perder acceso a los datos.

## Arranque

Desde la raíz del repositorio, en PowerShell:

```powershell
$compose = 'BackEnd/apps/MonoliticDataStructure/app/docker/docker-compose.yml'
docker compose -f $compose up -d --build
```

- Portal compilado en Nginx: <http://localhost:8080>.
- Desarrollo Vite: <http://localhost:5173>.
- API y documentación: <http://localhost:8000/docs>.
- PostgreSQL: puerto local 5433; pgAdmin: <http://localhost:5050>.

Nginx conserva el prefijo `/api` del backend integrado y sirve `/media`; Vite también reenvía ambos. Compose incorpora reinicio automático, opciones de sesión y conectores, zona horaria y control del trabajador de automatizaciones. Las reglas nacen pausadas.

Para una base existente en otra instalación, los scripts de Docker no se ejecutan automáticamente sobre un volumen inicializado. Aplicar explícitamente la migración, después de respaldar esa base:

```powershell
docker cp BackEnd/apps/MonoliticDataStructure/app/docker/init-scripts/init.sql proyecto_jupiter_db:/tmp/jupiter-init.sql
docker exec proyecto_jupiter_db psql -U admin -d supply_chain -v ON_ERROR_STOP=1 -f /tmp/jupiter-init.sql
```

HTTPS es opcional. `docker-compose.https.yml` monta `Frontend/nginx.tls.conf` y certificados propios; no reutiliza dominios ni certificados del proyecto de referencia:

```powershell
$env:TLS_CERTS_DIR = 'C:/ruta/a/certificados'
# El directorio debe contener cert.crt y private.key.
docker compose -f $compose -f BackEnd/apps/MonoliticDataStructure/app/docker/docker-compose.https.yml up -d nginx
```

## Verificación inicial (5 de septiembre)

- TypeScript: `npx --prefix Frontend tsc --noEmit -p Frontend/tsconfig.json` sin errores.
- Compilación Vite e imagen Docker de Nginx correctas; `nginx -t` correcto.
- 19 pruebas unitarias de reglas comerciales, inventario, maestros, ejecutivo, IA, conectores y reseñas aprobadas.
- 3 pruebas HTTP/SQL de integración aprobadas en `jupiter_integration_test`: rutas originales/nuevas y exclusiones; CRUD y referencias; recepción, dashboard, decisiones y las tres automatizaciones.
- SQL aplicado dos veces sobre la base aislada, comprobando repetibilidad.
- Acceso real al portal Nginx con el administrador solicitado y dashboard revisados en el navegador.
- Los cinco servicios quedaron activos y PostgreSQL saludable.

Las pruebas nuevas están en `BackEnd/apps/MonoliticDataStructure/app/tests`. `test_jupiter_integration.py` requiere una base desechable inicializada con `init.sql`, cuyo nombre termine en `_test`, indicada mediante `JUPITER_TEST_DB`. Lanza una API temporal en el puerto 18001; no debe apuntarse a la base de uso normal. La base de prueba utilizada se conserva separada para inspección.

No se realizaron llamadas reales a proveedores de IA, Google OAuth o servicios externos; requieren sus credenciales y disponibilidad. HTTPS queda preparado, sin activar por falta de certificados propios. La instalación de dependencias frontend informó 14 vulnerabilidades en el árbol heredado; no se aplicaron actualizaciones incompatibles durante esta integración. Las pruebas históricas de generadores no se ejecutaron por falta de pandas y pytest en el entorno Python local.


## Reintegración del 8 de septiembre de 2026

Se volvió a comparar el proyecto con las referencias actualizadas de `docs/kitia-server`, `docs/html_nginx`, `docs/dockerfiles` y el nuevo `docs/init-scripts/init-users.sql`.

### Nuevas funciones incorporadas

- Clientes con código textual que conserva ceros iniciales, tipos de cliente y ficha de detalle.
- Direcciones globales y asociaciones de direcciones a clientes y proveedores: creación, consulta, edición y desvinculación, con protección de dependencias y duplicados.
- Pantalla de proveedores con su lista de direcciones.
- Nuevos selectores de productos y proveedores, y ventanas de configuración de producto y creación de bodegas en inventario.
- Selector de opciones en los formularios de datos maestros.
- Corrección de la edición de direcciones: los identificadores de la asociación no se envían como campos de la dirección global. La lista vuelve a consultar el estado de uso tras cambiar asociaciones.
- Corrección de conversiones: su tabla no tiene `updated_at`; las consultas y actualizaciones respetan esa estructura.
- El formulario de cliente selecciona el tipo predeterminado de la base (Propio) cuando está disponible, en lugar del primer elemento de la lista descendente (Suspendido).

### SQL y compatibilidad

`init.sql` incorpora 14 tablas adicionales: `type_client`, `clients`, `globlal_addresses`, `clients_addresses`, `inventory_suppliers_addresses`, `error_log`, `properties`, `currency`, `type_catalog`, `type_funding_source`, `catalogues`, `catalogues_products`, `markets` y `markets_catalogues`.

Se conserva el nombre físico `globlal_addresses` utilizado por el contrato de origen. Las fechas comerciales nuevas utilizan TIMESTAMPTZ y los enlaces de mercados utilizan TEXT. Se mantienen los precios NUMERIC del proyecto local.

También se incorporan el índice único de código externo de producto, la vista de productos recientes y el trigger de fechas. Antes de crear el índice se comprobó que no había códigos externos duplicados. `proms` mantiene sus columnas locales y añade `nombre`, `prom`, `status` e `id_prom` calculado a partir de `id`, haciendo compatible el contrato del backend de referencia sin perder los registros existentes.

El bloque nuevo se encuentra igualmente en `src/DataBaseManagement/schema_extensions.sql`, que el backend ejecuta al inicializar sus tablas. Su contenido está incluido en `docker/init-scripts/init.sql`. Los tipos iniciales se insertan sin sobrescribir etiquetas que el usuario haya editado.

No se importan cambios de propietario, conexiones a otras bases, n8n, TaskManager, Gantt ni costes o registros de horas. Se mantienen las correcciones locales de autenticación y del trabajador de automatizaciones. Los selectores de inventario reutilizaban nombres CSS del registro de horas; se adaptaron a nombres propios de inventario y se retiraron los estilos de los módulos excluidos.

### Despliegue y comprobaciones actuales

- Respaldo anterior a la reintegración: `BackEnd/apps/MonoliticDataStructure/app/data/backups/jupiter-before-reintegration-20260908.dump`.
- Migración ejecutada dos veces en `jupiter_20260908_test` y aplicada a `supply_chain` conservando el volumen existente.
- 23 pruebas unitarias y 6 pruebas HTTP/SQL de integración aprobadas (29 en total). Incluyen las nuevas direcciones, duplicados, referencias, códigos de cliente, conversiones y compatibilidad de prompts.
- TypeScript sin errores y compilaciones de Vite y Nginx correctas.
- Acceso real verificado con `admin@stockassistant.app` y la contraseña solicitada; revisados el listado y el formulario de clientes en el navegador.
- Compose incorpora zona horaria de PostgreSQL y un healthcheck del backend; Nginx y Vite esperan a que esté saludable.

Se mantienen los mismos puertos de acceso y las limitaciones de credenciales externas y certificados descritas arriba. La compilación sigue informando 14 vulnerabilidades heredadas de dependencias frontend; no se realizaron actualizaciones incompatibles dentro de esta integración. Los datos de prueba permanecen en una base separada.
