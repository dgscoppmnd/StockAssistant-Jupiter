import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import BootstrapTable from "react-bootstrap-table-next";
import paginationFactory from "react-bootstrap-table2-paginator";
import { fetchSalesDocument, fetchSalesDocuments, fetchSalesPermissions } from "../api";
import type { SalesClient, SalesDocument, SalesKind, SalesPage, SalesPermission } from "../types";
import ClientCombobox from "./components/ClientCombobox";
import InventoryCrudCard from "./components/InventoryCrudCard";
import SectionIcon from "./components/SectionIcon";
import SalesOrderEditorModal from "./components/SalesOrderEditorModal";
import SalesOperationModal, { type SalesOperationMode } from "./components/SalesOperationModal";
import SalesActionModal from "./components/SalesActionModal";
import SalesDocumentDetail from "./components/SalesDocumentDetail";

const statusLabels: Record<string, string> = {
  borrador: "Borrador", confirmado: "Confirmado", parcial: "Parcial", completado: "Completado", cancelado: "Cancelado",
};

function SalesIcon({ name }: { name: "plus" | "refresh" | "search" | "filter" }) {
  return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === "plus" && <path d="M12 5v14M5 12h14" />}
    {name === "refresh" && <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M6.1 7a7 7 0 0 1 11.6-1L20 9M4 15l2.3 3A7 7 0 0 0 17.9 17" /></>}
    {name === "search" && <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></>}
    {name === "filter" && <><path d="M4 7h16M7 12h10M10 17h4" /></>}
  </svg>;
}

