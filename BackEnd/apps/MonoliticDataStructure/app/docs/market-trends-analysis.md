# Análisis de Tendencias

La tarjeta de Inteligencia de mercado consulta Google Trends mediante SerpAPI
para un producto o categoría, en España y durante los últimos doce meses.
No necesita un producto seleccionado ni modifica inventario o pedidos.

## Flujo

1. El botón muestra «Consultando…» y bloquea nuevos envíos mientras espera.
2. Se consulta `TIMESERIES`, se validan y ordenan los valores del índice 0–100
   y se guarda la respuesta con su referencia en la caché existente.
3. Cuando existen observaciones válidas, otra consulta `RELATED_QUERIES` obtiene
   búsquedas relacionadas. Esta segunda petición puede consumir otra consulta
   de la cuota de SerpAPI. Su fallo no impide mostrar la serie.
4. El código infiere la duración de los intervalos a partir de sus timestamps
   y excluye de la comparación los que no han terminado a la hora UTC de consulta.
   Compara los últimos cuatro intervalos terminados con los cuatro anteriores,
   si son consecutivos. Publica medias, diferencia en puntos, fechas de bloques,
   mínimo y máximo históricos y fechas del máximo. No es un modelo predictivo.
5. El proveedor de IA configurado recibe esas métricas y las consultas relacionadas
   para explicar señales y proponer acciones que se deberán validar. Tiene un
   límite de tiempo y tokens. Si falla, se conserva un resumen calculado.
6. La tarjeta muestra gráfico, tabla desplegable, relacionadas, explicación,
   advertencias, fecha y detalles técnicos.

## Ejecutivo

Ejemplos: `Analiza las tendencias de auriculares inalámbricos` y
`Analiza las tendencias de "auriculares inalámbricos"`.
Se aceptan comillas completas o una comilla de apertura sin cerrar. También se
reconocen términos después de expresiones como «tendencias de» o «tendencias sobre».
Sin un término concreto o ante varios términos ambiguos se pide aclaración,
en lugar de buscar la pregunta entera. El Ejecutivo usa
la misma función de análisis y muestra su explicación y evidencia técnica.
No se modifica la selección general de agentes por palabras clave.

## Estados

- `ok`: hay observaciones válidas; puede faltar IA o consultas relacionadas.
- `no_data`: el proveedor respondió sin observaciones válidas; no se invoca IA.
- `source_unavailable`: falta configuración o la consulta externa falla.
- `needs_clarification`: el Ejecutivo necesita un término concreto o una consulta menos ambigua.

Un índice cero es válido; una respuesta con un diccionario vacío no se considera
éxito. Se omiten duplicados, valores no numéricos o fuera de rango y observaciones
marcadas como parciales. El gráfico puede incluir un intervalo en curso sin
incorporarlo a las medias comparadas; su duración se infiere de los intervalos
observados, no de las etiquetas de fecha. La IA recibe también la serie y los
extremos históricos para distinguir picos anuales de cambios recientes.
No se afirma que exista estacionalidad, causalidad,
demanda futura o rentabilidad a partir de esta comparación.

## Verificación

Desde la carpeta del backend, con `src` y `.` en `PYTHONPATH`:

```text
python -m pytest tests/test_market_trends.py tests/test_external_connectors.py -q
```

Desde `Frontend`: `npm run build` y `npx tsc --noEmit`.

Probar en la GUI un término con datos, una fuente no disponible, una respuesta
vacía y el comportamiento del botón. Probar también el ejemplo del Ejecutivo.
Los tests usan respuestas controladas: no acreditan una llamada real a SerpAPI
ni la calidad de una explicación generada con credenciales del usuario.

No se modifican los iconos de información en esta entrega.
