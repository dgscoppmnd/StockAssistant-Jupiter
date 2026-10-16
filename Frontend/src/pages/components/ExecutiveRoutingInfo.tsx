import InfoPopup from "./InfoPopup";

export default function ExecutiveRoutingInfo() {
  return <InfoPopup title="Cómo funciona el enrutamiento trazable" label="Información sobre el enrutamiento trazable">
      <p>El <strong>Enrutamiento trazable es el coordinador del Agente Ejecutivo</strong>: escribes una pregunta y la app decide qué agente especializado debe atenderla.</p>
      <ol>
        <li><strong>Busca palabras clave en la pregunta.</strong> Por ejemplo, «stock» lleva a inventario; «margen», a finanzas; «demanda», a previsión de ventas; y «cliente», a clientes. Si coinciden varias categorías, se aplica un orden de prioridad.</li>
        <li><strong>Ejecuta la herramienta correspondiente</strong>, usando el cliente o producto seleccionado cuando esa herramienta los necesita.</li>
        <li><strong>Muestra el agente elegido, la herramienta y el resultado.</strong> Además, guarda la consulta y la respuesta en la base de datos para poder revisar la decisión. Por eso se llama trazable.</li>
      </ol>
      <p><strong>No tienes que seleccionar siempre un cliente y un producto.</strong> Sirven para identificar exactamente sobre quién o qué estás preguntando:</p>
      <table className="routing-info-table">
        <thead><tr><th scope="col">Qué quieres consultar</th><th scope="col">Qué debes seleccionar</th></tr></thead>
        <tbody>
          <tr><td>«¿Qué datos tenemos de este cliente?»</td><td><strong>Cliente.</strong> Actualmente consulta sus datos básicos; no recupera tickets, facturas ni pagos.</td></tr>
          <tr><td>«¿Cuál es la previsión de demanda?»</td><td><strong>Producto obligatorio</strong> para realizar la previsión.</td></tr>
          <tr><td>«Analiza la competencia de este producto»</td><td><strong>Producto obligatorio.</strong></td></tr>
          <tr><td>«¿Conviene reponer este producto?»</td><td><strong>Producto</strong> para obtener una recomendación específica. Sin producto, devuelve alertas generales de stock.</td></tr>
          <tr><td>«¿Qué productos tienen riesgo?» o «¿Cómo está el stock?»</td><td>Puedes dejar <strong>ambos vacíos</strong>: esas rutas consultan información general.</td></tr>
        </tbody>
      </table>
      <p>Seleccionarlos envía sus identificadores reales, evitando depender de que el sistema interprete un nombre escrito en la pregunta. <strong>La selección no determina el agente: lo determina el texto de tu consulta.</strong> Tampoco se combinan actualmente cliente y producto para hacer un análisis de compras de ese cliente.</p>
      <p><strong>Elegir un producto no filtra todas las respuestas.</strong> Las rutas de stock y riesgos siguen siendo generales aunque hayas seleccionado uno.</p>
      <p>Esta consulta no crea pedidos ni modifica inventario.</p>
  </InfoPopup>;
}
