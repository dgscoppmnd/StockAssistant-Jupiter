# StockAssistant-Jupiter


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