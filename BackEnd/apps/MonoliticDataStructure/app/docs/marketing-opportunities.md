# Asistente de Marketing

## Alcance

Selecciona hasta tres productos con crecimiento de despachos y stock disponible,
consulta su interés público y propone una campaña breve para revisión humana.
No requiere una fecha comercial concreta. No publica, envía correos, reserva stock,
aplica descuentos ni crea pedidos. La consulta puede guardar evidencia externa
en la caché existente y el Ejecutivo conserva su auditoría habitual.

Se reutiliza el servicio de Tendencias y el proveedor de IA ya configurado.
No se modifica el generador anterior de contenido comercial ni los agentes automáticos.

## Selección calculada

- Compara los últimos 30 días completos UTC con los 30 anteriores.
- Solo incluye movimientos `dispatch` con cantidad firmada negativa.
- Mínimos: 10 unidades recientes, 5 anteriores y despachos en 3 días recientes distintos.
- Exige crecimiento y stock agregado disponible mayor que cero; resta reservas.
- Ordena por aumento absoluto, después por porcentaje y finalmente por ID.
- Devuelve hasta tres candidatos; con menos candidatos no rellena la lista.
- Si ninguno cumple los criterios, no consulta SerpAPI ni genera campañas con IA.

Las cantidades están en la unidad base de cada producto. El ranking absoluto
favorece aumentos en número de unidades: es un filtro sencillo de candidatos,
no una optimización económica entre unidades distintas o productos con distinto valor.
No interpreta días sin registros como ausencia demostrada de demanda y no incluye
el día en curso. No detecta aún productos que solo destacan en el mercado externo
sin crecimiento interno, ni productos nuevos sin una base mínima anterior.

## Evidencia externa y propuesta

El nombre del producto se usa literalmente como término de Google Trends en España.
No se inventa una categoría de búsqueda ni se consulta a nombre del usuario.
Si el nombre es demasiado largo o corto, o si no hay datos, se informa la limitación.
Los nombres genéricos, códigos internos o productos simulados pueden no tener resultados.

Cada candidato puede consumir dos consultas de SerpAPI: serie y relacionadas,
como en Tendencias. El máximo por ejecución es seis consultas externas. La duración
depende del proveedor y sus reintentos; mientras tanto el botón indica «Analizando…».
No hay un segundo análisis de IA por cada serie: una petición de Marketing redacta
las propuestas de todos los candidatos. Si se rechaza su formato o contenido, se permite
un único intento correctivo (máximo dos peticiones), manteniendo las validaciones.
No se reintenta desde Marketing un error del proveedor; se conserva la plantilla.

La respuesta incluye objetivo, hipótesis de público, canal sugerido, ejemplo de mensaje
y motivo. El modelo no modifica las cifras calculadas. Solo se aceptan los productos
recibidos y los canales web, email o redes sociales. Un mensaje con porcentajes,
importes o afirmaciones de descuentos/ofertas no autorizadas se rechaza. Se rechazan
también superlativos comunes como «la mejor calidad» o «perfectos». El prompt exige
mensajes neutrales y prohíbe atribuir prestaciones que no se han proporcionado.
Estas comprobaciones básicas no sustituyen la revisión humana de todo el texto generado.

`ai_attempts` distingue una respuesta aceptada, una rechazada por el validador y un
error del proveedor. No almacena prompts ni respuestas rechazadas completas.

Si falla la IA o su respuesta no es válida, se conservan borradores de plantilla
claramente identificados, junto a la evidencia. Si falla SerpAPI, puede proponerse
una campaña basada solo en crecimiento interno, sin afirmar que esté de moda.
El usuario debe revisar el texto generado y validar público, disponibilidad y margen.

## Acceso

- Menú **Resumen → Análisis de Marketing**, página propia `/marketing`, con la tarjeta «Oportunidades y campañas».
- Ejecutivo: `Busca oportunidades de marketing` o `Propón una campaña de marketing`.
- API: `POST /agents/marketing/opportunities`, cuerpo `{"limit":3,"country":"ES"}`.

El Ejecutivo utiliza la misma selección automática; un producto seleccionado en el
formulario no restringe esta consulta. No interpreta solicitudes de publicar campañas
como autorización para ejecutarlas. Solo prepara borradores.

## Validación

Pruebas: `tests/test_marketing_opportunities.py` y regresión de Tendencias/Ventas.
Cubren selección, mínimos, stock reservado, límites, periodos UTC, fuentes ausentes,
fallo de IA, IDs inventados, mensajes no autorizados, rutas del Ejecutivo y reutilización
de datos sin análisis de IA duplicados.

Compilar `Frontend` con `npm run build` y comprobar tipos con `npx tsc --noEmit`.
Probar después con el sandbox local y sus credenciales. La calidad de la campaña y
su conversión comercial requieren revisión humana y medición posterior.
