import InfoPopup from "./InfoPopup";

export default function ReviewBatchInfo() {
  return <InfoPopup title="Cómo funciona procesar un lote de valoraciones" label="Información sobre procesar lote de valoraciones">
    <p>Esta tarjeta permite <strong>registrar varias valoraciones de un mismo producto y clasificarlas como positivas, negativas o neutras</strong>. El lote se guarda en la base de datos con origen «manual».</p>
    <ol>
      <li><strong>Selecciona el producto</strong> al que pertenecen las valoraciones, buscándolo por código o nombre. Este selector es independiente del de «Recomendación con evidencia»; no necesitas seleccionar un cliente.</li>
      <li><strong>Escribe o pega una valoración por línea.</strong> Cada línea con texto se procesa como una valoración distinta. Las líneas vacías se ignoran y se eliminan los espacios del principio y del final.</li>
      <li><strong>Pulsa «Clasificar valoraciones».</strong> El botón se habilita cuando hay un producto seleccionado y al menos una línea con texto. Mientras se procesa, muestra «Procesando…» y se bloquean los controles del formulario.</li>
      <li><strong>Comprueba la confirmación</strong> en el mensaje de estado de la parte superior de la página: «Lote procesado: N valoraciones». Tras completarse, se vacía el campo de texto y se mantiene el producto seleccionado. Si falla, el error aparece arriba y el texto se conserva.</li>
    </ol>
    <table className="routing-info-table">
      <thead><tr><th scope="col">Qué quieres hacer</th><th scope="col">Qué debes seleccionar o introducir</th></tr></thead>
      <tbody>
        <tr><td>Clasificar varias opiniones sobre un artículo</td><td>Selecciona el <strong>producto</strong>, pega <strong>una valoración por línea</strong> y pulsa <strong>Clasificar valoraciones</strong>.</td></tr>
        <tr><td>Procesar opiniones de productos diferentes</td><td>Envía un <strong>lote separado por producto</strong>, cambiando el selector antes de cada envío.</td></tr>
        <tr><td>Comprobar cuántas valoraciones se procesaron</td><td>Revisa el <strong>mensaje de confirmación</strong> de la parte superior. Cuenta las líneas con texto, no las líneas vacías.</td></tr>
        <tr><td>Consultar el desglose por sentimiento</td><td>El backend lo guarda y devuelve, pero <strong>esta tarjeta todavía no muestra el resumen ni la clasificación individual</strong>.</td></tr>
      </tbody>
    </table>
    <p><strong>Cómo se clasifica actualmente:</strong> se buscan coincidencias de texto sin distinguir mayúsculas y minúsculas. Las expresiones positivas son «bueno», «excelente», «genial», «recomiendo», «perfecto», «great» y «good». Las negativas son «malo», «defecto», «roto», «tarde», «poor», «bad» y «broken». Si no hay coincidencias, la valoración se considera neutra. Si aparecen expresiones de ambos grupos, tiene prioridad la clasificación positiva.</p>
    <p><strong>Ejemplo de lote:</strong></p>
    <pre>El producto es excelente.{"\n"}El artículo llegó roto.{"\n"}El paquete es azul.</pre>
    <p>Con las reglas actuales, estas tres líneas se clasifican como positiva, negativa y neutra, respectivamente.</p>
    <p><strong>Alcance de la clasificación:</strong> se utilizan reglas de coincidencia de texto, sin un modelo de IA para interpretar el significado. No se comprenden de forma fiable negaciones, ironía ni contexto: «no lo recomiendo» contiene «recomiendo» y se clasifica como positiva. Revisa los resultados antes de usarlos para tomar decisiones.</p>
    <p><strong>Qué se guarda:</strong> el producto y el origen del lote, los textos, su clasificación y un resumen con los recuentos de positivas, negativas y neutras. El formulario envía solo texto: no asigna estrellas, fechas de valoración ni identificadores externos. El indicador interno llamado «confidence_score» es una fórmula del resumen; no representa una probabilidad de acierto del clasificador.</p>
    <p><strong>Límites y repetición:</strong> el backend admite de 1 a 500 valoraciones por lote, con un máximo de 5000 caracteres por valoración. Volver a enviar los mismos textos crea otro lote; actualmente no se eliminan duplicados automáticamente.</p>
    <p><strong>Procesar un lote registra valoraciones.</strong> No publica opiniones en plataformas externas, no genera pedidos ni modifica existencias.</p>
  </InfoPopup>;
}
