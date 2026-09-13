# Qdrant: configuración, uso y pruebas

> [!info] Alcance
> Esta guía documenta la integración de Qdrant con el backend de `MonoliticDataStructure`. PostgreSQL continúa siendo la fuente de datos operativos; Qdrant se utiliza para búsqueda semántica de productos.

## 1. Arquitectura

```text
products.csv / PostgreSQL
        |
        | product_name + description
        v
Sentence Transformers
        |
        | vector de 384 dimensiones
        v
Qdrant: colección products
        |
        v
Búsqueda semántica desde FastAPI
```

Qdrant almacena el vector y una metadata mínima del producto. El precio, stock, ventas y métricas no se usan como texto vectorial porque son datos operativos que pueden cambiar.

## 2. Componentes configurados

| Componente | Configuración |
|---|---|
| Servicio | `qdrant/qdrant:latest` |
| Contenedor | `supply_chain_qdrant` |
| API HTTP | `http://localhost:6333` |
| API gRPC | Puerto `6334` |
| Colección | `products` |
| Modelo | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Dimensión | `384` |
| Distancia | `Cosine` |
| Tamaño de lote | `128` productos |
| Persistencia | Volumen Docker `qdrant_data` |

Archivos principales:

- [`docker/docker-compose.yml`](../docker/docker-compose.yml)
- [`src/vector_store/product_indexer.py`](../src/vector_store/product_indexer.py)
- [`src/vector_store/embeddings.py`](../src/vector_store/embeddings.py)
- [`src/vector_store/search.py`](../src/vector_store/search.py)
- [`src/api/routes/products.py`](../src/api/routes/products.py)
- [`src/api/config.py`](../src/api/config.py)
- [`requirements/api.txt`](../requirements/api.txt)

## 3. Requisitos previos

- Docker Desktop iniciado.
- Python 3.14 o una versión compatible con el entorno del proyecto.
- Entorno virtual en `.venv`.
- Ejecutar los comandos desde:

```powershell
cd BackEnd/apps/MonoliticDataStructure/app
```

Las dependencias vectoriales son:

```text
qdrant-client==1.15.1
sentence-transformers==5.1.0
```

El modelo de embeddings necesita descargar sus archivos la primera vez. También se instala PyTorch como dependencia de `sentence-transformers`.

## 4. Instalar dependencias

Usar el intérprete del entorno virtual:

```powershell
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements/api.txt
```

La opción `--only-binary=:all:` evita compilaciones locales de dependencias nativas.

Comprobar la instalación:

```powershell
.\.venv\Scripts\python.exe -m pip check
```

Debe aparecer:

```text
No broken requirements found.
```

Comprobar los imports principales:

```powershell
.\.venv\Scripts\python.exe -c "import qdrant_client, sentence_transformers, torch; print('Dependencias vectoriales: OK')"
```

## 5. Iniciar Qdrant

Desde la carpeta `app`:

```powershell
docker compose -f docker/docker-compose.yml up -d qdrant
```

Consultar el estado del contenedor:

```powershell
docker compose -f docker/docker-compose.yml ps qdrant
```

Comprobar que Qdrant está preparado:

```powershell
Invoke-RestMethod http://localhost:6333/readyz
```

La respuesta esperada es:

```text
 passed
```

También puede abrirse el panel web de Qdrant en:

```text
http://localhost:6333/dashboard
```

Para detenerlo sin eliminar los datos:

```powershell
docker compose -f docker/docker-compose.yml stop qdrant
```

Para eliminar el contenedor y conservar el volumen:

```powershell
docker compose -f docker/docker-compose.yml down
```

> [!warning] Datos persistentes
> No uses `docker compose down -v` salvo que quieras eliminar también `qdrant_data` y perder la colección indexada.

## 6. Indexar productos

El indexador lee por defecto:

```text
data/generated/products.csv
```

Ejecutarlo:

```powershell
.\.venv\Scripts\python.exe -m src.vector_store.product_indexer
```

