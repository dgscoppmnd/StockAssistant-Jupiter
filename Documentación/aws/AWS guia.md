# Guía de lo realizado en AWS (Fase 0 y paso 7)

  

Región: `eu-west-1`. Consola de referencia: CMD de Windows (`%VAR%`; en `.bat` duplicar `%%`).

No se guardan secretos en este documento: viven en SSM Parameter Store.

  

## 1. Estado actual

  

| Recurso                                                               | Nombre / ruta                                                                                                       | Estado                          |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| Bucket de estado Terraform + OIDC GitHub + rol deploy                 | `infra/bootstrap/main.tf`                                                                                           | Aplicado                        |
| Backend Terraform prod                                                | `infra/envs/prod/` (`backend.hcl` local, ignorado por git)                                                          | Configurado                     |
| S3 Vectors (bucket + índices `products`, `documents`, 1536 d, coseno) | `infra/envs/prod/s3vectors.tf`                                                                                      | Según lo aplicado con Terraform |
| Security Group RDS                                                    | `stockassistant-rds` (5432 solo desde tu IP `/32`)                                                                  | Activo                          |
| Parameter group                                                       | `stockassistant-pg16` (`rds.force_ssl=1`, `log_connections`, `log_disconnections`)                                  | Activo                          |
| Subnet group                                                          | `stockassistant-subnets` (3 subnets públicas de la VPC por defecto)                                                 | Activo                          |
| RDS                                                                   | `stockassistant-prod` (Postgres 16, db.t4g.micro, 20 GB gp3, cifrado, público, backups 7 días, deletion protection) | Disponible                      |
| Logs Postgres → CloudWatch                                            | `/aws/rds/instance/stockassistant-prod/postgresql` (retención 14 días)                                              | Activo                          |
| Contraseñas                                                           | SSM SecureString `/stockassistant/prod/db/{master_password,app_password,migrator_password}`                         | Guardadas                       |
| Roles Postgres                                                        | `dbadmin` (maestro), `migrator` (DDL), `app` (DML)                                                                  | Creados                         |
| Esquema                                                               | `docker/init-scripts/init.sql` cargado como `migrator`                                                              | Cargado                         |

  

## 2. Pasos realizados (reproducibles)

  

### 2.1 Red

Verificar VPC por defecto, 3 subnets públicas en AZ distintas y ruta `0.0.0.0/0 → igw`:

```bat

aws ec2 describe-vpcs --filters Name=isDefault,Values=true --region %R%

aws ec2 describe-subnets --filters Name=vpc-id,Values=%VPC% --region %R%

aws ec2 describe-route-tables --filters Name=vpc-id,Values=%VPC% --region %R%

```

  

### 2.2 Security Group limitado a tu IP

```bat

for /f %i in ('curl -s https://checkip.amazonaws.com') do set MYIP=%i

aws ec2 create-security-group --group-name stockassistant-rds --description "RDS Postgres StockAssistant" --vpc-id %VPC% --region %R%

aws ec2 authorize-security-group-ingress --group-id %SG% --protocol tcp --port 5432 --cidr %MYIP%/32 --region %R%

```

Si tu IP cambia (Digi usa IP dinámica): ejecutar [update-sg-ip.bat](../infra/update-sg-ip.bat).

  

### 2.3 Contraseña maestra en SSM

Generada aleatoria (32 alfanuméricos) y guardada sin mostrarla:

```bat

for /f %p in ('python -c "import secrets,string;print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))"') do set PGPASS=%p

aws ssm put-parameter --name /stockassistant/prod/db/master_password --type SecureString --value %PGPASS% --region %R%

```

Recuperarla en una nueva consola:

```bat

for /f %p in ('aws ssm get-parameter --name /stockassistant/prod/db/master_password --with-decryption --region %R% --query Parameter.Value --output text') do set PGPASS=%p

```

  

### 2.4 Parameter group, subnet group e instancia

```bat

aws rds create-db-parameter-group --db-parameter-group-name stockassistant-pg16 --db-parameter-group-family postgres16 --description "force ssl" --region %R%

aws rds modify-db-parameter-group --db-parameter-group-name stockassistant-pg16 --parameters "ParameterName=rds.force_ssl,ParameterValue=1,ApplyMethod=immediate" --region %R%

aws rds create-db-subnet-group --db-subnet-group-name stockassistant-subnets --db-subnet-group-description "public subnets" --subnet-ids <subnet-a> <subnet-b> <subnet-c> --region %R%

aws rds create-db-instance --db-instance-identifier stockassistant-prod --engine postgres --engine-version 16 --db-instance-class db.t4g.micro --allocated-storage 20 --storage-type gp3 --storage-encrypted --master-username dbadmin --master-user-password %PGPASS% --db-name stockassistant --vpc-security-group-ids %SG% --db-subnet-group-name stockassistant-subnets --db-parameter-group-name stockassistant-pg16 --publicly-accessible --no-multi-az --backup-retention-period 7 --deletion-protection --copy-tags-to-snapshot --region %R%

aws rds wait db-instance-available --db-instance-identifier stockassistant-prod --region %R%

```

  

