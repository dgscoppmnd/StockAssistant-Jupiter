import InfoPopup from "./InfoPopup";

export default function MarketTrendsInfo() {
  return <InfoPopup title="Cómo funcionan las tendencias autorizadas" label="Información sobre las tendencias autorizadas">
    <p>Esta tarjeta permite <strong>consultar señales de interés de búsqueda en Google Trends mediante SerpAPI</strong>. Es una consulta externa de solo lectura para apoyar el análisis de mercado de un término, producto o categoría.</p>
    <ol>
      <li><strong>Introduce un término de búsqueda</strong>, por ejemplo «auriculares inalámbricos» o «cargador portátil». El backend admite términos de entre 2 y 100 caracteres.</li>
      <li><strong>Pulsa «Consultar tendencias».</strong> La app envía el término al backend, comprueba la disponibilidad de SerpAPI y consulta Google Trends si la fuente está habilitada.</li>
      <li><strong>Comprueba el resultado en esta tarjeta.</strong> Se muestra «Datos de tendencia recibidos» cuando se recibe el bloque de datos, o «La fuente no está disponible» cuando la consulta no puede proporcionar datos. Debajo aparece el nombre de la fuente.</li>
      <li><strong>Si se produce un error de la solicitud</strong>, revisa el mensaje de error de la parte superior de la página. Puedes corregir el término o volver a consultar cuando el servicio esté disponible.</li>
    </ol>
    <table className="routing-info-table">
      <thead><tr><th scope="col">Qué quieres consultar</th><th scope="col">Qué debes seleccionar o introducir</th></tr></thead>
      <tbody>
        <tr><td>El interés de búsqueda de un producto o categoría</td><td>Escribe su <strong>nombre o término representativo</strong> y pulsa <strong>Consultar tendencias</strong>.</td></tr>
        <tr><td>Consultar otro término</td><td>Sustituye el texto del campo y vuelve a pulsar el botón. El resultado recibido sustituye al anterior.</td></tr>
        <tr><td>Comprobar si la consulta obtuvo datos</td><td>Revisa el <strong>mensaje del resultado</strong> y el nombre de la <strong>fuente</strong>.</td></tr>
        <tr><td>Comprobar la disponibilidad del proveedor</td><td>Revisa también <strong>Disponibilidad y modo</strong>, donde aparece el estado de SerpAPI y su detalle al cargar la página.</td></tr>
      </tbody>
    </table>
    <p><strong>No necesitas seleccionar cliente ni producto.</strong> La consulta utiliza el texto de este campo, de forma independiente de los selectores de otras tarjetas. Actualmente el país de consulta es <strong>España</strong>; esta tarjeta no permite elegir país ni intervalo de fechas y utiliza el período predeterminado del proveedor.</p>
    <p><strong>Qué datos prepara el backend:</strong> la evolución del interés a lo largo del tiempo y las consultas relacionadas, cuando la respuesta del proveedor las incluya, junto con la fecha de consulta y una referencia a la fuente. También guarda la respuesta externa para su trazabilidad.</p>
    <p><strong>Qué muestra actualmente la tarjeta:</strong> solo una confirmación de recepción y el nombre de la fuente. Todavía no presenta gráficos, valores de interés, consultas relacionadas ni un análisis redactado por IA. «Datos de tendencia recibidos» no garantiza que las series contengan observaciones ni demuestra que el interés esté creciendo.</p>
    <p><strong>Qué significa «autorizadas»:</strong> la app utiliza el conector configurado de SerpAPI con sus credenciales y controles de acceso al proveedor. Si falta la configuración, se agota la cuota o hay un fallo remoto, la fuente puede aparecer no disponible o entrar en pausa temporal. No implica que cada término requiera una aprobación manual.</p>
    <p><strong>Cómo usar la información:</strong> una señal de interés de búsqueda no confirma ventas, demanda de tu empresa ni rentabilidad. Contrástala con inventario, despachos, costes y márgenes antes de decidir una compra.</p>
    <p><strong>Consultar tendencias no ejecuta operaciones comerciales.</strong> No crea pedidos, genera propuestas de compra ni modifica inventario; la decisión sigue en manos humanas.</p>
  </InfoPopup>;
}
