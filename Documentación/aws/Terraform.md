github_deploy_role_arn = "arn:aws:iam::118645514410:role/stockassistant-github-deploy"
state_bucket = "stockassistant-tfstate-118645514410"

# Flujo de trabajo con Terraform — StockAssistant

Este documento describe cómo usar Terraform en el proyecto StockAssistant,
desde la configuración inicial hasta el despliegue de la infraestructura.

##  Estructura de carpetas

```
infra/
├── bootstrap/          # Proyecto Terraform para el estado remoto y OIDC
│   ├── main.tf
│   └── terraform.tfstate   (local, NO subir a Git)
├── envs/
│   └── prod/           # Proyecto Terraform del entorno de producción
│       ├── main.tf
│       ├── backend.hcl
│       └── ...
└── modules/            # (Opcional) Módulos reutilizables
```

##  Requisitos previos

1. **AWS CLI instalado** y configurado con SSO:

   ```bash
   aws configure sso
   ```

   Perfil usado en este proyecto: `AdministratorAccess-118645514410`

2. **Terraform ≥ 1.10** instalado:

   ```bash
   terraform -version
   ```

3. **Variable de entorno del perfil AWS** (recomendado):

   ```powershell
   $env:AWS_PROFILE = "AdministratorAccess-118645514410"
   ```

   O en CMD:

   ```cmd
   set AWS_PROFILE=AdministratorAccess-118645514410
   ```

##  Fase 1: Bootstrap (solo una vez)

La carpeta `infra/bootstrap/` crea el bucket S3 donde se guardará el estado
remoto de Terraform, además del proveedor OIDC de GitHub y el rol de despliegue.

### Ejecutar

```bash
cd infra/bootstrap
terraform init
terraform apply -var state_bucket_name=stockassistant-tfstate-118645514410
```

### Outputs

- `state_bucket`: nombre del bucket creado.
- `github_deploy_role_arn`: ARN del rol que usará GitHub Actions.

### Notas

- El estado de este bootstrap es **local** (`terraform.tfstate`).
- El bucket tiene `prevent_destroy = true` para evitar borrados accidentales.
- Si la cuenta ya tiene el proveedor OIDC de GitHub, poner
  `create_github_oidc_provider = false`.

##  Fase 2: Entorno de producción

La carpeta `infra/envs/prod/` contiene la infraestructura real del TFM.

### Configuración del backend (`backend.hcl`)

```hcl
bucket       = "stockassistant-tfstate-118645514410"
key          = "envs/prod/terraform.tfstate"
region       = "eu-west-1"
use_lockfile = true
encrypt      = true
```

 **Importante**: el nombre del bucket debe coincidir **exactamente** con el
creado en el bootstrap. No duplicar el prefijo.

### Ejecutar

```bash
cd infra/envs/prod
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

### Comandos útiles

| Comando | Descripción |
|---------|-------------|
| `terraform init -backend-config=backend.hcl` | Inicializa el backend remoto |
| `terraform plan` | Muestra los cambios antes de aplicar |
| `terraform apply` | Aplica los cambios |
| `terraform destroy` | Destruye la infraestructura (¡cuidado!) |
| `terraform state list` | Lista los recursos gestionados |
| `terraform output` | Muestra los outputs definidos |

##  Flujo típico de trabajo

1. Activar el perfil AWS:

   ```powershell
   $env:AWS_PROFILE = "AdministratorAccess-118645514410"
   ```

2. Ir al entorno deseado:

   ```bash
   cd infra/envs/prod
   ```

3. Inicializar (solo si cambia el backend o es la primera vez):

   ```bash
   terraform init -backend-config=backend.hcl
   ```

4. Revisar cambios:

   ```bash
   terraform plan
   ```

5. Aplicar:

   ```bash
   terraform apply
   ```

6. Si se cambia el código, repetir desde el paso 4.

##  Limpieza

Para destruir la infraestructura de producción:

```bash
cd infra/envs/prod
terraform destroy
```

Para destruir el bootstrap (requiere quitar `prevent_destroy`):

```bash
cd infra/bootstrap
# Editar main.tf y comentar prevent_destroy = true
terraform apply -var state_bucket_name=stockassistant-tfstate-118645514410
terraform destroy -var state_bucket_name=stockassistant-tfstate-118645514410
```

##  Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `No valid credential sources found` | Falta el perfil AWS | Exportar `AWS_PROFILE` o añadir `profile` al provider |
| `S3 bucket does not exist` | Nombre del bucket mal escrito en `backend.hcl` | Corregir el nombre para que coincida con el bootstrap |
| `Error acquiring the state lock` | Otra ejecución en curso | Esperar o eliminar el lock manualmente |
| `prevent_destroy` | Intento de borrar el bucket de estado | Comentar la línea y aplicar |

## Buenas prácticas

- **Nunca** subir `terraform.tfstate` ni `.terraform/` a Git.
- Usar `terraform fmt` para formatear el código.
- Usar `terraform validate` para comprobar la sintaxis.
- Versionar el código en Git, pero no el estado.
- Mantener el estado remoto en S3 con versionado y cifrado.
- Acotar los permisos del rol de GitHub Actions cuando la infraestructura
  esté estable (evitar `AdministratorAccess`).