import InfoPopup from "./InfoPopup";

export default function DashboardAssistantInfo() {
  return <InfoPopup title="Cómo analizar las alertas con Stock Assistant" label="Información sobre Analizar con Stock Assistant">
    <p>Esta tarjeta te ayuda a <strong>consultar a Stock Assistant para interpretar el inventario y orientar una decisión de compra</strong>. Puedes pedir prioridades de reposición, explicaciones sobre riesgos o información de productos, según los datos disponibles.</p>
    <ol>
      <li><strong>Pulsa «Analizar con Stock Assistant».</strong> El botón sitúa el cursor en el campo de consulta del «Asistente operativo» del dashboard. Ese clic todavía no envía ninguna pregunta ni inicia un análisis.</li>
      <li><strong>Escribe qué necesitas analizar.</strong> Por ejemplo: «Crea un plan de compras con las alertas». Puedes limitarlo a un producto, almacén, referencias críticas o presupuesto con moneda, como «solo los críticos, hasta 500 EUR».</li>
      <li><strong>Pulsa «Preguntar».</strong> El agente interpreta la petición y consulta inventario, alertas y datos de compra cuando corresponda. La búsqueda web está desactivada en este dashboard.</li>
      <li><strong>Revisa la respuesta y su justificación.</strong> El asistente responde en el historial e indica sus fuentes cuando existan. Contrasta las recomendaciones con las alertas, las compras prioritarias y la información disponible antes de tomar una decisión.</li>
    </ol>
    <table className="routing-info-table">
      <thead><tr><th scope="col">Qué quieres consultar</th><th scope="col">Qué debes hacer</th></tr></thead>
      <tbody>
        <tr><td>Qué productos conviene reponer primero</td><td>Pulsa <strong>Analizar con Stock Assistant</strong>, escribe una pregunta sobre prioridades de reposición y pulsa <strong>Preguntar</strong>.</td></tr>
        <tr><td>Por qué una alerta requiere atención</td><td>Indica el <strong>producto o la bodega</strong>. El agente recupera las alertas actuales desde la aplicación.</td></tr>
        <tr><td>Qué riesgos de inventario existen</td><td>Pregunta por <strong>riesgos de inventario o roturas de stock</strong> para orientar la consulta hacia las herramientas de inventario.</td></tr>
        <tr><td>Información de un producto concreto</td><td>Escribe el <strong>nombre o código del producto</strong> y lo que necesitas saber. Esta tarjeta no tiene selectores de cliente ni producto.</td></tr>
      </tbody>
    </table>
    <p><strong>Qué contexto recibe el asistente:</strong> tu pregunta, el período seleccionado y los últimos ocho mensajes. Las herramientas recuperan las alertas, prioridades e indicadores actuales desde el backend; los datos pueden haber cambiado desde la última actualización de la pantalla.</p>
    <p><strong>Período del análisis:</strong> el selector de 7, 30 o 90 días se envía al agente y se usa en los indicadores de actividad. Las existencias, la demanda pendiente y los pedidos en curso corresponden al estado actual.</p>
    <p><strong>Planes de compras:</strong> las cantidades descuentan reservas y compras pendientes. Los precios proceden de recepciones confirmadas y son estimaciones históricas por unidad base; si no existen, se indica «Coste no disponible». Los totales se separan por moneda, sin impuestos ni transporte. Con presupuesto, se priorizan lotes completos y se muestran las exclusiones.</p>
    <p><strong>Historial y borradores:</strong> se conservan hasta veinte mensajes por usuario en este navegador. Puedes guardar una propuesta como borrador local, volver a abrirla y descargarla en CSV. Una versión guardada conserva la fecha de consulta: pregunta de nuevo para actualizarla.</p>
    <p><strong>Alcance:</strong> el agente explica los resultados y prepara propuestas para revisión. <strong>No crea pedidos ni modifica la base de datos o el inventario.</strong></p>
  </InfoPopup>;
}
