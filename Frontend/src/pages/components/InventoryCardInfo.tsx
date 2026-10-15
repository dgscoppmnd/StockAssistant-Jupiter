import type { ReactNode } from "react";
import InfoPopup from "./InfoPopup";

function Actions({ rows }: { rows: [string, string][] }) {
  return <table className="routing-info-table">
    <thead><tr><th scope="col">Qué quieres hacer</th><th scope="col">Qué debes revisar o seleccionar</th></tr></thead>
    <tbody>{rows.map(([action, detail]) => <tr key={action}><td>{action}</td><td>{detail}</td></tr>)}</tbody>
  </table>;
}

function TableHelp() {
  return <p><strong>Cómo recorrer la tabla:</strong> utiliza la paginación y el selector de 5, 10 o 25 filas por página. Las columnas habilitadas permiten ordenar pulsando su cabecera. Si no caben todas las columnas, desplázate horizontalmente. La paginación y el total corresponden a los registros cargados, no necesariamente a todo el historial del sistema.</p>;
}

const topics: Record<string, { title: string; body: ReactNode }> = {
  overview: {
    title: "Cómo funciona la visibilidad de stock por bodega",
    body: <>
      <p>Esta tarjeta resume el <strong>estado del inventario registrado</strong>: productos del catálogo, bodegas, existencias físicas, disponible y registros bajo mínimo. Los indicadores se calculan en el backend; no son previsiones de IA.</p>
      <Actions rows={[
        ["Comprobar las existencias de un artículo", "Consulta «Snapshot por producto y bodega» para distinguir su stock físico, reservado y disponible en cada ubicación."],
        ["Entender un indicador", "Abre el icono de información de su tarjeta para ver cómo se calcula y qué cuenta."],
        ["Registrar una entrada o configurar el inventario", "Utiliza las tarjetas de pedidos, bodegas o configuraciones según la operación que necesites."],
      ]} />
      <p><strong>Actualización:</strong> los datos se cargan al abrir la página y se vuelven a consultar después de operaciones correctas realizadas desde ella. No hay refresco periódico automático; recarga la página para ver cambios posteriores realizados desde otros lugares.</p>
      <p>Los mensajes de estado y error aparecen aquí. Mientras se carga o si falla la consulta, los indicadores pueden mostrar ceros iniciales o los últimos valores cargados; comprueba el estado antes de interpretarlos.</p>
      <p>Consultar esta tarjeta no modifica inventario. Los formularios de confirmación y las acciones rápidas de esta página sí pueden registrar operaciones reales.</p>
    </>,
  },
  products: {
    title: "Qué cuenta el indicador Productos",
    body: <><p>Cuenta <strong>todos los productos del catálogo</strong>, tengan o no configuración de inventario o existencias. No cuenta unidades físicas ni filas de la tabla de stock.</p><p>Para consultar existencias, utiliza «Snapshot por producto y bodega». Un producto puede aparecer en varias bodegas y seguir contando una sola vez en este indicador.</p></>,
  },
  warehousesCount: {
    title: "Qué cuenta el indicador Bodegas",
    body: <><p>Cuenta <strong>todas las bodegas registradas</strong>, tanto activas como inactivas, incluso si no tienen stock.</p><p>Revisa «Listado de bodegas» para consultar su código, nombre, estado y fecha de actualización. Crear una bodega no carga existencias automáticamente.</p></>,
  },
  physical: {
    title: "Cómo se calcula el stock físico total",
    body: <><p>Suma las <strong>existencias físicas registradas</strong> de todos los productos y bodegas. Incluye las cantidades que estén reservadas; las reservas no se restan del físico.</p><p>Es una suma de cantidades de distintas referencias y unidades base, no un valor monetario ni una conversión a una unidad común. Consulta el detalle por producto y unidad en el snapshot. El indicador se muestra redondeado sin decimales, aunque las existencias pueden ser fraccionarias.</p></>,
  },
  available: {
    title: "Cómo se calcula el disponible total",
    body: <><p>Suma el <strong>stock físico menos el reservado</strong> de todos los registros de producto y bodega. Representa la cantidad registrada que no está comprometida por reservas.</p><p>El total mezcla referencias y unidades base sin convertirlas a una unidad común y se muestra sin decimales. Para tomar una decisión operativa, revisa el producto, la bodega y la unidad en el snapshot; un total positivo no garantiza disponibilidad de un artículo concreto.</p></>,
  },
  low: {
    title: "Qué cuenta el indicador Bajo mínimo",
    body: <><p>Cuenta los <strong>registros de producto y bodega cuyo disponible es menor o igual al punto de pedido</strong> configurado para el producto. La igualdad también cuenta como bajo mínimo.</p><p>Un mismo producto puede contar varias veces si cumple esa condición en distintas bodegas. Se consideran los registros de stock existentes con configuración, no todos los productos del catálogo. Revisa el snapshot y los puntos de pedido para identificar cada caso. El indicador no genera compras automáticamente.</p></>,
  },
  receipt: {
    title: "Cómo crear un pedido de stock y confirmar su entrada",
    body: <>
      <p>Este formulario <strong>registra una recepción real</strong>: al confirmar, crea la orden de compra como recibida, la recepción confirmada y sus movimientos, e incrementa el stock físico en la bodega elegida. No guarda un borrador ni una recomendación pendiente de aprobación.</p>
      <ol>
        <li>Selecciona un proveedor existente o utiliza la opción de crear uno nuevo. Si es nuevo, introduce su nombre y, opcionalmente, su código; antes de enviarlo se solicita confirmar la creación del proveedor y el pedido.</li>
        <li>Elige la bodega de destino y revisa el producto de cada línea. La página puede preseleccionar la primera bodega y el primer producto visibles.</li>
        <li>Introduce cantidad positiva, unidad válida y precio unitario no negativo. «Agregar línea» añade otro artículo; «Eliminar» quita una línea y se mantiene al menos una.</li>
        <li>Completa, si lo necesitas, el número de pedido y las notas. Pulsa «Confirmar pedido y entrada» solo cuando quieras registrar la mercancía como recibida.</li>
      </ol>
      <Actions rows={[
        ["Recibir varios productos en una bodega", "Selecciona proveedor y bodega, añade las líneas necesarias y confirma la entrada."],
        ["Utilizar un proveedor ya registrado", "Selecciónalo en el buscador. El catálogo se vuelve a comprobar antes del envío."],
        ["Dejar que se genere el número de pedido", "Deja «N. pedido» vacío. El backend asigna un número; la recepción tiene además su propia referencia."],
        ["Resolver un fallo de carga de proveedores", "Pulsa «Reintentar». La confirmación se bloquea mientras se cargan los proveedores, si hay un error de carga, durante una operación o si no hay bodegas."],
      ]} />
      <p><strong>Unidades y moneda:</strong> la cantidad se convierte a la unidad base si existe una conversión configurada; si la unidad no existe o no tiene conversión, la operación puede rechazarse. Este formulario utiliza EUR y tipo de cambio 1; no ofrece controles de moneda o cambio.</p>
      <p>Tras completarse, se recargan los datos y se limpian proveedor, número, notas y líneas. Reenviar el formulario es una nueva operación; introducir el mismo número de pedido no debe usarse como mecanismo para evitar duplicados.</p>
    </>,
  },
  orders: {
    title: "Cómo interpretar el listado de pedidos de stock",
    body: <>
      <p>Esta tabla es un <strong>resumen de recepciones representadas en los movimientos recientes</strong>. Agrupa movimientos de tipo documental «goods_receipt» por recepción o clave de operación. No es un listado completo de órdenes de compra pendientes.</p>
      <p><strong>Documento</strong> muestra una etiqueta «GR-ID» de la recepción o su clave de operación; no necesariamente el número comercial del pedido. <strong>Líneas</strong> cuenta los movimientos cargados de esa recepción; <strong>Cantidad</strong> suma sus cantidades con signo y <strong>Fecha</strong> toma la más reciente del grupo. «Operación» identifica la operación registrada.</p>
      <Actions rows={[
        ["Comprobar una entrada reciente", "Busca su bodega, fecha y referencia de recepción y contrasta los movimientos y el snapshot."],
        ["Registrar otra recepción", "Utiliza «Crear pedido de stock»; esta tabla no tiene acciones de edición o confirmación."],
      ]} />
      <p><strong>Alcance:</strong> se construye a partir de los últimos doce movimientos del dashboard. Una recepción puede quedar fuera o aparecer incompleta si solo parte de sus líneas está entre esos movimientos. La suma de cantidades puede mezclar productos con unidades diferentes; no representa un importe de compra.</p>
      <TableHelp />
    </>,
  },
  warehouses: {
    title: "Cómo consultar y crear bodegas",
    body: <>
      <p>La tabla muestra las <strong>bodegas registradas, activas e inactivas</strong>, con su ID, código, nombre, descripción, estado y fecha de última actualización. Cada fila representa una bodega; no es un historial de cambios.</p>
      <ol><li>Pulsa «Agregar bodega» para abrir el formulario.</li><li>Introduce código y nombre obligatorios y, si quieres, una descripción.</li><li>Pulsa «Guardar bodega» para crearla o «Cancelar» para cerrar sin guardar. Las nuevas bodegas se crean activas y el código se normaliza a mayúsculas.</li></ol>
      <Actions rows={[
        ["Consultar una ubicación", "Revisa su código, nombre y estado en la tabla."],
        ["Dar de alta una ubicación", "Pulsa «Agregar bodega» y completa el formulario. El backend valida los datos."],
      ]} />
      <p>Guardar crea la bodega y actualiza la página; no añade stock. Para cargar existencias, registra una entrada. Esta tarjeta no ofrece edición, eliminación ni cambio de estado de las bodegas existentes.</p>
      <TableHelp />
    </>,
  },
  config: {
    title: "Cómo configurar la unidad y el punto de pedido",
    body: <>
      <p>La tabla consolida por producto los registros del snapshot: <strong>unidad base, punto de pedido, cantidad sugerida, disponible sumado entre bodegas y nombres de las bodegas</strong>. Solo incluye productos presentes en ese snapshot; no es necesariamente todo el catálogo de configuraciones.</p>
      <ol><li>Pulsa «Configurar unidad y punto de pedido».</li><li>Introduce el ID de un producto existente y el código de una unidad ya registrada, por ejemplo «unit».</li><li>Define el punto de pedido y la cantidad sugerida, ambos no negativos, y si se permite stock negativo.</li><li>Pulsa «Guardar configuración». Si ya existe una configuración de ese producto, se actualiza; si no, se crea.</li></ol>
      <Actions rows={[
        ["Definir cuándo revisar la reposición", "Configura el punto de pedido. El indicador Bajo mínimo compara el disponible de cada bodega con ese valor."],
        ["Definir una cantidad de reposición", "Completa «Cantidad sugerida». Es un parámetro utilizado por otras funciones de reposición, no una compra automática."],
        ["Revisar el disponible consolidado", "Consulta la columna Disponible y contrástala con el detalle por bodega del snapshot."],
      ]} />
      <p>La configuración es <strong>por producto, no por bodega</strong>. «Permitir stock negativo» afecta a las validaciones de operaciones de inventario. Guardar no recibe mercancía ni convierte o recalcula las cantidades existentes; revisa la coherencia de la unidad base antes de cambiarla.</p>
      <TableHelp />
    </>,
  },
  movements: {
    title: "Cómo interpretar los últimos registros de inventario",
    body: <>
      <p>Esta tabla muestra los <strong>últimos doce movimientos</strong> devueltos por el dashboard, ordenados inicialmente del registro más reciente al más antiguo. Incluye fecha de registro, tipo, producto, bodega, posible destino, cantidad con signo y referencia documental.</p>
      <p>La cantidad se expresa en la unidad base. Una recepción registra una entrada; una transferencia puede generar una salida y una entrada. Las reservas y sus liberaciones afectan al comprometido: el tipo de movimiento es necesario para interpretar el efecto, no basta con sumar todos los signos como si fueran variaciones de stock físico.</p>
      <Actions rows={[
        ["Comprobar una operación reciente", "Contrasta tipo, producto, bodega, fecha y documento con el resultado esperado."],
        ["Conocer el saldo actual", "Consulta el snapshot. Estos doce movimientos no permiten reconstruir todo el historial."],
        ["Utilizar los botones de prueba", "Abre la ayuda de «Acciones rápidas de prueba»: esos botones registran operaciones reales."],
      ]} />
      <p>La bodega mostrada es la asociada al movimiento; aunque la columna se llame «Bodega origen», también puede ser una ubicación receptora. En «transfer_in», la primera bodega es la receptora y la columna «Bodega destino» contiene la contraparte de origen; interpreta ambas junto con el tipo de movimiento. Un guion indica que no se ha informado una contraparte. Si no se resuelve el nombre del producto o bodega, se muestra su identificador. La tabla no permite editar ni eliminar movimientos.</p>
      <TableHelp />
    </>,
  },
  quick: {
    title: "Qué hacen las acciones rápidas de prueba",
    body: <>
      <p><strong>Estos botones registran operaciones reales en la base de datos y cambian las existencias.</strong> La palabra «demo» identifica datos de prueba; no implica una simulación ni una vista previa.</p>
      <Actions rows={[
        ["Recepción demo", "Registra 5 unidades del primer producto visible en la primera bodega, con proveedor «Proveedor demo», precio unitario 1 y tipo de cambio 1. Crea la compra, la recepción y el movimiento de entrada."],
        ["Transferencia demo", "Transfiere 1 unidad del primer producto desde la primera bodega a la segunda. Reduce el origen, aumenta el destino y registra los movimientos correspondientes."],
      ]} />
      <p>El primer producto se toma del snapshot; las bodegas se toman del listado cargado. No hay selector en estos botones: revisa esos datos antes de usarlos. La recepción requiere al menos una bodega y un producto; la transferencia requiere además dos bodegas diferentes. Ambos se bloquean durante una operación.</p>
      <p>Las líneas usan el código de unidad «unit». El backend aplica las conversiones configuradas y las validaciones de stock; la transferencia puede rechazarse por falta de disponible u otra configuración inválida. El proveedor demo puede crearse si no existe.</p>
      <p>Cada pulsación correcta registra una nueva operación y recarga las tablas. Para elegir proveedor, cantidades, producto y bodega, utiliza el formulario de pedido de stock.</p>
    </>,
  },
  snapshot: {
    title: "Cómo leer el snapshot por producto y bodega",
    body: <>
      <p>Cada fila muestra el <strong>saldo registrado de un producto en una bodega</strong>: físico, reservado, disponible y punto de pedido. El snapshot corresponde a la última carga correcta de la página; no es una actualización continua.</p>
      <Actions rows={[
        ["Ver cuántas existencias hay", "Consulta Físico, expresado en la unidad base del producto."],
        ["Ver lo comprometido", "Consulta Reservado: cantidades retenidas por reservas."],
        ["Ver lo libre de reservas", "Consulta Disponible: físico menos reservado, en esa bodega."],
        ["Detectar un registro bajo mínimo", "Compara Disponible con Punto pedido. Menor o igual cuenta en el indicador Bajo mínimo."],
      ]} />
      <p>Solo aparecen combinaciones con registro de existencias y configuración de inventario. Una fila ausente no confirma stock cero. Los valores se muestran con hasta dos decimales; el backend puede conservar más precisión. La configuración del punto de pedido es del producto y se repite en sus bodegas.</p>
      <p>Esta tabla no modifica cantidades directamente. Las entradas, transferencias, reservas y despachos registrados en el sistema actualizan los saldos que se muestran tras recargar los datos.</p>
      <TableHelp />
    </>,
  },
};

export default function InventoryCardInfo({ topic }: { topic: keyof typeof topics }) {
  const { title, body } = topics[topic];
  return <InfoPopup title={title} label={`Información: ${title}`}>{body}</InfoPopup>;
}
