# Proyecto Jupiter

Portal local: [http://localhost:8080](http://localhost:8080).

- [Instalación y actualización](readmeIntalacion.md).
- [Contenido, arquitectura y funcionalidades](readmeContenido.md).

[Integración, esquema, arranque y verificaciones](Documentación/Integracion-Proyecto-Jupiter.md).


```
Usuario
   │
   ▼
Agente Ejecutivo
   │
 ├── Agente Stock
 ├── Agente Compras
 ├── Agente Ventas
 ├── Agente Finanzas
 ├── Agente Competencia
 ├── Agente SEO
 ├── Agente Clientes
 ├── Agente Riesgos
 └── Agente Tendencias
        │
        ▼
PostgreSQL
Ollama
APIs externas
```
# Datos de backend

| Agente | Modelo recomendado | Nota |
|---|---|---|
| Compras inteligente | `qwen3:14b` | Comparar ofertas, interpretar fichas y justificar recomendaciones. Los precios, descuentos y costes se calculan en código. |
| Gestión de stock | Predictor estadístico + `qwen3:4b-instruct` | Las predicciones deben salir de SQL/Python, no del LLM; el modelo explica alertas y sugerencias. |
| Predicción de ventas | Predictor estadístico + `qwen3:8b` | Series temporales para la previsión; el LLM analiza estacionalidad y propone promociones. |
| Financiero | SQL/código + `qwen3:4b-instruct` | Márgenes, beneficios y rentabilidad deben ser cálculos deterministas. |
| Valoraciones | `qwen3:8b` o `qwen3:14b` | Resumen, clasificación de sentimientos y detección de problemas en lotes de reseñas. |
| Competencia | `qwen3:4b-instruct` | Extrae cambios relevantes de precios y catálogos ya recolectados por scrapers. |
| Comercial | `qwen3:14b` | Redacción SEO, títulos, emails y redes sociales requieren mejor calidad lingüística. |
| Atención al cliente | `qwen3:14b` + `embeddinggemma` | Chat con RAG sobre catálogo, políticas y stock en tiempo real. |
| Compras automáticas | Reglas deterministas + `qwen3:4b-instruct` | El modelo puede redactar y validar la solicitud; la aprobación y creación del pedido deben controlarse con código. |
| Riesgos | Detección de anomalías + `qwen3:8b` | Detecta señales numéricas y sintetiza causas, impacto y recomendaciones. |
| Inteligencia de mercado | `qwen3:14b` | Analiza tendencias y fuentes externas, y propone oportunidades con evidencia. |
| Ejecutivo / Manager IA | `qwen3:14b` | Decide qué herramientas o agentes consultar y resume resultados. No debería aprobar ni ejecutar compras por sí solo. |


## Integración a 8 de septiembre de 2026

El resumen de integración está en [Documentación de integración](Documentación/Integracion-Proyecto-Jupiter.md). El commit `3369c4082bb2194550df90641c97e049f0f1d94b` está integrado: incorpora Qdrant, embeddings multilingües, indexación de productos desde CSV y el endpoint `/api/v1/products/semantic-search`.

La búsqueda vectorial utiliza el catálogo analítico y no se sincroniza automáticamente con los productos operativos del portal. No hay una pantalla específica de búsqueda semántica en el frontend actual. Es necesario indexar un CSV propio para obtener resultados; la instalación no precarga un catálogo vectorial.

## Resumen de Arranque

Desde la raíz del repositorio, en PowerShell:

```powershell
$compose = 'BackEnd/apps/MonoliticDataStructure/app/docker/docker-compose.yml'
docker compose -f $compose up -d --build
```

- Portal compilado en Nginx: <http://localhost:8080>.
- Desarrollo Vite: <http://localhost:5173>.
- API y documentación: <http://localhost:8000/docs>.
- PostgreSQL: puerto local 5433; pgAdmin: <http://localhost:5050>.
- Qdrant: <http://localhost:6333/dashboard>; API HTTP en 6333 y gRPC en 6334.

Nginx conserva el prefijo `/api` del backend integrado y sirve `/media`; Vite también reenvía ambos. Compose incorpora reinicio automático, opciones de sesión y conectores, zona horaria y control del trabajador de automatizaciones. Las reglas nacen pausadas.

Para una base existente en otra instalación, los scripts de Docker no se ejecutan automáticamente sobre un volumen inicializado. Aplicar explícitamente la migración, después de respaldar esa base:

```powershell
docker cp BackEnd/apps/MonoliticDataStructure/app/docker/init-scripts/init.sql proyecto_jupiter_db:/tmp/jupiter-init.sql
docker exec proyecto_jupiter_db psql -U admin -d supply_chain -v ON_ERROR_STOP=1 -f /tmp/jupiter-init.sql
```

Reaplicar el esquema completo restablece las credenciales y el estado activo del administrador inicial. Para añadir solo los campos de productos, consulta la migración específica en [Instalación](readmeIntalacion.md).

Cuenta local de desarrollo: `admin@stockassistant.app`, contraseña `Jupiter!2026Stock`.

## Validación de la integración vectorial

Comprobación local del 8 de septiembre de 2026:

- Compilación del frontend completada correctamente.
- Login por el portal 8080, sesión, productos e inventario con respuesta HTTP 200.
- 14 pruebas de reglas y una prueba de integración vectorial superadas.
- Embeddings reales, indexación por lotes, reindexación sin duplicados, búsqueda por similitud, filtro de categoría y validación de consultas comprobados con datos temporales; la colección de prueba se eliminó al terminar.

Qdrant está fijado en `1.19.1` y su cliente Python en `1.19.0`. La imagen utiliza PyTorch `2.8.0` para CPU y NumPy `1.26.4` compatible con pandas `2.1.0`. La carga vectorial se realiza al invocar su ruta, sin bloquear el arranque del login. Si la colección aún no existe, la búsqueda devuelve `items: []`.

Las pruebas anteriores no certifican las integraciones externas de Google, Ollama, OpenAI o SerpAPI. Los comandos para repetirlas y diagnosticar un acceso lento están en [Instalación](readmeIntalacion.md).
