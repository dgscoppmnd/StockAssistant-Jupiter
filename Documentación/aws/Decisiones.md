# Migración a AWS Serverless: decisiones de infraestructura

  

Rama: `feature/AWSConversion` · Región: `eu-west-1` · Estado: Fase 0 en curso

  

## 1. Contexto y restricciones

  

| Restricción        | Valor                                                                                                                                                      |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tipo de proyecto   | TFM: tráfico mínimo (pruebas propias, defensa, evaluación)                                                                                                 |
| Presupuesto máximo | 50 USD/mes (objetivo real: lo más bajo posible)                                                                                                            |
| Coste actual       | ~50-60 USD/mes (EC2 + RDS + EBS)                                                                                                                           |
| Tiempo disponible  | 4 días (fin de semana + lunes festivo)                                                                                                                     |
| Prioridad          | Eliminar costes fijos recurrentes sobre cualquier otra consideración                                                                                       |
| Plan B             | Si el domingo por la noche no hay avances claros: descartar la rama y pasar a **una única EC2** con Docker (backend + Qdrant + PostgreSQL), ~18-30 USD/mes |

  

**Punto de decisión (domingo noche):** el chat con streaming responde desde Lambda y `core` y `ai` corren con la misma imagen en local. Si no se cumple, se activa el plan B.

  

## 2. Decisiones tomadas

  

| Área                  | Decisión                                                                              | Alternativas descartadas y motivo                                                                                                                                                                                                                |
| --------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Cómputo               | **Una Lambda FastAPI** como imagen de contenedor (ECR) con **AWS Lambda Web Adapter** | Mangum: no hace streaming. Varias Lambdas: más complejidad sin necesidad con este tráfico                                                                                                                                                        |
| Entrada API           | **Lambda Function URL** con `RESPONSE_STREAM`, detrás de CloudFront                   | API Gateway HTTP API: no soporta streaming. REST API: más cara y más configuración (la diferencia de coste es irrelevante a este tráfico)                                                                                                        |
| Frontend              | S3 + CloudFront (OAC), ya desplegado                                                  | Sin cambios                                                                                                                                                                                                                                      |
| Autenticación         | **Google `id_token` validado en la Lambda** (lo que ya hace el backend)               | Cognito: añade Hosted UI, cambios en el SPA y un authorizer que la Function URL no usa. Se puede añadir en una iteración posterior                                                                                                               |
| PostgreSQL            | **RDS PostgreSQL `db.t4g.micro` actual, accesible públicamente** (Lambda sin VPC)     | Neon/Supabase: gratis y sin cambios de código, pero se elige RDS por ser nativo de AWS (IAM, backups, un solo proveedor). Aurora Serverless v2: coste mínimo > presupuesto o cold start de 15-30 s. DynamoDB: no encaja con las agregaciones SQL |
| Base vectorial        | **S3 Vectors** (coste fijo ~0)                                                        | Qdrant Cloud/EC2: coste fijo recurrente. Mantener Qdrant solo en el plan B                                                                                                                                                                       |
| Embeddings y LLM      | **OpenAI** (`text-embedding-3-small`, 1536 dimensiones; LLM sin cambios)              | Bedrock/Titan: exige acceso a modelos e IAM extra. `sentence-transformers`/`torch` se retiran (peso y cold start)                                                                                                                                |
| Ingesta de documentos | **S3 `ObjectCreated` → Lambda de ingesta** (misma imagen, otro handler)               | SQS + DLQ: complejidad innecesaria. Indexar de forma síncrona en la subida: choca con el límite de 6 MB de payload y el tiempo de petición                                                                                                       |
| Secretos              | **SSM Parameter Store (SecureString)**                                                | Variables de entorno en claro: no. Secrets Manager: coste por secreto                                                                                                                                                                            |
| IaC                   | **Terraform** con estado remoto en S3 y CI por OIDC de GitHub                         | SAM/CDK: peor encaje con S3 Vectors y el resto de piezas                                                                                                                                                                                         |
| Red                   | **Sin VPC**                                                                           | Evita NAT Gateway, RDS Proxy y endpoints de interfaz                                                                                                                                                                                             |

  

## 3. Arquitectura objetivo

  

```

Browser -> CloudFront --default--> S3 frontend (OAC)

                      \--/api/*--> Lambda Function URL (streaming) -> Lambda FastAPI (imagen ECR)

                                                       |-> RDS PostgreSQL (público, TLS forzado, usuario limitado)

                                                       |-> S3 Vectors (índices products y documents)

                                                       |-> OpenAI (LLM + embeddings)

                                                       |-> SSM Parameter Store (secretos)

Browser --PUT URL firmada--> S3 uploads --ObjectCreated--> Lambda ingesta -> OpenAI embeddings -> S3 Vectors + RDS

Google Identity: el backend valida el id_token

Observabilidad: CloudWatch Logs; costes: AWS Budgets

```

  

