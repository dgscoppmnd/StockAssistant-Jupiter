# RAG documental de Proyecto Jupiter

## Objetivo

Este modulo permite responder preguntas sobre documentos aprobados del proyecto sin mezclar esa informacion con el indice semantico de productos.

## Arquitectura

```text
PDF / Markdown / TXT -> lector -> fragmentacion -> embeddings -> Qdrant(jupiter_knowledge)
Pregunta -> embedding -> retrieval -> evidencia con citas -> LLM -> respuesta
```

La coleccion `products` sigue dedicada a catalogo. La coleccion `jupiter_knowledge` contiene conocimiento documental y almacena `source`, `source_type`, `page`, `chunk` y `text` como payload.

## Instalacion

```powershell
cd BackEnd/apps/MonoliticDataStructure/app
.\.venv\Scripts\python.exe -m pip install -r requirements/api.txt
docker compose -f docker/docker-compose.yml up -d qdrant
```

Configura un proveedor LLM existente en el proyecto. Por ejemplo, para OpenAI:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=tu_clave
OPENAI_MODEL=gpt-4.1-mini
```

Tambien se puede usar Ollama mediante las variables `AI_PROVIDER`, `OLLAMA_URL` y `OLLAMA_MODEL` existentes.

## Indexacion

Coloca PDF, Markdown o TXT en `data/knowledge` y ejecuta:

```powershell
.\.venv\Scripts\python.exe -m src.vector_store.knowledge
```

El proceso usa IDs estables y `upsert`, por lo que una reindexacion actualiza los fragmentos sin duplicarlos.

## Uso

Arranca la API y verifica primero la recuperacion:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --reload --port 8000
Invoke-RestMethod "http://localhost:8000/api/v1/knowledge/search?q=que%20datos%20son%20operativos" | ConvertTo-Json -Depth 8
```

Para solicitar una respuesta generada y sus citas:

```powershell
Invoke-RestMethod "http://localhost:8000/api/v1/knowledge/answer?q=para%20que%20sirve%20Qdrant" | ConvertTo-Json -Depth 8
```

Si la evidencia no alcanza el umbral de similitud, el endpoint responde que no hay informacion suficiente. Este comportamiento reduce alucinaciones y deja claro cuando hace falta incorporar un documento.

## Configuracion

```env
KNOWLEDGE_COLLECTION=jupiter_knowledge
KNOWLEDGE_SEARCH_LIMIT=5
KNOWLEDGE_SCORE_THRESHOLD=0.35
```
