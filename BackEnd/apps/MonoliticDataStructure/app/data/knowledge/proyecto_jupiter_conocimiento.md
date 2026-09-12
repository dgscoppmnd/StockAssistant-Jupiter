# Proyecto Jupiter: base de conocimiento

## Proposito

Proyecto Jupiter es una plataforma de apoyo para la gestion de inventario, productos, proveedores, ventas, logistica y metricas. El producto central, StockAssistant, combina una API FastAPI, una interfaz web y servicios de datos para ayudar a equipos operativos y ejecutivos.

## Componentes

La API principal expone rutas versionadas bajo `/api/v1` para productos, inventario, ventas, proveedores, logistica, metricas y analitica. El frontend se implementa con React y Vite. PostgreSQL conserva los datos operativos y Qdrant se reserva para recuperacion semantica.

## Regla de datos

El vector store no debe ser la fuente de verdad para precio, stock, ventas ni otros valores que cambian. La recuperacion vectorial encuentra contexto o identificadores y la API debe consultar PostgreSQL cuando necesita valores operativos actuales.

## RAG documental

El RAG documental utiliza la coleccion `jupiter_knowledge`, distinta de la coleccion `products`. Acepta PDF, Markdown y texto. Cada fragmento guarda fuente, tipo, pagina cuando aplica y numero de fragmento. Las respuestas se deben generar solo a partir de fragmentos recuperados y deben incluir sus citas.

## Flujo de actualizacion

1. Depositar los documentos aprobados en `data/knowledge`.
2. Iniciar Qdrant.
3. Ejecutar el indexador documental.
4. Consultar `/api/v1/knowledge/search` para evaluar recuperacion.
5. Consultar `/api/v1/knowledge/answer` cuando haya un proveedor LLM configurado.

## Limites

Si no hay evidencia suficiente, el asistente debe indicarlo claramente. El RAG no sustituye autorizaciones, politicas internas ni una consulta en tiempo real al sistema transaccional.

