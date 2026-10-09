import BootstrapTable from "react-bootstrap-table-next";
import { Link } from "react-router-dom";
import type { SalesDocument, SalesKind } from "../../types";
import InventoryCrudCard from "./InventoryCrudCard";
import SectionIcon from "./SectionIcon";

export default function SalesDocumentDetail({ kind, document, actions }: {
  kind: SalesKind; document: SalesDocument; actions: JSX.Element;
}) {
  const invoice = kind === "invoices";
  const number = document.invoice_number ?? document.sales_order_number;
  const columns = invoice ? [
    { dataField: "description_snapshot", text: "Producto" },
    { dataField: "invoiced_qty", text: "Cantidad" },
    { dataField: "unit_snapshot", text: "Unidad" },
    { dataField: "unit_price", text: "Precio" },
    { dataField: "discount_percent", text: "Desc. %" },
    { dataField: "tax_percent", text: "Imp. %" },
    { dataField: "line_subtotal", text: "Base" },
    { dataField: "line_tax", text: "Impuesto" },
    { dataField: "line_total", text: "Total" },
  ] : [
    { dataField: "description_snapshot", text: "Producto" },
    { dataField: "unit_code", text: "Unidad base" },
    { dataField: "requested_qty", text: "Solicitado" },
    { dataField: "reserved_qty", text: "Reserva actual" },
    { dataField: "dispatched_qty", text: "Despachado" },
    { dataField: "invoiced_qty", text: "Facturado" },
    { dataField: "canceled_qty", text: "Cancelado" },
    { dataField: "returned_qty", text: "Devuelto" },
    { dataField: "pending_qty", text: "Pendiente" },
    { dataField: "unit_price", text: "Precio" },
    { dataField: "discount_percent", text: "Desc. %" },
    { dataField: "tax_percent", text: "Imp. %" },
    { dataField: "line_total", text: "Total de línea" },
  ];
  const address = invoice ? document.customer_snapshot?.address : document.address_snapshot;
  return <div className={invoice ? "sales-document-detail sales-invoice-print" : "sales-document-detail"}>
    <InventoryCrudCard sectionLabel={invoice ? "Factura de venta" : "Pedido de venta"} title={number ?? "Documento"} titleIcon={<SectionIcon kind="cart" />}
      headerAction={<div className="sales-no-print">{actions}</div>}>
      <div className="inventory-crud-grid">
        <p><strong>Cliente:</strong> {document.customer_snapshot?.name ?? document.customer_name}</p>
        <p><strong>Estado:</strong> {document.status}</p>
        <p><strong>Fecha:</strong> {document.invoice_date ?? document.order_date}</p>
        {invoice && <p><strong>Vencimiento:</strong> {document.due_date || "Sin vencimiento"}</p>}
        <p><strong>Referencia:</strong> {document.reference || "—"}</p>
        {address && <p><strong>Dirección:</strong> {[address.address_line_1, address.address_line_2, address.city, address.postal_code, address.country_code].filter(Boolean).join(", ") || "Sin dirección"}</p>}
      </div>
      {document.order_number && <p>Pedido: <Link to={`/ventas/pedidos?id=${document.sales_order_id}`}>{document.order_number}</Link></p>}
      {document.correction_of_id && <p>Rectificativa de <Link to={`/ventas/facturas?id=${document.correction_of_id}`}>factura #{document.correction_of_id}</Link></p>}
      {document.void_reason && <p><strong>Motivo de anulación:</strong> {document.void_reason}</p>}
      <div className="users-table-wrapper"><BootstrapTable keyField="id" data={document.lines} columns={columns} bordered={false} classes="users-table" noDataIndication="Sin líneas" /></div>
      <p><strong>Base:</strong> {Number(document.subtotal).toFixed(2)} · <strong>Impuestos:</strong> {Number(document.tax_total).toFixed(2)} · <strong>Total:</strong> {Number(document.total).toFixed(2)} {document.currency_code}</p>
      {document.notes && <p>{document.notes}</p>}
      {!invoice && <div className="sales-related">
        <h4>Documentos relacionados</h4>
        <p>Facturas: {document.invoices?.length ? document.invoices.map(i => <Link key={i.id} to={`/ventas/facturas?id=${i.id}`}>{i.invoice_number} ({i.status}) </Link>) : "Ninguna"}</p>
        <p>Despachos: {document.dispatches?.map(d => d.dispatch_number).join(", ") || "Ninguno"}</p>
        <p>Devoluciones: {document.returns?.map(r => `${r.return_number} · ${r.reason}`).join(", ") || "Ninguna"}</p>
      </div>}
      <div className="sales-no-print">
        <h4>Auditoría</h4>
        {document.events?.length ? <ul>{document.events.map(e => <li key={e.id}>{new Date(e.created_at).toLocaleString("es-ES")} · {e.action} · {e.user_name}</li>)}</ul> : <p>Sin eventos del nuevo módulo.</p>}
      </div>
    </InventoryCrudCard>
  </div>;
}
