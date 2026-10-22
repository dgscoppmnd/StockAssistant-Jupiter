import type { ReactNode } from "react";
import InfoPopup from "./InfoPopup";

function Guide({ rows }: { rows: [string, string][] }) {
  return <table className="routing-info-table">
    <thead><tr><th scope="col">Qué quieres consultar</th><th scope="col">Qué debes seleccionar o revisar</th></tr></thead>
    <tbody>{rows.map(([question, action]) => <tr key={question}><td>{question}</td><td>{action}</td></tr>)}</tbody>
  </table>;
}

const topics = {
  overview: {
    title: "Cómo funciona Agentes y análisis",
    body: <>
      <p>Esta página reúne <strong>señales de inventario, disponibilidad de fuentes, análisis comerciales, valoraciones y consultas documentales o de mercado</strong>. Cada tarjeta tiene su propia ayuda y sus propios datos.</p>
      <p>El resumen superior cuenta las alertas de stock cargadas, las fuentes disponibles respecto al total y las alertas de devolución recibidas. Son recuentos de registros, no cantidades de mercancía ni importes.</p>
      <Guide rows={[
        ["Revisar las señales generales", "Consulta Alertas de reposición, Disponibilidad y modo y los riesgos de devolución en Datos con vigencia."],
        ["Analizar un producto", "Selecciona el producto en Recomendación con evidencia y utiliza Analizar compra o Análisis comercial."],
        ["Actualizar stock, fuentes y riesgos", "Pulsa Actualizar datos. Si falla la carga, utiliza Reintentar carga y revisa el mensaje de error."],
        ["Abrir la configuración de reglas", "Pulsa Editor de reglas. El enlace abre otra página; no ejecuta ni modifica una regla por sí solo."],
      ]} />
      <p><strong>Actualizar datos</strong> vuelve a consultar únicamente stock, estado de fuentes y riesgos. No recalcula la recomendación de compra, la previsión, el margen, la competencia ni las consultas de soporte y mercado. Cada análisis se ejecuta desde su tarjeta.</p>
      <p>Los datos generales se cargan al abrir la página y al solicitar su actualización; no se refrescan periódicamente. Si falla una actualización, pueden permanecer los últimos datos recibidos. Comprueba los mensajes de estado antes de interpretar las cifras.</p>
    </>,
  },
  stock: {
    title: "Cómo interpretar las alertas de reposición",
    body: <>
      <p>Esta tarjeta muestra <strong>productos y bodegas cuyo stock disponible es menor o igual al punto de pedido configurado</strong>. El disponible se calcula como existencias físicas menos reservas.</p>
      <p>Cada fila corresponde a un producto en una bodega. La cifra de la izquierda es el disponible y la de la derecha el umbral, expresados en la unidad base mostrada. El contador refleja filas de alerta: un producto puede aparecer en varias bodegas.</p>
      <Guide rows={[
        ["Por qué aparece una alerta", "Compara el disponible con el umbral. La igualdad también genera alerta."],
        ["Cuántas unidades conviene comprar", "Selecciona el producto en Recomendación con evidencia y pulsa Analizar compra. Esta tarjeta no calcula por sí sola la compra."],
        ["Cambiar el umbral o consultar el saldo", "Revisa la configuración de inventario y el snapshot por producto y bodega en la página de inventario."],
        ["Consultar cambios recientes", "Pulsa Actualizar datos en la cabecera de esta página."],
      ]} />
      <p>Las alertas son generales; no se filtran al seleccionar un producto en compras o valoraciones. Se basan en registros de existencias con configuración de inventario, no en una predicción de demanda. «Sin alertas de reposición» indica que los datos cargados no cumplen este criterio; no garantiza que todos los productos tengan existencias configuradas.</p>
      <p>Consultar las alertas no crea pedidos, reservas ni propuestas de compra y no modifica existencias.</p>
    </>,
  },
  sources: {
    title: "Cómo interpretar la disponibilidad y el modo de las fuentes",
    body: <>
      <p>Esta tarjeta muestra el <strong>estado que declara cada conector externo</strong>: su nombre, disponibilidad, detalle y modo de uso. El resumen superior cuenta cuántos están disponibles respecto al total cargado.</p>
      <Guide rows={[
        ["Qué fuente puede utilizarse", "Revisa Disponible y el detalle del proveedor. La configuración habilitada no garantiza que la siguiente consulta remota vaya a completarse."],
        ["Por qué no se puede consultar una fuente", "Lee el detalle: puede faltar configuración, existir una pausa temporal o requerirse activación de la integración."],
        ["Qué permite el modo Solo lectura", "Consultar datos externos mediante las herramientas de la app; no publicar ni modificar información en el servicio externo."],
        ["Comprobar de nuevo el estado", "Pulsa Actualizar datos. Esta tarjeta no contiene controles para introducir credenciales o activar conectores."],
      ]} />
      <p>SerpAPI se utiliza para consultas de Shopping y Trends. Su estado depende de la configuración y de posibles pausas temporales por cuota o errores remotos. Otras fuentes pueden seguir sin estar disponibles aunque detecten credenciales si su integración requiere activación y validación.</p>
      <p>El estado corresponde a la última carga de la página y no es una prueba completa de conectividad de cada proveedor. No necesitas seleccionar cliente ni producto para consultar esta tarjeta. Las consultas internas de stock o finanzas no dependen de que todas las fuentes externas estén disponibles.</p>
    </>,
  },
  forecast: {
    title: "Cómo interpretar la previsión y el margen",
    body: <>
      <p>Esta tarjeta muestra los <strong>resultados comerciales del producto seleccionado en Recomendación con evidencia</strong>. Para cargarla, selecciona allí un producto y pulsa «Análisis comercial»; «Analizar compra» no carga esta previsión ni estos importes.</p>
      <Guide rows={[
        ["Obtener los resultados de un artículo", "Selecciona el producto en compras y pulsa Análisis comercial."],
        ["Interpretar la previsión", "Revisa el horizonte indicado y la media diaria. El cálculo proyecta despachos históricos; no es una cantidad que se deba comprar automáticamente."],
        ["Interpretar el margen", "Compara ingresos y coste: margen = ingresos menos coste; el porcentaje se calcula respecto a los ingresos."],
        ["Cambiar de producto", "Selecciona otro producto y vuelve a ejecutar Análisis comercial. El cambio de selección limpia los resultados anteriores."],
      ]} />
      <p><strong>Método de previsión:</strong> suma las unidades despachadas registradas en los últimos 90 días, divide entre 90 para obtener la media diaria y la multiplica por el horizonte de previsión, que en esta consulta es de 30 días. Es una media histórica, no un modelo de aprendizaje automático entrenado.</p>
      <p><strong>Tendencia:</strong> compara los despachos de los últimos 30 días con los 30 anteriores. Las etiquetas «up», «down» y «stable» indican aumento, descenso o igualdad en esa comparación; «insufficient_evidence» indica pocos días registrados. Ninguna garantiza demanda futura ni cobertura completa del historial.</p>
      <p><strong>Finanzas:</strong> los ingresos usan cantidades despachadas, precio y tipo de cambio de las líneas de venta. El coste estimado utiliza el coste unitario medio ponderado de las recepciones registradas y las unidades despachadas. Estas cifras históricas no están limitadas a los 90 días de la previsión ni equivalen a beneficio neto o saldo cobrado.</p>
      <p>Los importes no incorporan automáticamente todos los gastos del negocio. Si faltan datos de ventas o costes pueden aparecer ceros; revisa su cobertura antes de interpretar un margen alto. La consulta no crea pedidos ni modifica inventario, y «Actualizar datos» no vuelve a ejecutar este análisis.</p>
    </>,
  },
  risks: {
    title: "Cómo interpretar los datos con vigencia",
    body: <>
      <p>Esta tarjeta combina <strong>dos consultas con distinto alcance</strong>: ofertas de competencia del producto analizado y alertas generales de devolución. Seleccionar un producto para el análisis comercial no filtra las alertas de devolución.</p>
      <Guide rows={[
        ["Consultar ofertas del producto analizado", "Selecciona el producto en Recomendación con evidencia y pulsa Análisis comercial. Aquí se muestra el número de ofertas devueltas."],
        ["Obtener nuevas ofertas externas", "Analizar compra consulta Shopping cuando SerpAPI está disponible. Después puedes ejecutar Análisis comercial para consultar las ofertas guardadas."],
        ["Revisar productos con devoluciones elevadas", "Consulta los nombres y porcentajes de las filas de riesgos. Se cargan al abrir la página y al pulsar Actualizar datos."],
      ]} />
      <p><strong>Competencia:</strong> se utiliza la última respuesta de Google Shopping guardada para ese producto; «Análisis comercial» no hace una nueva búsqueda externa. El resultado puede contener ofertas caducadas. El backend devuelve fechas y datos de fuente, pero esta tarjeta muestra solo el recuento, no las fechas ni una validación visual de vigencia. Cero ofertas no demuestra que no haya competidores.</p>
      <p><strong>Riesgo de devolución:</strong> se divide la cantidad devuelta entre la cantidad despachada registrada del producto y se muestran los casos con una tasa de al menos el 10 %. No es un porcentaje de opiniones negativas ni una predicción. La consulta usa el historial de movimientos sin un filtro de fechas en esta página.</p>
      <p>El backend revisa hasta 30 productos con devoluciones, priorizados por cantidad devuelta, y aplica el umbral a esos candidatos. Si no hay despachos registrados, calcula una tasa cero. Por ello, «No hay riesgos de devolución sobre el umbral» describe los resultados cargados, no garantiza la ausencia total de incidencias.</p>
      <p>Consultar esta tarjeta no genera pedidos, alertas enviadas a terceros ni cambios de existencias.</p>
    </>,
  },
} satisfies Record<string, { title: string; body: ReactNode }>;

export default function AgentsCardInfo({ topic }: { topic: keyof typeof topics }) {
  const { title, body } = topics[topic];
  return <InfoPopup title={title} label={`Información: ${title}`}>{body}</InfoPopup>;
}
