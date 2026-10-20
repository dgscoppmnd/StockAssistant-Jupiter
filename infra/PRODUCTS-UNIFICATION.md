# Unificación del catálogo de productos

`docker/init-scripts/init.sql` (dentro del backend) es la fuente canónica, tanto
para bases nuevas como para actualizar las existentes. La migración está dentro
del bloque `JUPITER SCHEMA`; también se ejecuta mediante `init_db()` en local.
En Lambda el arranque omite DDL: hay que aplicar el esquema antes de desplegar.

## Resultado y compatibilidad

- Una única tabla física: `public.products`. Su clave primaria es `id BIGINT`.
- Los antiguos `productos.pk_product` se conservan exactamente como `products.id`.
- `products.product_id` es el código externo textual, único y opcional. Se conserva
  este nombre para mantener los contratos analíticos y los scripts CSV existentes.
- Nombre, descripción y fechas se almacenan una sola vez: `product_name`,
  `description`, `created_at`, `updated_at`.
- `public.productos` pasa a ser una vista actualizable, sin almacenamiento propio.
  Traduce los nombres del contrato operativo (`pk_product`, `name_product`, etc.).
  Las escrituras del backend siguen siendo escrituras sobre la tabla única.
- Las relaciones operativas apuntan a `products.id`. Las cuatro relaciones
  analíticas (`inventory`, `sales`, `logistics`, `supply_chain_metrics`) conservan
  sus códigos textuales y apuntan a la clave única `products.product_id`. Esto
  evita cambiar las API analíticas y conserva los códigos originales.
- No se fusionan marca y proveedor, ni coste en USD y precio operativo. `price`,
  `final_price`, descuentos y moneda conservan su comportamiento; los importes
  explícitos en USD se guardan por separado. Para productos exclusivamente
  analíticos se mantienen los precios operativos que exponía la antigua vista AWS.
- Categoría, marca, SKU y costes del CSV se guardan estructurados. Las descripciones
  históricas no se reescriben ni se interpretan mediante heurísticas.
- Se conserva la identidad vectorial `operational:{id}` y los snapshots históricos.
- `PRODUCTS_READ_RELATION` ya no selecciona catálogos distintos ni bloquea las
  escrituras. Se ignora en el backend; la configuración Lambda queda en `productos`.

## Producción

1. Crear un snapshot/restauración verificable de RDS (o respaldo completo equivalente).
2. Ensayar sobre una copia, incluyendo pruebas operativas. La copia local de
   200.000 productos sirve de referencia; no sustituye el ensayo sobre RDS.
3. Activar una ventana de mantenimiento y detener escritores y workers. Esta es
   una migración transaccional con bloqueos, no un despliegue sin interrupción.
4. Usar el propietario del esquema o un migrator con propiedad/permisos sobre
   las tablas y vistas existentes; el rol `app` no tiene permisos de migración.
5. Definir `JUPITER_MIGRATION_DSN` sin incluirlo en comandos, logs ni el repositorio.
   La conexión debe utilizar la configuración TLS apropiada para RDS.
6. Con Python y `psycopg2` disponibles, ejecutar desde la raíz:

   ```text
   python infra/scripts/apply-schema.py --legacy-timezone UTC --check-only
   python infra/scripts/apply-schema.py --legacy-timezone UTC
   ```

   Sustituir `UTC` por la zona en la que se escribieron realmente las fechas
   `TIMESTAMP` del catálogo analítico. No inferirla de la ubicación del servidor.
   Los `TIMESTAMPTZ` operativos ya contienen el instante y se conservan.
   Como alternativa, `psql -X -v ON_ERROR_STOP=1 -f .../init.sql` ejecuta el archivo
   completo; configurar previamente la misma zona horaria en la conexión.
7. Desplegar el backend actualizado y ejecutar lecturas, altas, CSV, imágenes,
   inventario, compras, ventas, agentes y búsqueda semántica antes de reabrir.

El esquema adquiere el mismo advisory lock que `init_db()`. El límite de espera
por bloqueos es 15 segundos: si hay escritores activos, se aborta para poder
reintentar durante la ventana. No se elimina ninguna dependencia con CASCADE.

Los duplicados de código, SKU incompatibles, conflictos de nombre/descripción
para un mismo código y dependencias desconocidas causan error y rollback. Los
triggers personalizados, RLS y restricciones de negocio no previstas también
exigen una migración explícita; no se eliminan silenciosamente. Se
deben reconciliar explícitamente y volver a ejecutar; no se descartan registros.
Los campos operativos y sus fechas tienen prioridad en coincidencias por código;
los campos exclusivos analíticos completan el registro. IDs de registros solo
analíticos se asignan por encima del máximo ID operativo, nunca desde el código.
Se copian las claves foráneas con sus acciones y los permisos DML existentes.

`03-productos-catalogo.sql` queda como alias opcional para herramientas antiguas.
Ejecutarlo solo después del esquema canónico. El backend no depende de ese alias.
`04-integrated-automation.sql` también referencia la tabla canónica.

## Reversión y pruebas

Un fallo antes del commit revierte DDL y datos. Después del commit, restaurar el
respaldo durante mantenimiento y desplegar la versión anterior. Si se han
reabierto las escrituras, hace falta reconciliar las operaciones posteriores al
respaldo: no existe un downgrade automático sin pérdida de esas escrituras.

Las pruebas reales `tests/test_products_unification_postgres.py` crean y eliminan
bases aisladas. Cubren instalación nueva, repetición, vistas actualizables,
fusión, IDs, secuencias, claves foráneas y rollback ante conflictos/dependencias.
No deben apuntar a una base de aplicación mediante modificaciones de esas pruebas.