El texto enviado al modelo para cada producto es:

```text
product_name + description
```

La metadata almacenada en Qdrant contiene:

```json
{
  "product_id": "PRD0000001",
  "product_name": "...",
  "product_category": "Electronics",
  "brand": "...",
  "sku": "..."
}
```

El indexador trabaja por lotes y muestra mensajes como:

```text
Indexados 128 productos
Indexados 256 productos
...
Indexación completada: 200000 productos
```

### CSV alternativo

Se puede indicar otro fichero:

```powershell
.\.venv\Scripts\python.exe -m src.vector_store.product_indexer `
  --csv data/generated/products.csv
```

Cambiar el tamaño del lote:

```powershell
.\.venv\Scripts\python.exe -m src.vector_store.product_indexer `
  --batch-size 64
```

### Reindexación

El proceso es idempotente. Puede ejecutarse varias veces porque el ID de Qdrant se genera de forma estable a partir de `product_id` y se utiliza `upsert`.

Por tanto, reindexar actualiza los puntos existentes y no debería duplicarlos:

```powershell
.\.venv\Scripts\python.exe -m src.vector_store.product_indexer
```

## 7. Comprobar la colección

Consultar la configuración de la colección:

```powershell
Invoke-RestMethod http://localhost:6333/collections/products | ConvertTo-Json -Depth 10
```

Debe comprobarse que:

- La colección se llama `products`.
- El tamaño del vector es `384`.
- La distancia es `Cosine`.

Contar los puntos indexados:

```powershell
$body = '{"exact":true}'

Invoke-RestMethod `
  -Uri http://localhost:6333/collections/products/points/count `
  -Method Post `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 10
```

Con el CSV actual, el contador esperado es aproximadamente `200000`.

Para comprobar que no se duplican:

1. Anotar el contador actual.
2. Ejecutar otra vez el indexador.
3. Consultar el contador de nuevo.
4. Confirmar que el número no ha aumentado al doble.

Obtener algunos puntos de ejemplo:

```powershell
$body = '{"limit":2,"with_payload":true,"with_vector":false}'

Invoke-RestMethod `
  -Uri http://localhost:6333/collections/products/points/scroll `
  -Method Post `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 10
```

## 8. Probar la búsqueda semántica directamente en la API

La ruta implementada es:

```text
GET /api/v1/products/semantic-search
```

Primero iniciar la API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --reload --port 8000
```

> [!note] PostgreSQL
> `src.api.main` inicializa también la conexión SQLAlchemy. Si la API no arranca, inicia PostgreSQL con `docker compose` o revisa las variables `DB_*` del entorno.

Consulta básica:

```powershell
Invoke-RestMethod `
  "http://localhost:8000/api/v1/products/semantic-search?q=portatil%20gris%20con%20mucha%20memoria&limit=5" `
  | ConvertTo-Json -Depth 10
```

Consulta con filtro por categoría:

```powershell
Invoke-RestMethod `
  "http://localhost:8000/api/v1/products/semantic-search?q=producto%20para%20hacer%20deporte&category=Sports&limit=5" `
  | ConvertTo-Json -Depth 10
