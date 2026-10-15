import InfoPopup from "./InfoPopup";

export default function PurchaseRecommendationInfo() {
  return <InfoPopup title="Cómo funciona la recomendación con evidencia" label="Información sobre la recomendación con evidencia">
    <p>Esta tarjeta permite <strong>analizar la compra de un producto del catálogo</strong> usando su inventario configurado y, cuando estén disponibles, ofertas externas. También permite consultar su previsión, margen y competencia mediante un análisis comercial independiente.</p>
    <ol>
      <li><strong>Selecciona un producto</strong> en el buscador por código o nombre. Los botones permanecen deshabilitados hasta que lo selecciones y durante el análisis. No necesitas seleccionar un cliente.</li>
      <li><strong>Pulsa «Analizar compra»</strong> para calcular una cantidad sugerida, estimar su coste si hay ofertas y obtener una explicación basada en la evidencia recuperada.</li>
      <li><strong>Revisa el resultado en esta tarjeta:</strong> producto, pedido sugerido en su unidad base, coste estimado, explicación y número de ofertas comparables.</li>
      <li><strong>Pulsa «Análisis comercial»</strong> si quieres ampliar la revisión del mismo producto. Sus resultados se muestran en las tarjetas «Previsión y margen» y «Datos con vigencia»; este botón no recalcula la recomendación de compra.</li>
    </ol>
    <table className="routing-info-table">
      <thead><tr><th scope="col">Qué quieres consultar</th><th scope="col">Qué debes seleccionar</th></tr></thead>
      <tbody>
        <tr><td>Una cantidad de compra sugerida y su justificación</td><td>Selecciona el <strong>producto</strong> y pulsa <strong>Analizar compra</strong>.</td></tr>
        <tr><td>El coste estimado y las ofertas encontradas</td><td>Ejecuta <strong>Analizar compra</strong> y revisa el coste y el número de ofertas de esta tarjeta.</td></tr>
        <tr><td>La previsión de ventas, el margen y la competencia</td><td>Selecciona el <strong>producto</strong>, pulsa <strong>Análisis comercial</strong> y revisa las tarjetas de resultados correspondientes.</td></tr>
        <tr><td>Analizar otro artículo</td><td>Selecciona otro <strong>producto</strong>. Se limpian los resultados anteriores para que puedas ejecutar un nuevo análisis.</td></tr>
      </tbody>
    </table>
    <p><strong>Cómo se calcula la cantidad:</strong> se suma el stock disponible del producto entre sus bodegas (existencias físicas menos reservas). Se utiliza la cantidad de reposición configurada; si es cero, se calcula la diferencia entre el punto de pedido y el disponible, con un mínimo de una unidad. El producto debe tener existencias y configuración de inventario para poder analizarlo.</p>
    <p><strong>La cantidad sugerida no comprueba por sí sola si hace falta comprar.</strong> El cálculo puede devolver una cantidad incluso cuando el disponible supera el punto de pedido. Revisa las alertas y las necesidades reales antes de decidir; esta recomendación no incorpora automáticamente la previsión ni el margen del análisis comercial.</p>
    <p><strong>De dónde sale el coste:</strong> si SerpAPI está disponible, se consultan ofertas de Google Shopping por el nombre del producto, para España y en español. El coste estimado utiliza el menor precio recuperado, multiplicado por la cantidad sugerida y por el factor de coste de importación configurado. Sin ofertas con precio, aparece «Sin oferta».</p>
    <p><strong>Qué significa «con evidencia»:</strong> el cálculo usa datos internos de inventario y las ofertas externas recuperadas; la IA redacta una explicación con esos datos. Si el proveedor de IA falla, se mantiene el cálculo y se muestra una explicación básica. El número de ofertas no garantiza que todas correspondan exactamente a la misma variante, moneda o condiciones de entrega; compruébalas antes de comprar. La tarjeta muestra un resumen, no el listado completo de ofertas y fuentes.</p>
    <p><strong>Alcance del análisis comercial:</strong> la previsión proyecta una media de despachos registrados en los últimos 90 días; no utiliza un modelo de aprendizaje automático entrenado. El margen se calcula con ventas despachadas y costes históricos de recepción. La competencia utiliza las ofertas guardadas de consultas anteriores y puede incluir datos caducados; no realiza una nueva búsqueda externa al pulsar ese botón.</p>
    <p><strong>Analizar no ejecuta una compra.</strong> Ninguno de estos botones crea pedidos definitivos, genera propuestas pendientes de aprobación ni modifica el inventario. La decisión de compra sigue en manos humanas.</p>
  </InfoPopup>;
}
