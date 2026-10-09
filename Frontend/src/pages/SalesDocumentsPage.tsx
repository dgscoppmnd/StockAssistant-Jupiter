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
  const columns = [
    { dataField: "number", text: invoice ? "Factura" : "Pedido", formatter: (value: string, row: SalesDocument) =>
      <button className="chip-btn" type="button" disabled={loading} aria-pressed={selectedId === row.id} onClick={() => setSearchParams({ id: String(row.id) })}>{value}</button> },
    { dataField: invoice ? "invoice_date" : "order_date", text: "Fecha" },
    { dataField: "customer_name", text: "Cliente" },
    { dataField: "status", text: "Estado" },
    { dataField: "currency_code", text: "Moneda" },
    { dataField: "total", text: "Total", formatter: (value: number) => Number(value).toFixed(2) },
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
  return <div className="stack sales-page">
    <div className="sales-no-print">
      <InventoryCrudCard sectionLabel="Ventas" title={invoice ? "Facturas de venta" : "Pedidos de venta"} titleIcon={<SectionIcon kind="cart" />}
        description={invoice ? "Documentos históricos vinculados a pedidos y despachos. Facturar no descuenta stock." : "Borradores, reservas y despachos con trazabilidad de inventario."}
        headerAction={<div className="actions-row"><button className="primary-btn" disabled={!allowed(invoice ? "invoice" : "create")} onClick={() => setEditor("create")}>{invoice ? "Agregar factura" : "Agregar pedido"}</button>
          <button className="chip-btn" disabled={loading} onClick={() => setRevision(value => value + 1)}>Actualizar</button></div>}>
        <div className="inventory-crud-grid sales-filters">
          <label>Buscar número, cliente o referencia<input value={query} onChange={e => { setQuery(e.target.value); setPage(1); }} /></label>
          <label>Estado<select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="">Todos</option>
            {["borrador","confirmado","parcial","completado","cancelado"].map(s => <option key={s}>{s}</option>)}</select></label>
          <ClientCombobox selected={client} onSelect={c => { setClient(c); setPage(1); }} />
          <button type="button" className="chip-btn" disabled={!client} onClick={() => { setClient(null); setPage(1); }}>Todos los clientes</button>
          <label>Desde<input type="date" value={from} onChange={e => { setFrom(e.target.value); setPage(1); }} /></label>
          <label>Hasta<input type="date" min={from} value={to} onChange={e => { setTo(e.target.value); setPage(1); }} /></label>
        </div>
        {(error || permissionError) && <p className="error-line" role="alert">{error || permissionError}</p>}
        {loading && <p role="status">Cargando documentos…</p>}
        <div className="users-table-wrapper" aria-busy={loading}>
          <BootstrapTable keyField="id" data={data.items} columns={columns} classes="users-table" bordered={false}
            noDataIndication={loading ? "Cargando…" : "Sin documentos"} remote={{ pagination: true }}
            pagination={paginationFactory({ page, sizePerPage: size, totalSize: data.total, sizePerPageList: [10,25,50], showTotal: true })}
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
