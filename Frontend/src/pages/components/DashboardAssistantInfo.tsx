import InfoPopup from "./InfoPopup";

export default function DashboardAssistantInfo() {
  return <InfoPopup title="Cómo analizar las alertas con Stock Assistant" label="Información sobre Analizar con Stock Assistant">
    <p>Esta tarjeta te ayuda a <strong>consultar a Stock Assistant para interpretar el inventario y orientar una decisión de compra</strong>. Puedes pedir prioridades de reposición, explicaciones sobre riesgos o información de productos, según los datos disponibles.</p>
    <ol>
      <li><strong>Pulsa «Analizar con Stock Assistant».</strong> El botón sitúa el cursor en el campo de consulta del «Asistente operativo» del dashboard. Ese clic todavía no envía ninguna pregunta ni inicia un análisis.</li>
      <li><strong>Escribe qué necesitas analizar.</strong> Por ejemplo: «¿Qué productos tienen riesgo de rotura de stock y cuáles debería reponer primero?». Si preguntas por una alerta concreta, incluye el producto, la bodega y los datos relevantes que ves en pantalla.</li>
      <li><strong>Pulsa «Preguntar».</strong> La consulta se envía al agente StockAssistant con herramientas de consulta habilitadas. Según el texto, puede consultar riesgos de inventario o buscar productos en el catálogo. La búsqueda web está desactivada en este dashboard.</li>
      <li><strong>Revisa la respuesta y su justificación.</strong> El asistente responde en el historial e indica sus fuentes cuando existan. Contrasta las recomendaciones con las alertas, las compras prioritarias y la información disponible antes de tomar una decisión.</li>
    </ol>
    <table className="routing-info-table">
      <thead><tr><th scope="col">Qué quieres consultar</th><th scope="col">Qué debes hacer</th></tr></thead>
      <tbody>
        <tr><td>Qué productos conviene reponer primero</td><td>Pulsa <strong>Analizar con Stock Assistant</strong>, escribe una pregunta sobre prioridades de reposición y pulsa <strong>Preguntar</strong>.</td></tr>
        <tr><td>Por qué una alerta requiere atención</td><td>Incluye en la pregunta el <strong>producto, la bodega y los valores de la alerta</strong> que quieras interpretar.</td></tr>
        <tr><td>Qué riesgos de inventario existen</td><td>Pregunta por <strong>riesgos de inventario o roturas de stock</strong> para orientar la consulta hacia las herramientas de inventario.</td></tr>
        <tr><td>Información de un producto concreto</td><td>Escribe el <strong>nombre o código del producto</strong> y lo que necesitas saber. Esta tarjeta no tiene selectores de cliente ni producto.</td></tr>
      </tbody>
    </table>
    <p><strong>Qué contexto recibe el asistente:</strong> se envía el texto de tu pregunta. Las alertas, las filas de compras prioritarias y los gráficos visibles no se adjuntan automáticamente. Las herramientas recuperan información según la consulta; incluye los datos concretos que quieras que tenga en cuenta.</p>
    <p><strong>Período del análisis:</strong> el dashboard permite consultar 7, 30 o 90 días y muestra ese período como referencia junto a las respuestas. Actualmente ese selector no se envía al agente: su herramienta de riesgos de inventario utiliza un período de 30 días. Cambiar el selector no cambia ese período de la herramienta.</p>
    <p><strong>Historial:</strong> se muestran los seis mensajes más recientes y se conservan hasta veinte en este navegador. El historial visible no se envía con cada pregunta; incluye de nuevo el contexto necesario en las consultas siguientes.</p>
    <p><strong>Alcance de la recomendación:</strong> la calidad depende de los datos disponibles y no se utiliza una predicción entrenada en esta consulta. La respuesta es una orientación para revisar; <strong>no genera por sí sola propuestas de compra, no crea pedidos ni modifica inventario</strong>.</p>
  </InfoPopup>;
}
