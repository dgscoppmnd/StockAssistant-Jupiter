# Actualización desde Configuración

En `/configuracion` y `/setup`, **Actualizar base de datos** ejecuta el bloque
`JUPITER SCHEMA` del `docker/init-scripts/init.sql` incluido en el servidor desplegado.
El navegador solo envía el hash esperado; no acepta SQL, archivos ni credenciales.
Solo modifica PostgreSQL: no crea ni actualiza recursos AWS, políticas IAM,
contenedores ni despliegues. Si se usa SSM, únicamente lee la credencial existente.

Cada versión del archivo se aplica una sola vez. El historial persistente en
`app_schema_update_history` se escribe en la misma transacción que los cambios.
El servidor comprueba ese historial bajo el bloqueo antes de ejecutar SQL; los
reintentos y los reinicios de Lambda no repiten una versión ya confirmada. El
botón queda deshabilitado cuando ya está aplicada. Un fallo con rollback permite
volver a intentarlo. Si se despliega un init.sql diferente, se habilita su nueva
actualización manual. Volver a desplegar un archivo antiguo ya aplicado no lo repite.

El despliegue AWS tambien comprueba y aplica el `init.sql` pendiente antes de
las migraciones versionadas de `infra/sql/migrations`. Comparte el lector, las
validaciones, el bloqueo y el historial de hashes con este panel: una version
confirmada por cualquiera de las dos rutas no se repite por la otra. El actor
`0` en `app_schema_updates` identifica una aplicacion automatica del despliegue.
`schema_migrations` registra por separado los archivos incrementales versionados;
no sustituye el historial de hashes del esquema canonico.

El servidor divide las instrucciones respetando los bloques PostgreSQL, toma el
mismo bloqueo de inicialización y ejecuta todo dentro de una transacción. Después
comprueba las tablas y columnas esenciales, valida los CHECK y las claves foráneas
pendientes y fuerza la comprobación de restricciones diferidas. Solo entonces
registra la versión aplicada y hace COMMIT. Los errores SQL o de validación provocan
ROLLBACK, incluidos los cambios de estructura. La barra avanza por instrucciones,
no estima el tiempo restante. El 100 % requiere confirmación del COMMIT.

Si se pierde la conexión justo al confirmar, el resultado puede ser incierto:
**Consultar estado** permite comprobar el hash y la fecha de la última ejecución
confirmada. No se debe interpretar un corte de red como un rollback confirmado.
La validación comprueba integridad SQL y compatibilidad estructural básica; no
sustituye las pruebas funcionales de un cambio de negocio.

## Local

Temporalmente, cualquier usuario con sesión válida y cuenta activa y no caducada
puede consultar el estado y ejecutar la actualización pendiente. La variable
`SCHEMA_ADMIN_USER_IDS` y su función de lectura se conservan para futuras versiones,
pero no restringen estas operaciones, aunque estén vacías o no incluyan al usuario.
Una API key por sí sola no sustituye la sesión de usuario requerida por este panel.
Se usa la conexión actual de PostgreSQL, que debe tener permisos de propietario
para los objetos modificados. Opcionalmente `JUPITER_MIGRATION_DSN` proporciona
una conexión separada a la misma base, host y puerto. Nunca colocar este DSN en
variables `VITE_*`, código frontend ni Git.

## AWS Lambda

1. Desplegar la imagen de API y el frontend que contienen este cambio.
2. Iniciar sesión con una cuenta activa del portal. No hace falta configurar
   `SCHEMA_ADMIN_USER_IDS`: temporalmente se ignora hasta incorporar roles.
3. Crear el parámetro **SecureString** de SSM
   `/stockassistant/prod/db/migration_dsn`, con un DSN PostgreSQL de migración
   (`host=... port=5432 dbname=... user=... password=... sslmode=verify-full`).
   Debe apuntar a la misma base, host y puerto que la API y tener permisos para
   modificar los objetos del esquema. Para otra ruta, definir
   `SCHEMA_MIGRATION_DSN_PARAMETER`.
4. En el **rol de ejecución de Lambda**, permitir `ssm:GetParameter` para el ARN
   de ese parámetro. Si usa una clave KMS propia, permitir también `kms:Decrypt`
   sobre ella. El rol de despliegue de GitHub es diferente: sus permisos no se
   trasladan al proceso Lambda. El backend exige TLS con verificación del
   certificado RDS, incluido en la imagen actual.
5. Mantener conectividad de Lambda a RDS y un timeout suficiente para la operación
   (recomendado 360 segundos). El servicio limita cada instrucción a 60 segundos,
   la espera por bloqueos a 15 segundos y revisa un presupuesto de 240 segundos
   entre instrucciones. Los límites del proxy también deben permitir esta duración.
   El adaptador Lambda de esta imagen ya declara `response_stream`; el endpoint
   AWS que lo invoque debe admitir streaming para ver avances durante la ejecución.

El botón aplica
el archivo de la API desplegada; no descarga el archivo de GitHub ni despliega
el frontend. Cambiar una definición `CREATE TABLE IF NOT EXISTS` no modifica una
tabla existente: los nuevos cambios deben incluir `ALTER`/migraciones idempotentes
en el bloque del esquema. No incluir COMMIT/ROLLBACK explícitos ni operaciones
externas con efectos no transaccionales en ese bloque.

## Verificación

`tests/test_schema_update.py` usa una base temporal creada y eliminada por el test
con la conexión del contenedor. Comprueba ejecución completa y repetida, rollback
de DDL y datos, validación fallida, desconexión, exclusión mutua y autorización.
Ejemplo: copiarlo a `/tmp/test_schema_update.py` en el contenedor API y ejecutar
`python /tmp/test_schema_update.py`.
Frontend: `node --test tests/schema-update.test.mjs`, `npx tsc --noEmit`, `npm run build`.