```

La respuesta tendrá esta forma:

```json
{
  "query": "portatil gris con mucha memoria",
  "items": [
    {
      "score": 0.82,
      "product_id": "PRD0000001",
      "product_name": "...",
      "product_category": "Electronics",
      "brand": "...",
      "sku": "..."
    }
  ]
}
```

El campo `score` representa la similitud calculada con distancia cosine. Un resultado con mayor score es más parecido a la consulta dentro de esa búsqueda.

## 9. Consultas recomendadas para validar calidad

Probar consultas que coincidan con los atributos generados:

```text
portátil gris con mucha memoria
producto electrónico con pantalla grande
ropa deportiva cómoda
mueble de madera para espacios pequeños
producto de belleza hidratante
producto para entrenar en casa
juego para niños
libro sobre tecnología
```

Para cada consulta revisar:

- Que los primeros resultados pertenecen a la categoría esperada.
- Que `product_name` y `description` tienen relación con la consulta.
- Que los scores son superiores a los resultados claramente irrelevantes.
- Que el filtro `category` limita los resultados correctamente.

## 10. Flujo de datos recomendado

```text
1. Generar o actualizar products.csv
2. Cargar PostgreSQL si procede
3. Arrancar Qdrant
4. Ejecutar el indexador
5. Comprobar colección y contador
6. Arrancar FastAPI
7. Probar búsquedas semánticas
```

PostgreSQL y Qdrant tienen responsabilidades distintas:

| Necesidad | Sistema |
|---|---|
| Producto y descripción original | PostgreSQL / CSV |
| Stock actual | PostgreSQL |
| Precio actual | PostgreSQL |
| Ventas y métricas | PostgreSQL |
| Similitud semántica | Qdrant |
| Filtros vectoriales por categoría | Qdrant payload |
| Respuesta operativa definitiva | PostgreSQL |

En una futura versión, Qdrant puede devolver los `product_id` relevantes y la API puede consultar después PostgreSQL para devolver stock y precio actualizados.

## 11. Configuración mediante `.env`

Los valores por defecto están en [`src/api/config.py`](../src/api/config.py). Pueden sobrescribirse mediante variables de entorno:

```env
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=products
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION=384
VECTOR_SEARCH_LIMIT=10
```

Si la API o el indexador se ejecutan dentro de otro contenedor de Docker, `QDRANT_URL` debe apuntar al nombre del servicio dentro de la red, por ejemplo:

```env
QDRANT_URL=http://qdrant:6333
```

Desde Windows ejecutando Python fuera de Docker se mantiene:

```env
QDRANT_URL=http://localhost:6333
```

## 12. Problemas habituales

### Docker no está disponible

Error típico:

```text
failed to connect to the Docker API
```

Solución:

1. Abrir Docker Desktop.
2. Esperar a que el motor Linux esté iniciado.
3. Repetir `docker info`.
4. Arrancar Qdrant de nuevo.

### Qdrant no responde en el puerto 6333

Comprobar:

```powershell
docker compose -f docker/docker-compose.yml ps qdrant
docker logs supply_chain_qdrant
Invoke-RestMethod http://localhost:6333/readyz
```

### La colección no existe

Ejecutar el indexador. `ensure_collection()` crea automáticamente `products` si no existe.

### El contador es cero

Comprobar que:

- Qdrant está iniciado.
- El CSV existe.
- El indexador se ejecutó desde la carpeta `app`.
- `QDRANT_URL` apunta al servidor correcto.

### Error de dimensión del vector

La colección debe usar dimensión `384`, porque el modelo configurado produce vectores de 384 componentes. No se debe cambiar el modelo sin recrear la colección o crear otra colección compatible.

### El modelo se descarga de nuevo

El modelo se carga en la caché local de Hugging Face. La primera descarga puede tardar; las ejecuciones posteriores reutilizan la caché mientras no se cambie `EMBEDDING_MODEL`.

### Se necesitan cambiar los textos vectorizados

Si cambia `product_name`, `description` o el modelo de embeddings:

1. Regenerar el CSV.
2. Confirmar que el modelo y dimensión son compatibles.
3. Ejecutar el indexador.
4. Repetir las consultas de calidad.

## 13. Checklist final

- [ ] Docker Desktop está iniciado.
- [ ] `qdrant` está en estado `running`.
- [ ] `/readyz` responde correctamente.
- [ ] La colección `products` existe.
- [ ] La dimensión es `384`.
- [ ] La distancia es `Cosine`.
- [ ] El contador coincide con los productos indexados.
- [ ] Reindexar no crea duplicados.
- [ ] Las consultas semánticas devuelven resultados relevantes.
- [ ] El filtro por categoría funciona.
- [ ] La API responde en `/api/v1/products/semantic-search`.