export default function SalesDocumentsPage({ kind }: { kind: SalesKind }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = Number(searchParams.get("id")) || 0;
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(10);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [client, setClient] = useState<SalesClient | null>(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [data, setData] = useState<SalesPage>({ items: [], total: 0, page: 1, size: 10 });
  const [detail, setDetail] = useState<SalesDocument | null>(null);
  const [permissions, setPermissions] = useState<SalesPermission[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [permissionError, setPermissionError] = useState("");
  const [revision, setRevision] = useState(0);
  const [editor, setEditor] = useState<"create" | "edit" | null>(null);
  const [operation, setOperation] = useState<SalesOperationMode | null>(null);
  const [action, setAction] = useState<"delete" | "cancel" | "issue" | "void" | null>(null);
  const invoice = kind === "invoices";
  useEffect(() => {
    let alive = true;
    void fetchSalesPermissions().then(result => { if (alive) { setPermissions(result.permissions); setPermissionError(""); } })
      .catch(err => { if (alive) setPermissionError(String(err)); });
    return () => { alive = false; };
  }, [revision]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    const timer = window.setTimeout(() => {
      void fetchSalesDocuments(kind,{ q: query, status, client_id: client?.id ?? "", date_from: from, date_to: to, page, size },controller.signal)
        .then(result => {
          if (!controller.signal.aborted) {
            setData(result);
            if (!result.items.length && page > 1) setPage(Math.max(1, Math.ceil(result.total / size)));
          }
        }).catch(err => { if (!controller.signal.aborted) { setError(String(err)); setData({ items: [], total: 0, page, size }); } })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 200);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [kind,query,status,client?.id,from,to,page,size,revision]);
  useEffect(() => {
    if (!selectedId) { setDetail(null); setDetailError(""); return; }
    const controller = new AbortController();
    setDetail(null); setDetailLoading(true); setDetailError("");
    void fetchSalesDocument(kind,selectedId,controller.signal)
      .then(document => { if (!controller.signal.aborted) setDetail(document); })
      .catch(err => { if (!controller.signal.aborted) setDetailError(String(err)); })
      .finally(() => { if (!controller.signal.aborted) setDetailLoading(false); });
    return () => controller.abort();
  }, [kind,selectedId,revision]);
  const allowed = (permission: SalesPermission) => permissions.includes(permission);
  const saved = (id: number) => { setEditor(null); setOperation(null); setSearchParams({ id: String(id) }); setRevision(value => value + 1); };
  const actionSaved = (deleted: boolean) => { setAction(null); if (deleted) setSearchParams({}); setRevision(value => value + 1); };
  const draft = detail?.status === "borrador";
  const hasFilters = Boolean(query || status || client || from || to);
  const clearFilters = () => { setQuery(""); setStatus(""); setClient(null); setFrom(""); setTo(""); setPage(1); };
  const columns = [
    { dataField: "number", text: invoice ? "Factura" : "Pedido", headerStyle: { width: "360px" }, formatter: (value: string, row: SalesDocument) =>
      <button className="sales-document-link" type="button" disabled={loading} aria-pressed={selectedId === row.id} onClick={() => setSearchParams({ id: String(row.id) })}>{value}<span aria-hidden="true">↗</span></button> },
    { dataField: invoice ? "invoice_date" : "order_date", text: "Fecha", formatter: (value?: string) => value ? new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString("es-ES") : "—" },
    { dataField: "customer_name", text: "Cliente", classes: "sales-customer-cell" },
    { dataField: "status", text: "Estado", formatter: (value: string) => <span className={`sales-status sales-status--${value}`}><span aria-hidden="true" />{statusLabels[value] ?? value}</span> },
    { dataField: "currency_code", text: "Moneda", classes: "sales-currency-cell" },
    { dataField: "total", text: "Total", align: "right", headerAlign: "right", classes: "sales-total-cell", formatter: (value: number) => Number(value).toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
  ];
  const detailActions = <div className="actions-row">
    {draft && <button className="chip-btn" disabled={!allowed(invoice ? "invoice" : "edit")} onClick={() => setEditor("edit")}>Editar</button>}
    {draft && <button className="danger-btn" disabled={!allowed(invoice ? "invoice" : "delete")} onClick={() => setAction("delete")}>Eliminar borrador</button>}
    {!invoice && detail && ["borrador","confirmado","parcial"].includes(detail.status) &&
      <button className="primary-btn" disabled={!allowed("reserve")} onClick={() => setOperation("reserve")}>Confirmar / reservar</button>}
    {!invoice && detail && ["confirmado","parcial"].includes(detail.status) && <>
      <button className="primary-btn" disabled={!allowed("dispatch") || !allowed("invoice")} onClick={() => setOperation("dispatch")}>Despachar y facturar</button>
      <button className="danger-btn" disabled={!allowed("edit")} onClick={() => setAction("cancel")}>Cancelar pendientes</button>
    </>}
    {!invoice && detail?.lines.some(l => Number(l.dispatched_qty) > Number(l.returned_qty)) &&
      <button className="chip-btn" disabled={!allowed("return")} onClick={() => setOperation("return")}>Registrar devolución</button>}
    {invoice && draft && <button className="primary-btn" disabled={!allowed("invoice")} onClick={() => setAction("issue")}>Emitir</button>}
    {invoice && detail?.status === "confirmado" && !detail.correction_of_id &&
      <button className="danger-btn" disabled={!allowed("void")} onClick={() => setAction("void")}>Anular con rectificativa</button>}
    {invoice && <button className="chip-btn" onClick={() => window.print()}>Imprimir</button>}
  </div>;
  return <div className="stack sales-page sales-workspace">
    <div className="sales-no-print">
      <InventoryCrudCard sectionLabel="Ventas" title={invoice ? "Facturas de venta" : "Pedidos de venta"} titleIcon={<SectionIcon kind="cart" />}
        description={invoice ? "Documentos históricos vinculados a pedidos y despachos. Facturar no descuenta stock." : "Gestiona tus ventas, desde el primer borrador hasta el último despacho."}
        headerAction={<div className="actions-row"><button className="chip-btn sales-refresh" disabled={loading} onClick={() => setRevision(value => value + 1)}><SalesIcon name="refresh" />Actualizar</button>
          <button className="primary-btn" title={!allowed(invoice ? "invoice" : "create") ? "Se necesita permiso para crear documentos" : undefined} disabled={!allowed(invoice ? "invoice" : "create")} onClick={() => setEditor("create")}><SalesIcon name="plus" />{invoice ? "Nueva factura" : "Nuevo pedido"}</button></div>}>
        <div className="sales-filter-panel">
          <div className="sales-filter-heading"><span><SalesIcon name="filter" />Filtrar {invoice ? "facturas" : "pedidos"}</span><button type="button" className="sales-clear" disabled={!hasFilters} onClick={clearFilters}>Limpiar filtros</button></div>
          <div className="sales-filters">
            <label className="sales-search">Buscar<span className="sales-search-control"><SalesIcon name="search" /><input placeholder="Número, cliente o referencia…" value={query} onChange={e => { setQuery(e.target.value); setPage(1); }} /></span></label>
            <label>Estado<select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="">Todos los estados</option>
              {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <div className="sales-client-filter"><ClientCombobox selected={client} onSelect={c => { setClient(c); setPage(1); }} />
              {client && <button type="button" className="sales-clear" onClick={() => { setClient(null); setPage(1); }}>Quitar cliente</button>}</div>
            <div className="sales-date-range"><label>Desde<input type="date" max={to || undefined} value={from} onChange={e => { setFrom(e.target.value); setPage(1); }} /></label>
              <span aria-hidden="true">—</span><label>Hasta<input type="date" min={from} value={to} onChange={e => { setTo(e.target.value); setPage(1); }} /></label></div>
          </div>
        </div>
        {(error || permissionError) && <div className="sales-error" role="alert"><span>{error || permissionError}</span><button type="button" className="chip-btn" disabled={loading} onClick={() => setRevision(value => value + 1)}>Reintentar</button></div>}
        <div className="sales-list-heading"><h4>{invoice ? "Listado de facturas" : "Listado de pedidos"}<span className="sales-count">{loading ? "…" : data.total}</span></h4><span role="status">{loading ? "Actualizando documentos…" : hasFilters ? "Resultados filtrados" : "Todos los registros"}</span></div>
        <div className={`users-table-wrapper sales-list-table${!data.items.length ? " sales-list-table--empty" : ""}`} aria-label={invoice ? "Facturas de venta" : "Pedidos de venta"} aria-busy={loading}>
          <BootstrapTable keyField="id" data={data.items} columns={columns} classes="users-table" bordered={false}
            rowClasses={(row: SalesDocument) => selectedId === row.id ? "sales-row-selected" : ""}
            noDataIndication={<div className="sales-empty"><SectionIcon kind="cart" /><strong>{loading ? "Cargando documentos…" : error ? "No se pudieron cargar los documentos" : hasFilters ? "Sin resultados para estos filtros" : invoice ? "Todavía no hay facturas" : "Todavía no hay pedidos"}</strong><span>{loading ? "El listado estará listo en un momento." : error ? "Vuelve a intentarlo para consultar el listado." : hasFilters ? "Prueba con otro estado, cliente o intervalo de fechas." : "Crea el primer documento para empezar a gestionar tus ventas."}</span>{hasFilters && !loading && !error && <button type="button" className="chip-btn" onClick={clearFilters}>Limpiar filtros</button>}</div>} remote={{ pagination: true }}
            pagination={paginationFactory({ page, sizePerPage: size, totalSize: data.total, sizePerPageList: [10,25,50], showTotal: true,
              paginationTotalRenderer: (from: number, to: number, total: number) => <span className="sales-pagination-total">{total ? from : 0}–{to} de {total} {invoice ? "facturas" : "pedidos"}</span>,
              firstPageTitle: "Primera página", prePageTitle: "Página anterior", nextPageTitle: "Página siguiente", lastPageTitle: "Última página" })}
            onTableChange={(_type: string, state: { page: number; sizePerPage: number }) => { setPage(state.page); setSize(state.sizePerPage); }} />
        </div>
      </InventoryCrudCard>
    </div>
    {detailError && <p className="error-line" role="alert">{detailError}</p>}
    {detailLoading && <p role="status">Cargando detalle…</p>}
    {detail && <SalesDocumentDetail kind={kind} document={detail} actions={detailActions} />}
    {editor && !invoice && <SalesOrderEditorModal record={editor === "edit" ? detail : null} onClose={() => setEditor(null)} onSaved={saved} />}
    {editor && invoice && <SalesOperationModal mode="invoice" order={null} invoice={editor === "edit" && detail ? detail : undefined} onClose={() => setEditor(null)} onSaved={saved} />}
    {operation && detail && <SalesOperationModal mode={operation} order={detail} onClose={() => setOperation(null)} onSaved={saved} />}
    {action && detail && <SalesActionModal kind={kind} id={detail.id} action={action} onClose={() => setAction(null)} onSaved={actionSaved} />}
  </div>;
}
