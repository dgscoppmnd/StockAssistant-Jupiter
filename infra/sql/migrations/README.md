# Migraciones de PostgreSQL en AWS

Crear aqui cada cambio nuevo con el formato:

```text
V20261020150000__agregar_campo_clientes.sql
```

La version son 14 digitos `AAAAMMDDhhmmss` en UTC, unica y mayor que todas las
versiones existentes/aplicadas. La descripcion usa minusculas ASCII y guiones
bajos. Resolver colisiones y orden en el PR antes de integrar en `master`.
El nombre anterior es un ejemplo: no existe una migracion inicial de prueba.

## Datos y estructura para app y migrator (21 de octubre de 2026)

Ambos roles pueden modificar datos y estructura de los objetos de usuario del
esquema `public`. El propietario comun es `migrator`: `app` hereda ese rol y
sus conexiones nuevas usan automaticamente `role=migrator`. De esta forma,
los objetos futuros creados desde cualquiera de los dos logins pertenecen al
mismo propietario y ambos pueden ejecutar ALTER, crear indices y reemplazar
funciones. Un GRANT de DML por si solo no concede estos derechos de propietario.
No se concede superusuario, CREATEROLE ni acceso a objetos del sistema.

Antes del siguiente Deploy AWS hay que ejecutar una vez, como `dbadmin` en
`stockassistant`, [05-migration-permissions.sql](../05-migration-permissions.sql).
Reconciliara los objetos existentes de `public`, incluidas tablas, vistas,
secuencias, funciones, procedimientos, enumeraciones y dominios. Excluye los
objetos pertenecientes a extensiones. Configura la pertenencia de `app`, su rol
efectivo de conexion y los privilegios futuros. Es transaccional y repetible.
Las conexiones de `app` que ya estuvieran abiertas deben reconectarse.
Los objetos nuevos deben crearse en `public` y conservar el rol efectivo;
un RESET ROLE explicito puede volver a crear objetos propiedad de `app`.

El CD actual solo dispone de la credencial `migrator`, sin capacidad para
administrar roles. Por eso no puede ejecutar esa preparacion automaticamente.
`V20261021130000__shared_schema_owner_access.sql` comprueba que este preparada
y concede privilegios sobre objetos actuales y futuros durante el siguiente
Deploy AWS (`all`, `backend` o `migrations`). Si falta la preparacion, devuelve
un error que indica el archivo administrativo necesario. La migracion anterior
`V20261021120000__restore_app_runtime_permissions.sql` se conserva sin cambios.
Para nuevas instalaciones se configura el mismo modelo desde `01-roles.sql`.

Con ambos roles capaces de alterar estructura, `app` tambien puede modificar
los historiales tecnicos por sus derechos heredados de propietario. Los REVOKE
sobre permisos directos no eliminan esa autoridad. Este modelo sustituye la
separacion anterior entre el rol operativo y el de migraciones.

Los privilegios PostgreSQL siguen siendo distintos de
`public.users.automation_permissions`: activar una regla requiere tambien una
sesion web cuyo usuario tenga `activate`. No se amplian permisos de usuarios web.

Validacion: pruebas de migraciones con PostgreSQL, incluidas conexiones reales
como `app` y ALTER de objetos creados por el otro login. Recuperacion: una nueva
migracion administrativa que retire la pertenencia de `app` y restablezca su rol
de conexion, seguida de reconexion; no editar versiones ya aplicadas.

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
- En instalaciones existentes ejecutar como `dbadmin`, conectado a
  `stockassistant`, [05-migration-permissions.sql](../05-migration-permissions.sql).
  Se puede repetir: instala las extensiones, transfiere a `migrator` las tablas,
  vistas, funciones y secuencias del esquema de la aplicacion y concede a `app`
  derechos de datos y estructura sobre objetos existentes y futuros.
  El recorrido incluye todos los objetos de usuario de public y excluye extensiones.
  No cambia contrasenas ni concede superusuario o CREATEROLE a `app`.
  La pertenencia temporal del ejecutor a `migrator` se retira solo si el propio
  script la agrego. Las pertenencias previas se conservan.
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

## Error PostgreSQL 42501 en AWS

El codigo indica permisos insuficientes en PostgreSQL. No significa un error
IAM ni de contrasena si ya se ha conectado y empezado a aplicar `init.sql`.
El ejecutor informa archivo, numero de instruccion, operacion y SQLSTATE sin
imprimir SQL, mensajes del servidor ni datos. Una operacion `UNKNOWN` puede ser
un bloque `DO`; el indice identifica el bloque completo, no su sentencia interna.

1. Conectar a `stockassistant` como `dbadmin` y ejecutar el diagnostico de solo
   lectura [diagnose-migration-permissions.sql](../diagnose-migration-permissions.sql).
2. Ejecutar como `dbadmin` [05-migration-permissions.sql](../05-migration-permissions.sql)
   para reparar permisos y propiedad de los objetos de la aplicacion.
   Para preparar solamente extensiones tambien existe
   [00-migration-extensions.sql](../00-migration-extensions.sql).
   `CREATE ON SCHEMA public` no equivale a `CREATE ON DATABASE stockassistant`.
   Preinstalarlas evita ampliar los permisos del migrador para instalarlas.
3. Si la reparacion falla, revisar objetos de la aplicacion cuyo propietario no sea `migrator` ni un rol
   cuyos permisos de propietario herede. Para ALTER/DROP o CREATE OR REPLACE de
   funciones no basta con `GRANT ALL ON TABLES`.
   Transferir solo los objetos identificados de la aplicacion con
   `ALTER TABLE ... OWNER TO migrator`, `ALTER VIEW ... OWNER TO migrator` o
   `ALTER FUNCTION nombre(tipos) OWNER TO migrator`, segun corresponda.
   La cuenta administradora necesita poder actuar como el propietario actual
   y asignar al nuevo propietario; en RDS puede requerir temporalmente
   `GRANT migrator TO dbadmin`, retirandolo despues con
   `REVOKE migrator FROM dbadmin`. No reasignar objetos internos ni extensiones.
4. Reintentar el job. El `init.sql` fallido se revierte y su hash no se registra;
   la tabla `schema_migrations`, creada previamente, puede permanecer vacia.

No volver a ejecutar `01-roles.sql` completo para reparar una instalacion:
sus instrucciones `CREATE ROLE` presuponen que los roles no existen todavia.
No conceder `dbadmin`, superusuario ni CREATEROLE al usuario `app`.
La pertenencia de `app` a `migrator` es intencional para permitir DDL a ambos roles.
