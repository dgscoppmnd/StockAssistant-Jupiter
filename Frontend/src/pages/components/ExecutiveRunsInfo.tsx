import InfoPopup from "./InfoPopup";

export default function ExecutiveRunsInfo() {
  return <InfoPopup title="Cómo interpretar las últimas ejecuciones" label="Información sobre las últimas ejecuciones">
    <p>Esta tarjeta muestra el <strong>historial reciente de las automatizaciones del backend</strong>. Cada fila corresponde a una ejecución concreta, tanto manual como automática. Una misma regla puede aparecer varias veces si se ha ejecutado en distintas ocasiones.</p>
    <ol>
      <li><strong>Regla:</strong> aparece el código de la automatización ejecutada: «stock_reorder_proposals» corresponde a Propuestas de reposición; «daily_inventory_report», a Informe diario; y «risk_alerts», a Alertas de riesgos.</li>
      <li><strong>Estado:</strong> indica si esa ejecución está en curso, terminó correctamente o falló. Es el estado de esa ejecución, no el estado «Activa» o «Pausada» de la regla.</li>
      <li><strong>Fecha y hora:</strong> muestran cuándo comenzó la ejecución, en el formato y la zona horaria de tu navegador. No indican cuándo terminó ni cuándo se ejecutará de nuevo.</li>
    </ol>
    <table className="routing-info-table">
      <thead><tr><th scope="col">Estado que aparece</th><th scope="col">Qué significa</th></tr></thead>
      <tbody>
        <tr><td><strong>running</strong></td><td>La ejecución se ha registrado como iniciada y todavía no consta un resultado final. Este estado, por sí solo, no garantiza que siga avanzando.</td></tr>
        <tr><td><strong>completed</strong></td><td>La regla terminó correctamente y su resultado quedó guardado. Puede haber terminado sin encontrar alertas ni crear propuestas nuevas.</td></tr>
        <tr><td><strong>failed</strong></td><td>La ejecución falló y el backend registró el error. El mensaje del error no se muestra actualmente en esta tarjeta.</td></tr>
      </tbody>
    </table>
    <table className="routing-info-table">
      <thead><tr><th scope="col">Qué quieres comprobar</th><th scope="col">Qué debes revisar</th></tr></thead>
      <tbody>
        <tr><td>Si una regla se ha ejecutado recientemente</td><td>Busca su <strong>código</strong> en el historial y comprueba la <strong>fecha de inicio</strong>.</td></tr>
        <tr><td>Si terminó correctamente</td><td>Revisa que el estado de esa ejecución sea <strong>completed</strong>.</td></tr>
        <tr><td>Si se generaron propuestas de reposición</td><td>Revisa también <strong>Propuestas de compra</strong>. Una ejecución completada no implica que se hayan creado propuestas nuevas.</td></tr>
        <tr><td>Volver a ejecutar una regla o cambiar su activación</td><td>Utiliza los botones de <strong>Activar, ejecutar y auditar</strong>. Esta tarjeta solo muestra el historial.</td></tr>
      </tbody>
    </table>
    <p><strong>El historial muestra hasta las 50 ejecuciones más recientes</strong>, ordenadas por su identificador de registro, de la más reciente a la más antigua. Se carga al abrir la página y se actualiza tras activar, pausar o ejecutar una regla desde ella. Actualmente no se refresca automáticamente mientras mantienes la página abierta; vuelve a cargarla para consultar cambios posteriores del programador.</p>
    <p>El backend conserva también el origen de la ejecución (manual o automático), el resultado, el posible error y la fecha de finalización. <strong>Estos detalles no se muestran actualmente en las filas de esta tarjeta.</strong></p>
    <p><strong>No necesitas seleccionar cliente ni producto.</strong> Los selectores de «Enrutamiento trazable» no filtran este historial. Si aparece «Aún no hay ejecuciones auditadas», la lista cargada está vacía; activar una regla no crea por sí solo un registro de ejecución.</p>
    <p><strong>Una ejecución completada no significa que una compra esté aprobada.</strong> Las propuestas de reposición siguen pendientes de aprobación humana; consultar este historial no crea pedidos ni modifica inventario.</p>
  </InfoPopup>;
}
