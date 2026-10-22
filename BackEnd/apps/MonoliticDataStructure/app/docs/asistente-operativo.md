# Asistente operativo: consultas y propuestas de compra

El dashboard usa `/api/agents/stockassistant/chat`. Envía el período seleccionado,
el contexto `dashboard` y los ocho mensajes recientes. El agente interpreta la
petición mediante una salida estructurada validada y selecciona consultas de
inventario, catálogo o una propuesta de compras. Después responde usando la
evidencia recuperada. El historial se trata como contexto no verificado.

## Propuesta calculada

`src/purchase_plan.py` usa exclusivamente SELECT sobre tablas existentes. No
requiere migraciones, escrituras, ofertas externas ni nuevos paquetes.

- Disponible = físico menos reservas.
- Demanda adicional = pedidos de venta pendientes sin reservar.
- Suministro pendiente = líneas pendientes de pedidos de compra activos,
  excluidos borradores, cancelados y recibidos.
- Déficit = máximo de cero y punto de reposición + demanda adicional − disponible
  − suministro pendiente.
- Con déficit, se propone el máximo entre déficit y lote de reposición. Si el
  disponible neto alcanza el umbral y no hay suministro pendiente, se propone el
  lote configurado. Una configuración sin objetivo ni lote se identifica como pendiente.
- Se excluyen excesos y necesidades ya cubiertas por pedidos en curso.
- Se utiliza el último precio positivo de una recepción confirmada en la misma
  unidad base. Se muestra proveedor, fecha y moneda. No se equiparan precios de
  catálogo o venta a costes de compra. Los precios históricos no son ofertas vigentes.
- Se calculan importes con Decimal y redondeo monetario a dos decimales. Los
  totales se separan por moneda, sin impuestos, transporte ni conversión.
- Con presupuesto y moneda explícitos, se seleccionan lotes completos por
  prioridad hasta el límite. Se identifican los lotes que no caben y los que
  carecen de valoración en esa moneda. No es una optimización global del presupuesto.
- Se evalúan hasta `max_tool_results` candidatos (100 en el dashboard), después
  de filtrar por producto, almacén y criticidad. Se informa del recorte y los
  totales solo cubren la selección evaluada.

Los indicadores de actividad respetan el período solicitado; el stock y los
pedidos representan el estado actual. Las consultas de riesgos existentes
incluyen hasta 16 alertas y 12 prioridades; el plan usa su propia consulta de
candidatos y no está limitado por esas tarjetas.

## Conversación y persistencia

La respuesta del agente se acompaña de una tabla calculada y metadatos de las
consultas ejecutadas. Si la interpretación estructurada falla, se recupera una
consulta general cuando se reconoce la intención, mostrando una advertencia
de que no se han aplicado los filtros ni el presupuesto. No se sustituye el
agente por respuestas prefijadas: se necesita un proveedor IA disponible para
responder a consultas operativas.

Se conservan hasta veinte mensajes por usuario en el navegador. «Guardar borrador
local» conserva la propuesta; «Abrir borrador local» la incorpora al historial
para consultarla o ajustarla mediante el agente. Cada nueva propuesta vuelve a
consultar los datos. El CSV incluye líneas, exclusiones, costes, fecha y supuestos.
Estas acciones no crean pedidos ni propuestas persistentes en el servidor.

## Verificación sin datos reales

- Backend: `python -m unittest discover -s tests -p test_operational_assistant.py`.
  Requiere las dependencias normales del backend, con `PYTHONPATH` apuntando a la
  carpeta de la aplicación y a `src`. Todos los proveedores y conexiones se simulan.
- Frontend: `node --test tests/operational-assistant.test.mjs`,
  `node node_modules/typescript/bin/tsc --noEmit` y `npm run build`.
