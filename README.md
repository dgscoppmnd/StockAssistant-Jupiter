# Proyecto Jupiter

Portal local: http://localhost:8080.

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


## Igntegracion a 8 septiembre de 2026

El resumen de la ultima integracion esta en Documentación\Integracion-Proyecto-Jupiter.md

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

Nginx conserva el prefijo `/api` del backend integrado y sirve `/media`; Vite también reenvía ambos. Compose incorpora reinicio automático, opciones de sesión y conectores, zona horaria y control del trabajador de automatizaciones. Las reglas nacen pausadas.

Para una base existente en otra instalación, los scripts de Docker no se ejecutan automáticamente sobre un volumen inicializado. Aplicar explícitamente la migración, después de respaldar esa base:

```powershell
docker cp BackEnd/apps/MonoliticDataStructure/app/docker/init-scripts/init.sql proyecto_jupiter_db:/tmp/jupiter-init.sql
docker exec proyecto_jupiter_db psql -U admin -d supply_chain -v ON_ERROR_STOP=1 -f /tmp/jupiter-init.sql

usuario local de desarrollo frontend: admin@stockassistant.app y Contraseña: Jupiter!2026Stock