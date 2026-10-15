# Prevision de ventas

El backend estima unidades mediante la media de despachos confirmados de los ultimos 90 dias. El LLM interpreta el resultado y sus limitaciones; no entrena un predictor ni modifica las cifras del backend.

Si el proveedor de IA falla, se conserva el calculo y se informa de la ausencia de analisis IA. La etiqueta trend es heredada y no demuestra una tendencia.

Validacion: suite local de 175 pruebas superadas y 7 omitidas antes del ultimo ajuste del prompt; las 2 pruebas especificas de IA pasan despues del ajuste. GUI comprobada con OpenAI y escenarios sinteticos de crecimiento y descenso.

Pendiente: mejorar y validar precision predictiva, estacionalidad y evidencia para promociones. Los resultados sinteticos no acreditan precision comercial real.