Diagrama editable: `docs/architecture/*.drawio`.

  

## 4. Hallazgos del código que condicionan la migración

  

Revisados en `BackEnd/apps/MonoliticDataStructure/app`.

  

| Hallazgo                                                                                                | Fichero                                                                                              | Impacto en Lambda                                                                                                                                                                              |
| ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dos hilos en segundo plano al arrancar (`start_knowledge_worker`, `start_automation_worker`)            | `src/api/main.py`, `src/knowledge_worker.py`, `src/executive_service.py`                             | Lambda congela el proceso entre invocaciones: los hilos no funcionan. Hay que desactivarlos en Lambda y sustituirlos por eventos (S3 → ingesta; EventBridge programado para la automatización) |
| Ficheros en disco local (`data/knowledge`, `/app/data/uploads`, ruta `/media`)                          | `src/knowledge_files.py`, `src/api/main.py`                                                          | El sistema de ficheros es de solo lectura salvo `/tmp`, y `mkdir` en `/app/data/uploads` falla al importar. Hay que usar S3 y rutas configurables                                              |
| `init_db()` y `Base.metadata.create_all` en el arranque                                                 | `src/api/main.py`                                                                                    | Se ejecutan en cada cold start. Mover las migraciones a un paso de CI                                                                                                                          |
| Dos colecciones Qdrant: `products` (MiniLM local) y `jupiter_documents_<hash>` (por proveedor y modelo) | `src/vector_store/*`, `src/knowledge_vectors.py`                                                     | Dos índices en S3 Vectors. Se reindexa todo con OpenAI                                                                                                                                         |
| Búsqueda documental con filtro `has_id` de Qdrant                                                       | `src/knowledge_vectors.py` (`search`)                                                                | S3 Vectors filtra por metadatos (no por lista de claves): hay que guardar `chunk_id` o `document_id` como metadato filtrable y comprobar los límites de `$in`                                  |
| Los chunks ya viven en PostgreSQL (`knowledge_chunks.content`)                                          | `docker/init-scripts/init.sql`                                                                       | Reindexar no exige reprocesar PDFs: se leen los chunks de la base de datos                                                                                                                     |
| Embeddings ya soportan proveedor `openai`                                                               | `src/knowledge_vectors.py`                                                                           | Poco cambio en documentos. Productos usan `sentence_transformers` y sí requieren cambio (`src/vector_store/embeddings.py`)                                                                     |
| Acceso a PostgreSQL con `psycopg2` y SQLAlchemy, sin SSL                                                | `src/DataBaseManagement/dbConectionPostgres.py`, `src/api/database.py`, `src/database/connection.py` | Añadir `sslmode=verify-full` en todos los puntos de conexión                                                                                                                                   |
| OCR con Tesseract y `pypdfium2`                                                                         | `requirements/knowledge.txt`, `Dockerfile`                                                           | Aumenta el peso de la imagen. Valorar si el OCR corre en la Lambda de ingesta o se descarta                                                                                                    |
| Autenticación propia con claves API, secreto de sesión y Google                                         | `docker-compose.yml`, `src/auth_service.py`, `src/security.py`                                       | Pasar los secretos a SSM. No usar valores por defecto en producción                                                                                                                            |
| `MLStockPredictTool` (AutoML)                                                                           | `BackEnd/apps/MLStockPredictTool`                                                                    | Fuera de alcance de esta migración                                                                                                                                                             |

  

## 5. Coste estimado (aproximado, sin verificar)

  

| Partida | USD/mes |
|---|---|
| RDS `db.t4g.micro` + almacenamiento | ~15-16 |
| IPv4 pública del RDS | ~3,7 |
| Lambda + Function URL + CloudFront + S3 + S3 Vectors + SSM + CloudWatch | ~1-5 |
| OpenAI (embeddings y LLM) | variable, ver sección 7 |
| **Total AWS** | **~20-25** |

  

Verifica los precios con la calculadora de AWS en `eu-west-1`. Si la cuenta tiene créditos o free tier, baja.

  

## 6. RDS accesible públicamente: lista de comprobación

  

1. El grupo de subredes del RDS debe tener ruta a un **Internet Gateway**. Con "Publicly accessible = Yes" y subredes sin esa ruta la base sigue sin ser alcanzable. Si no la tiene, restaura un snapshot en una instancia nueva en subredes públicas.

2. Security group: TCP 5432 desde `0.0.0.0/0` (Lambda sin VPC no tiene IP fija).

3. Parameter group: `rds.force_ssl = 1`. En el cliente, `sslmode=verify-full` con el bundle `global-bundle.pem` de RDS.

4. Usuario de aplicación con permisos limitados y otro de migraciones. La Lambda nunca usa el administrador.

