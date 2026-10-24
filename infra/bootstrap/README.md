# Acceso de GitHub Actions a ECR Public

El job `backend-build` de `.github/workflows/deploy-aws.yml` inicia sesión en
ECR privado para subir la imagen y en `public.ecr.aws` para descargar Lambda Web
Adapter. El login público usa `us-east-1`, como exige AWS; el despliegue continúa
en `eu-west-1` (o en la región configurada en `AWS_REGION`).

## Aplicar los permisos con Terraform

1. Comprueba en GitHub, Settings > Environments > production, la variable
   `AWS_DEPLOY_ROLE_ARN`. Debe identificar el rol de despliegue que vas a actualizar.
   Este bootstrap define `stockassistant-github-deploy` y su política `deploy-app`.
2. Usa las credenciales administrativas habituales y el mismo estado local y
   variables con los que se aplicó originalmente este bootstrap. No inicialices
   un estado nuevo para recursos existentes. Este directorio tiene estado local;
   no utiliza el estado de `infra/envs/prod`.
3. Desde la raíz del proyecto, ejecuta:

   ```powershell
   terraform -chdir=infra/bootstrap init
   terraform -chdir=infra/bootstrap plan -out=ecr-public.tfplan
   ```

   Añade al comando `plan` el mismo `-var-file` o las mismas opciones `-var`
   del bootstrap original, si corresponde.
4. Revisa el plan: para este cambio solo se espera actualizar la política
   `deploy-app` del rol de GitHub con `ecr-public:GetAuthorizationToken` y
   `sts:GetServiceBearerToken`, sobre `Resource: "*"`. Si propone crear recursos
   existentes, borrar recursos o cambiar otros permisos, revisa el estado y las
   variables antes de continuar.
5. Aplica el plan revisado:

   ```powershell
   terraform -chdir=infra/bootstrap apply ecr-public.tfplan
   ```

## Alternativa desde la consola de AWS

Si no tienes disponible el estado original del bootstrap:

1. Abre IAM > Roles y selecciona el rol identificado por `AWS_DEPLOY_ROLE_ARN`.
2. En Permissions, abre la política inline `deploy-app` y edita su JSON.
3. Añade este objeto al array `Statement`, conservando los permisos existentes:

   ```json
   {
     "Sid": "EcrPublicLogin",
     "Effect": "Allow",
     "Action": [
       "ecr-public:GetAuthorizationToken",
       "sts:GetServiceBearerToken"
     ],
     "Resource": "*"
   }
   ```

4. Guarda la política. Si el rol real no tiene `deploy-app`, añade una política
   inline con `Version: "2012-10-17"` y este objeto en su array `Statement`.
5. El cambio ya está reflejado en `main.tf` para mantenerlo en futuras aplicaciones
   del bootstrap. No cambies el rol de ejecución de Lambda ni la relación de
   confianza OIDC para resolver este error.

## Publicar y comprobar

1. Publica el cambio del workflow en `master` después de actualizar IAM. Un push
   que cambie este workflow activa el despliegue según sus filtros actuales.
2. Para iniciarlo manualmente, abre Actions > Deploy AWS > Run workflow,
   selecciona `master` y el target `backend`.
3. Comprueba que el nuevo paso de login termina con `Login Succeeded`, que el
   build puede descargar el adaptador y que terminan correctamente las migraciones,
   la actualización de Lambda y el smoke test.
4. No uses solo "Re-run jobs" sobre la ejecución antigua: conserva la versión
   anterior del workflow. Usa una ejecución del commit que contiene el arreglo.

Referencias oficiales:

- [Autenticación de ECR Public](https://docs.aws.amazon.com/AmazonECR/latest/public/public-registry-auth.html)
- [Permisos para descargas autenticadas](https://docs.aws.amazon.com/AmazonECR/latest/public/docker-pull-ecr-image.html)