### 2.5 Conexión con SSL (psql en Docker)

Certificado: `curl -o infra\rds-global-bundle.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem` (ignorado por git).

```bat

set H=<endpoint-rds>

docker run --rm -e PGPASSWORD=%PGPASS% -v "%cd%\infra:/certs" postgres:16 psql "host=%H% dbname=stockassistant user=dbadmin sslmode=verify-full sslrootcert=/certs/rds-global-bundle.pem" -c "select ssl from pg_stat_ssl where pid=pg_backend_pid();"

```

Comprobación de rechazo sin SSL (`sslmode=disable`) → `no encryption`. Verificado.

  

### 2.6 Usuarios con mínimo privilegio

- Contraseñas `app` y `migrator` aleatorias en SSM (`app_password`, `migrator_password`).

- Script: [01-roles.sql](../infra/sql/01-roles.sql). Se ejecuta como `dbadmin` pasando contraseñas con `-v migpass=... -v apppass=...`.

- En RDS `dbadmin` no es superusuario: el script se concede `migrator` temporalmente para poder fijar los privilegios por defecto y lo revoca.

- Extensiones `uuid-ossp` y `pgcrypto` creadas como `dbadmin`.

  

### 2.7 Carga del esquema

```bat

docker run --rm -e PGPASSWORD=%MIGPASS% -v "%cd%\BackEnd\apps\MonoliticDataStructure\app\docker\init-scripts:/sql" -v "%cd%\infra:/certs" postgres:16 psql "host=%H% dbname=stockassistant user=migrator sslmode=verify-full sslrootcert=/certs/rds-global-bundle.pem" -v ON_ERROR_STOP=1 --single-transaction -f /sql/init.sql

```

Los avisos de transacción son inofensivos (el `init.sql` ya incluye `BEGIN`/`COMMIT`).

  

Verificación con `app`: lee datos y `create table` da `permission denied for schema public`.

  

### 2.8 Logs y retención

```bat

aws rds modify-db-parameter-group --db-parameter-group-name stockassistant-pg16 --parameters "ParameterName=log_connections,ParameterValue=1,ApplyMethod=immediate" "ParameterName=log_disconnections,ParameterValue=1,ApplyMethod=immediate" --region %R%

aws rds modify-db-instance --db-instance-identifier stockassistant-prod --cloudwatch-logs-export-configuration EnableLogTypes=postgresql --apply-immediately --region %R%

aws logs put-retention-policy --log-group-name /aws/rds/instance/stockassistant-prod/postgresql --retention-in-days 14 --region %R%

```

  

## 3. Modelo de seguridad

- RDS público porque la Lambda irá **sin VPC** (evita NAT, ~$32/mes). Compensación: SSL obligatorio, `verify-full`, contraseñas largas en SSM, usuarios sin DDL para la app, SG cerrado hasta probar la Lambda.

- `0.0.0.0/0` en 5432 se abre **solo** durante las pruebas de la Lambda y se vuelve a cerrar.

- `init_db()` / `create_all` del backend no deben ejecutarse con `app` (sin DDL): migraciones solo con `migrator`.

  

## 4. Pendiente

1. Smoke test Lambda: ECR + imagen de [Dockerfile.lambda](../BackEnd/apps/MonoliticDataStructure/app/Dockerfile.lambda) + Function URL `RESPONSE_STREAM` + `/health` y `/db-check`.

2. Probar streaming (decisión plan B el domingo por la noche).

3. Fase 1: embeddings OpenAI, adaptadores S3 Vectors, arranque seguro en Lambda (workers, `/tmp`), SSL en Postgres.

4. AWS Budgets con alertas.

  

## 5. Trabajo en equipo

Recomendación: desarrollo en Postgres local con `docker-compose`; el RDS es un único entorno compartido.

Para que un compañero acceda al RDS: su IP `/32` en el SG y un usuario propio (no compartir `app` ni `dbadmin`).

  

## 6. Recuperación rápida

| Necesito                   | Comando                                                                                                 |
| -------------------------- | ------------------------------------------------------------------------------------------------------- |
| Contraseña de un rol       | `aws ssm get-parameter --name /stockassistant/prod/db/<rol>_password --with-decryption ...`             |
| Actualizar la IP permitida | `infra\update-sg-ip.bat`                                                                                |
| Estado de RDS              | `aws rds describe-db-instances --db-instance-identifier stockassistant-prod --region eu-west-1`         |
| Parar RDS para ahorrar     | `aws rds stop-db-instance ...` (se reinicia solo a los 7 días; con deletion protection no impide parar) |