5. Contraseña larga en SSM SecureString. Mejora opcional: autenticación IAM de base de datos.

6. Backups a 7 días, protección contra borrado y alarma de CloudWatch sobre `DatabaseConnections`.

7. `reserved concurrency` baja (por ejemplo 10): un `t4g.micro` tiene pocas conexiones máximas. Una conexión por contenedor, sin pool grande.

  

## 7. Cómo presupuestar los embeddings

  

Qdrant cuenta puntos, pero el coste depende de los **tokens**. El texto de cada chunk ya está en PostgreSQL, así que es mejor medirlo allí.

  

### 7.1 Puntos y dimensión en Qdrant (PowerShell, Qdrant local en `:6333`)

  

Levanta Qdrant primero: `docker compose -f docker/docker-compose.yml up -d qdrant`.

  

```powershell

$base = "http://localhost:6333"

# Si usas API key: -Headers @{ "api-key" = "<clave>" } en cada llamada

  

$cols = (Invoke-RestMethod "$base/collections").result.collections

$cols | ForEach-Object {

  $c = Invoke-RestMethod "$base/collections/$($_.name)"

  $n = (Invoke-RestMethod -Method Post -Uri "$base/collections/$($_.name)/points/count" `

        -ContentType "application/json" -Body '{"exact":true}').result.count

  [pscustomobject]@{ coleccion=$_.name; puntos_exactos=$n; dimension=$c.result.config.params.vectors.size; distancia=$c.result.config.params.vectors.distance }

} | Format-Table -AutoSize

```

  

Anota `products` y cada `jupiter_documents_<hash>`. Puede haber varias colecciones de documentos por perfil de embedding antiguo: solo cuenta lo que vayas a reindexar.

  

### 7.2 Tokens reales en PostgreSQL (fuente de verdad)

  

```sql

-- Chunks documentales

SELECT embedding_provider, embedding_model,

       count(*)            AS chunks,

       sum(length(content)) AS caracteres,

       round(avg(length(content))) AS media_caracteres

FROM public.knowledge_chunks

GROUP BY 1, 2;

  

-- Documentos activos

SELECT count(*) AS documentos, sum(length(content)) AS caracteres

FROM public.knowledge_documents WHERE is_active;

  

-- Productos (texto semántico aproximado)

SELECT count(*) FROM public.products;

```

  

Ajusta el nombre de la tabla de productos si en tu esquema es otro.

  

### 7.3 Fórmula

  

```

tokens ≈ caracteres / 3.5            (español; usa /4 para inglés)

coste  = tokens / 1.000.000 × precio_por_millón

```

  

| Dato de referencia (verifica en la página de precios de OpenAI) | Valor |
|---|---|
| `text-embedding-3-small` | ~0,02 USD por millón de tokens |
| Dimensión por defecto | 1536 |

  

Ejemplo ilustrativo: 20.000 chunks × 800 caracteres = 16 M caracteres ≈ 4,6 M tokens ≈ **0,09 USD**. Reindexar cuesta céntimos; el gasto relevante es el del LLM de chat.

  

Almacenamiento en S3 Vectors: cada vector de 1536 dimensiones float32 ocupa ~6 KB, así que 100.000 vectores ≈ 0,6 GB.

  

## 8. Plan por fases (resumen)

  

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Presupuesto, S3 Vectors, ECR, S3 de uploads, SSM, RDS público, bootstrap de Terraform, imagen `/health` + Function URL + CloudFront | **En curso** |
| 1 | Refactor: embeddings OpenAI, `search.py`/`product_indexer.py`/`knowledge_vectors.py` a S3 Vectors, rutas y workers para Lambda, SSL en PostgreSQL, subidas con URL firmada | Pendiente |
| 2 | Reindexado de productos y documentos desde PostgreSQL (script idempotente) | Pendiente |
| 3 | Validación de Google `id_token`, CORS, CloudFront en `/api/*` | Pendiente |
| 4 | Pruebas de carga, memoria y timeout, alarmas | Pendiente |
| 5 | Corte de tráfico y apagado de EC2/Qdrant tras snapshots | Pendiente |

  

## 9. Puntos por verificar antes de avanzar

  

- [ ] S3 Vectors disponible en `eu-west-1` y límites vigentes (metadatos filtrables, `top_k`, operadores `$in`).

- [ ] El grupo de subredes del RDS tiene ruta a un Internet Gateway.

- [ ] Tamaño real de la imagen de contenedor con las dependencias definitivas (sin `torch`).

- [ ] Streaming de FastAPI (`StreamingResponse`) con Web Adapter en modo `response_stream`.

- [ ] Qué hace `executive_service` en su hilo de automatización y cómo programarlo con EventBridge.

- [ ] Versión del provider de AWS para Terraform con `aws_s3vectors_*` (la pin actual es `>= 6.0`; ajusta si `terraform init` lo rechaza).