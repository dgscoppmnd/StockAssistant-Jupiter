import InfoPopup from "./InfoPopup";

export default function CustomerSupportInfo() {
  return <InfoPopup title="Cómo funciona el asistente con fuentes vigentes" label="Información sobre el asistente con fuentes vigentes">
    <p>Esta tarjeta permite <strong>conversar sobre políticas, procedimientos y documentos de la Base de conocimiento</strong>. El asistente busca fragmentos relacionados con tu pregunta y utiliza esa evidencia para preparar la respuesta. Puedes añadir un producto para consultar también su catálogo y stock actual.</p>
    <ol>
      <li><strong>Selecciona un producto solo si lo necesitas.</strong> Es opcional para preguntas documentales y necesario para incorporar el stock confirmado de un artículo. Este selector es independiente de los de las otras tarjetas.</li>
      <li><strong>Escribe una pregunta de entre 2 y 2000 caracteres y pulsa «Enviar».</strong> Mientras se consulta, los controles se bloquean y aparece un mensaje de progreso.</li>
      <li><strong>Revisa la respuesta y sus fuentes.</strong> Abre «Fuentes consultadas» para ver títulos, fragmentos, páginas y vigencia cuando estén disponibles. Si seleccionaste un producto y existen datos, aparece «Stock confirmado» por bodega.</li>
      <li><strong>Continúa la conversación o empieza otra.</strong> Puedes hacer preguntas de seguimiento. «Nueva conversación» limpia los mensajes y conserva el producto seleccionado. Cambiar o quitar el producto también limpia los mensajes.</li>
    </ol>
    <table className="routing-info-table">
      <thead><tr><th scope="col">Qué quieres consultar</th><th scope="col">Qué debes seleccionar o introducir</th></tr></thead>
      <tbody>
        <tr><td>Una política, un procedimiento o el contenido de un documento</td><td>Escribe una <strong>pregunta concreta</strong>. No necesitas seleccionar producto ni cliente.</td></tr>
        <tr><td>El stock actual de un artículo</td><td>Selecciona el <strong>producto</strong>, pregunta por su disponibilidad y revisa <strong>Stock confirmado</strong>.</td></tr>
        <tr><td>Comprobar en qué se basa una respuesta</td><td>Abre <strong>Fuentes consultadas</strong> y contrasta los fragmentos con las citas de la respuesta, como «[F1, p. N]».</td></tr>
        <tr><td>Entender por qué falta información documental</td><td>Revisa <strong>Documentos pendientes o incidencias</strong>, cuando aparezca, y comprueba el procesamiento y la vigencia en la Base de conocimiento.</td></tr>
        <tr><td>Iniciar otro tema sin el historial anterior</td><td>Pulsa <strong>Nueva conversación</strong>. Si también quieres cambiar el artículo, utiliza el selector o <strong>Quitar producto</strong>.</td></tr>
      </tbody>
    </table>
    <p><strong>Qué significa «fuentes vigentes»:</strong> la búsqueda utiliza documentos activos, procesados y no caducados de la Base de conocimiento. Se recuperan hasta cinco fragmentos por similitud y se vuelve a comprobar su disponibilidad después de la búsqueda. Un documento pendiente de procesar o con incidencias puede no aportar evidencia. La vigencia depende de los datos configurados; no garantiza por sí sola que el contenido sea completo o correcto.</p>
    <p><strong>Documentos y existencias tienen funciones diferentes.</strong> Los fragmentos explican el contenido documental. La disponibilidad actual se obtiene del inventario del producto seleccionado y se calcula como existencias físicas menos reservas, por bodega. Un inventario citado en un documento puede ser histórico o ficticio; comprueba siempre la sección «Stock confirmado». La selección de producto añade contexto de catálogo y stock, pero no limita la búsqueda documental a ese artículo.</p>
    <p><strong>Contexto de la conversación:</strong> se envían hasta los doce mensajes previos más recientes, excluyendo los mensajes de error y limitando cada mensaje a 4000 caracteres. El historial ayuda a interpretar el diálogo, pero no se utiliza como evidencia de hechos. Las preguntas breves de seguimiento pueden combinarse con tu pregunta anterior para buscar documentos. Los mensajes se mantienen en esta sesión de la tarjeta y no se guardan en el navegador para recuperarlos tras recargar la página.</p>
    <p><strong>Proveedor y falta de datos:</strong> la respuesta puede indicar OpenAI u Ollama y «Respaldo automático» cuando se utiliza un proveedor alternativo. Si no hay IA disponible, se ofrece una respuesta básica con la información operativa confirmada y se añade una incidencia. Si faltan fuentes o datos, no debe interpretarse la ausencia de respuesta como confirmación de una política o de disponibilidad. Ante un error de la consulta, el texto de la pregunta se restaura para que puedas reintentarlo.</p>
    <p><strong>Alcance:</strong> esta tarjeta consulta la Base de conocimiento y, si seleccionas un producto, datos internos de catálogo e inventario. No realiza una búsqueda web, no consulta automáticamente el expediente de un cliente, no crea pedidos ni modifica existencias.</p>
  </InfoPopup>;
}
