# Migraciones de PostgreSQL en AWS

Crear aqui cada cambio nuevo con el formato:

```text
V20261020150000__agregar_campo_clientes.sql
```

La version son 14 digitos `AAAAMMDDhhmmss` en UTC, unica y mayor que todas las
versiones existentes/aplicadas. La descripcion usa minusculas ASCII y guiones
bajos. Resolver colisiones y orden en el PR antes de integrar en `master`.
El nombre anterior es un ejemplo: no existe una migracion inicial de prueba.

## Flujo del desarrollador

1. Actualizar el esquema canonico en
   [init.sql](../../../BackEnd/apps/MonoliticDataStructure/app/docker/init-scripts/init.sql).
   El despliegue AWS lo comprueba y aplica automaticamente cuando su hash no
   consta en el historial compartido con Configuracion. Para tablas existentes,
   incluir `ALTER TABLE` o bloques de reconciliacion idempotentes: cambiar solo
   `CREATE TABLE IF NOT EXISTS` no actualiza columnas, tipos ni restricciones.
2. Si hace falta una migracion incremental adicional, crear aqui un SQL compatible
   con el esquema canonico y probarlo con datos representativos. Se ejecuta
   despues de `init.sql`; no duplicar sus efectos ni copiar el inicializador
   completo como migracion. No ejecutar `init_db()` desde las migraciones.
3. Incluir en el PR efecto sobre datos, verificacion y recuperacion. Preferir
   cambios aditivos compatibles con la version anterior de la aplicacion.
4. Integrar en `master`. El CD valida, construye la imagen, aplica
   el `init.sql` pendiente y las migraciones con `migrator` y solo entonces
   actualiza Lambda y publica frontend.
   Tambien existe Actions -> Deploy AWS -> Run workflow -> target `migrations`.
   La rama autorizada sigue siendo `master`.

No se necesita CMD ni entregar contrasenas al desarrollador. Las aprobaciones
dependen de las protecciones configuradas en el entorno GitHub `production`;
el YAML por si solo no impone una aprobacion humana.

## Ejecucion y versionado

- Se valida primero el historial de migraciones versionadas; despues se aplica
  el bloque `JUPITER SCHEMA` de `init.sql` si su hash es nuevo, en una transaccion
  propia. Se validan las tablas y columnas esenciales y las restricciones antes
  de registrar el hash y confirmar. El archivo completo determina el hash, con
  la misma lectura y normalizacion de saltos de linea que Configuracion.
- `app_schema_updates` registra la ultima aplicacion de `init.sql` y
  `app_schema_update_history` conserva todos los hashes aplicados. El actor `0`
  identifica el despliegue automatico. Una version aplicada desde Configuracion
  tampoco se repite en CD, ni se repite al volver a un archivo antiguo.
- Si el hash ya existe, se valida el esquema esencial sin repetir el SQL.
  No se calcula un diff automatico de PostgreSQL: los cambios para estructuras
  existentes deben estar expresados en el SQL. El archivo se ejecuta completo
  cuando el hash es nuevo, incluyendo sus instrucciones de datos.
- `public.schema_migrations` registra version, nombre, SHA-256, commit Git,
  fecha y usuario. Es una tabla tecnica nueva, no un recurso AWS.
- Orden lexicografico ascendente; solo se aplican versiones pendientes.
- Una migracion aplicada no se edita, renombra ni elimina: crear otra version.
  El ejecutor rechaza cambios de checksum, archivos aplicados ausentes y
  versiones nuevas anteriores a las ya aplicadas.
- El checksum de las migraciones versionadas normaliza CRLF a LF y elimina
  BOM UTF-8 para Windows/Linux. El de `init.sql` conserva el algoritmo de
  Configuracion para reconocer el historial existente.
- Un bloqueo asesor PostgreSQL, compartido con Configuracion e inicializacion,
  impide ejecutar ambos mecanismos simultaneamente.
- Cada archivo y su registro se confirman en la misma transaccion. Si falla,
  se revierte ese archivo y se detiene el CD; los anteriores quedan aplicados.
  Esto incluye `init.sql`: si ya se confirmo y una migracion posterior falla,
  el esquema canonico permanece aplicado. Cada migracion posterior tambien
  valida la compatibilidad estructural antes de confirmar.
- No incluir `BEGIN`, `COMMIT`, `ROLLBACK`, comandos de psql o cambios de sesion,
  roles o permisos del propio ejecutor. No modificar `schema_migrations`.
- No usar operaciones incompatibles con transacciones, como
  `CREATE INDEX CONCURRENTLY`, ni cambios destructivos sin un procedimiento
  especifico. Limites iniciales: espera de bloqueo 5 s y sentencia 120 s.
- Si falla el despliegue despues de migrar, el esquema no se revierte al volver
  a la imagen anterior. Usar expand/contract y planificar respaldo recuperable.

## Punto de partida

Los SQL historicos `infra/sql/01-roles.sql` a `04-integrated-automation.sql`
no se ejecutan ni se marcan automaticamente como aplicados. La primera ejecucion
crea `schema_migrations` y aplica el `init.sql` pendiente, aunque esta carpeta no
contenga SQL. Los bloques de reconciliacion del esquema canonico se ejecutan
como parte del archivo; la validacion estructural no sustituye una comparacion
exhaustiva del esquema ni las pruebas funcionales.
No trasladar los historicos aqui sin revisar que efectos repetirian.

## Preparacion unica del administrador

- Aplicar el cambio de la politica existente en
  [infra/bootstrap/main.tf](../../bootstrap/main.tf) para que el rol de despliegue
  lea solamente `/stockassistant/prod/db/migrator_password` con `ssm:GetParameter`.
  No se crean recursos AWS ni se modifica la red.
- Configurar variables del entorno GitHub `production`:
  `DB_MIGRATION_HOST` = endpoint RDS y `DB_MIGRATION_DATABASE` = `stockassistant`.
  No guardar contrasenas en variables GitHub.
- Mantener usuario `migrator` propietario de los objetos a alterar y privilegios
  por defecto para `app`. Las tablas nuevas se crean en `public`.
- `init.sql` usa extensiones `uuid-ossp`, `pgcrypto` y `pg_trgm`: deben existir
  o el migrador debe disponer de los permisos necesarios para instalarlas.
  Configurar `DB_LEGACY_TIMEZONE` en el entorno GitHub `production` con la zona
  usada por las fechas historicas de productos, si corresponde. Se transmite a
  la transaccion del esquema; si esta vacia se conserva la zona de la conexion.
- El runner usa el endpoint publico existente, SSL `verify-full` y certificado
  oficial RDS. Depende de la accesibilidad actual confirmada por el administrador;
  no abre puertos ni agrega IPs. Si se restringe la red, el job fallara.
  Este flujo no endurece la regla publica existente.
- SSM usa el cifrado actual; una clave KMS personalizada requeriria revisar
  tambien `kms:Decrypt` para esa clave.

Validacion local opcional:
`python infra/scripts/migrate.py --check`.
Comprueba tambien el bloque y las instrucciones de `init.sql`, sin conectarse:
la validacion real de tablas, columnas y restricciones ocurre durante la ejecucion.
Dependencias: [requirements-migrations.txt](../../scripts/requirements-migrations.txt).
