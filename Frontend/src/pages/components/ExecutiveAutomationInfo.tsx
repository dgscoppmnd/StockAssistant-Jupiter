import InfoPopup from "./InfoPopup";

export default function ExecutiveAutomationInfo() {
  return <InfoPopup title="Cómo funciona activar, ejecutar y auditar" label="Información sobre las automatizaciones del backend">
    <p>Esta tarjeta permite <strong>controlar las reglas de automatización del backend</strong>. Cada fila muestra el nombre de la regla, lo que hace, su estado y los botones para gestionarla.</p>
    <ol>
      <li><strong>Activar:</strong> habilita la regla para que el programador del backend la ejecute cuando corresponda según su intervalo. Las reglas predeterminadas se crean pausadas y con un intervalo de 24 horas. La ejecución automática requiere que el programador esté habilitado y el backend en funcionamiento.</li>
      <li><strong>Pausar:</strong> deshabilita las siguientes ejecuciones automáticas. No elimina el historial ni las propuestas creadas, ni cancela una ejecución que ya haya comenzado.</li>
      <li><strong>Ejecutar:</strong> lanza una ejecución manual inmediata de esa regla, incluso si está pausada. No cambia su estado de activación. Cuando termina correctamente, actualiza la fecha de última ejecución, que se utiliza para calcular cuándo vuelve a corresponder una ejecución automática.</li>
      <li><strong>Auditar:</strong> cada ejecución queda registrada con su origen (manual o automático), fecha de inicio, estado y resultado o error. La tarjeta «Últimas ejecuciones» muestra la regla, el estado y la fecha de inicio; el backend conserva los demás detalles.</li>
    </ol>
    <table className="routing-info-table">
      <thead><tr><th scope="col">Qué quieres hacer</th><th scope="col">Qué debes seleccionar</th></tr></thead>
      <tbody>
        <tr><td>Permitir que una regla se ejecute automáticamente</td><td>Pulsa <strong>Activar</strong> en la fila de esa regla.</td></tr>
        <tr><td>Detener sus siguientes ejecuciones automáticas</td><td>Pulsa <strong>Pausar</strong> en la fila de esa regla.</td></tr>
        <tr><td>Obtener el resultado ahora</td><td>Pulsa <strong>Ejecutar</strong> en la regla que quieras lanzar, esté activa o pausada.</td></tr>
        <tr><td>Comprobar lo que se ha ejecutado</td><td>Revisa la tarjeta <strong>Últimas ejecuciones</strong> y las propuestas generadas en <strong>Propuestas de compra</strong>.</td></tr>
      </tbody>
    </table>
    <p><strong>Qué hace cada regla:</strong></p>
    <ul>
      <li><strong>Propuestas de reposición:</strong> revisa las alertas de stock bajo y crea propuestas de compra pendientes de aprobación humana. Evita crear otra propuesta pendiente para el mismo producto y bodega.</li>
      <li><strong>Informe diario:</strong> calcula el número de movimientos de inventario y la cantidad neta de las últimas 24 horas, y guarda el resultado en el registro de ejecución.</li>
      <li><strong>Alertas de riesgos:</strong> consulta el análisis de riesgos y guarda su resultado en el registro de ejecución.</li>
    </ul>
    <p><strong>No necesitas seleccionar cliente ni producto.</strong> Estas reglas trabajan con los datos generales del backend; los selectores de «Enrutamiento trazable» no afectan a esta tarjeta.</p>
    <p><strong>Ejecutar una regla no crea pedidos definitivos ni modifica inventario.</strong> Las propuestas de reposición siguen pendientes de aprobación humana; activar o ejecutar la regla no las aprueba.</p>
  </InfoPopup>;
}
