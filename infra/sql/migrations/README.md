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

1. Crear un SQL incremental compatible con el esquema actual y probarlo con
   datos representativos. No ejecutar `init_db()` ni copiar el inicializador
   completo como migracion.
2. Actualizar tambien el esquema para instalaciones locales nuevas en
   [init.sql](../../../BackEnd/apps/MonoliticDataStructure/app/docker/init-scripts/init.sql).
   AWS no lo ejecuta automaticamente.
3. Incluir en el PR efecto sobre datos, verificacion y recuperacion. Preferir
   cambios aditivos compatibles con la version anterior de la aplicacion.
4. Integrar en `master`. El CD valida, construye la imagen, aplica migraciones
   pendientes con `migrator` y solo entonces actualiza Lambda y publica frontend.
   Tambien existe Actions -> Deploy AWS -> Run workflow -> target `migrations`.
   La rama autorizada sigue siendo `master`.

No se necesita CMD ni entregar contrasenas al desarrollador. Las aprobaciones
dependen de las protecciones configuradas en el entorno GitHub `production`;
el YAML por si solo no impone una aprobacion humana.

## Ejecucion y versionado

- `public.schema_migrations` registra version, nombre, SHA-256, commit Git,
  fecha y usuario. Es una tabla tecnica nueva, no un recurso AWS.
- Orden lexicografico ascendente; solo se aplican versiones pendientes.
- Una migracion aplicada no se edita, renombra ni elimina: crear otra version.
  El ejecutor rechaza cambios de checksum, archivos aplicados ausentes y
  versiones nuevas anteriores a las ya aplicadas.
- El checksum normaliza CRLF a LF y elimina BOM UTF-8 para Windows/Linux.
- Un bloqueo asesor PostgreSQL impide dos ejecutores simultaneos.
- Cada archivo y su registro se confirman en la misma transaccion. Si falla,
  se revierte ese archivo y se detiene el CD; los anteriores quedan aplicados.
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
crea solo el historial si esta carpeta no contiene SQL.
Antes de integrar una funcionalidad, verificar que RDS tiene sus prerrequisitos;
este ejecutor no detecta ni corrige divergencias previas de esquema.
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
- El runner usa el endpoint publico existente, SSL `verify-full` y certificado
  oficial RDS. Depende de la accesibilidad actual confirmada por el administrador;
  no abre puertos ni agrega IPs. Si se restringe la red, el job fallara.
  Este flujo no endurece la regla publica existente.
- SSM usa el cifrado actual; una clave KMS personalizada requeriria revisar
  tambien `kms:Decrypt` para esa clave.

Validacion local opcional:
`python infra/scripts/migrate.py --check`.
Dependencias: [requirements-migrations.txt](../../scripts/requirements-migrations.txt).
