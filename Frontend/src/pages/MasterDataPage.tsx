import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import BootstrapTable from "react-bootstrap-table-next";
import paginationFactory from "react-bootstrap-table2-paginator";
import { createMasterRecord, deleteMasterRecord, fetchMasterRecords, updateMasterRecord } from "../api";
import MasterDataEditorModal from "./components/MasterDataEditorModal";
import type { MasterField, MasterRecord } from "../types";

type ResourceConfig = { title: string; description: string; fields: MasterField[] };

const resources: Record<string, ResourceConfig> = {
  units: { title: "Unidades de medida", description: "Unidades base y de compra usadas por el inventario.", fields: [{ key: "code", label: "Código", required: true, placeholder: "unit" }, { key: "name", label: "Nombre", required: true, placeholder: "Unidad" }, { key: "description", label: "Descripción", type: "text" }] },
  currencies: { title: "Monedas", description: "Códigos ISO 4217 disponibles para documentos comerciales.", fields: [{ key: "iso_code", label: "Código ISO", required: true, placeholder: "EUR" }, { key: "name", label: "Nombre", required: true, placeholder: "Euro" }, { key: "symbol", label: "Símbolo", placeholder: "€" }] },
  warehouses: { title: "Bodegas", description: "Ubicaciones físicas para existencias y movimientos.", fields: [{ key: "code", label: "Código", required: true, placeholder: "MADRID" }, { key: "name", label: "Nombre", required: true }, { key: "description", label: "Descripción" }, { key: "is_active", label: "Activa", type: "checkbox" }] },
  suppliers: { title: "Proveedores", description: "Contrapartes para las órdenes y recepciones de compra.", fields: [{ key: "supplier_code", label: "Código" }, { key: "name", label: "Nombre", required: true }, { key: "email", label: "Email" }, { key: "phone", label: "Teléfono" }] },
  "unit-conversions": { title: "Conversiones de unidad", description: "Factores explícitos hacia la unidad base del producto.", fields: [{ key: "product_id", label: "ID de producto (vacío = global)", type: "number" }, { key: "from_unit_id", label: "ID unidad origen", type: "number", required: true }, { key: "to_unit_id", label: "ID unidad destino", type: "number", required: true }, { key: "factor", label: "Factor", type: "decimal", required: true, placeholder: "1" }] },
  "knowledge-documents": { title: "Base de conocimiento", description: "Documentos vigentes utilizados por el asistente RAG.", fields: [{ key: "title", label: "Título", required: true }, { key: "content", label: "Contenido", type: "textarea", required: true }, { key: "source", label: "Fuente", required: true, placeholder: "política interna" }, { key: "expires_at", label: "Caducidad ISO (opcional)", placeholder: "2026-12-31T23:59:59Z" }, { key: "is_active", label: "Activo", type: "checkbox" }] },
  "client-types": { title: "Tipos de cliente", description: "Estados y clasificación usados para clientes propios, prospectos y cuentas activas.", fields: [{ key: "name", label: "Nombre", required: true, placeholder: "Activo" }] },
  clients: { title: "Clientes", description: "Contrapartes comerciales asociadas a un tipo de cliente existente.", fields: [{ key: "client_code", label: "Código de cliente" }, { key: "name", label: "Nombre", required: true, placeholder: "Cliente ejemplo" }, { key: "description", label: "Descripción" }, { key: "fk_type_client", label: "ID tipo de cliente", type: "number", required: true, placeholder: "1 = Propio" }] },
  "global-addresses": { title: "Direcciones globales", description: "Direcciones reutilizables que pueden vincularse a clientes y otras entidades.", fields: [{ key: "address_line_1", label: "Dirección", required: true }, { key: "address_line_2", label: "Complemento" }, { key: "city", label: "Ciudad", required: true }, { key: "state_province", label: "Provincia / estado" }, { key: "postal_code", label: "Código postal" }, { key: "country_code", label: "Código país", required: true, placeholder: "ES" }, { key: "country_name", label: "País" }, { key: "contact_name", label: "Contacto" }, { key: "contact_phone", label: "Teléfono" }, { key: "contact_email", label: "Email" }, { key: "notes", label: "Notas", type: "textarea" }] },
};

function initialValues(config: ResourceConfig): Record<string, unknown> {
  return Object.fromEntries(config.fields.map((field) => [field.key, field.type === "checkbox" ? true : ""]));
}

export default function MasterDataPage({ resource }: { resource: string }) {
  const navigate = useNavigate();
  const config = resources[resource];
  const [records, setRecords] = useState<MasterRecord[]>([]);
  const [editor, setEditor] = useState<MasterRecord | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => { try { setRecords(await fetchMasterRecords(resource)); setError(""); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo cargar el maestro"); } };
  useEffect(() => { if (config) void load(); }, [resource]);
  if (!config) return <p className="error-line">Recurso maestro no disponible.</p>;
  const openCreate = () => { setEditor(null); setValues(initialValues(config)); setError(""); };
  const openEdit = (record: MasterRecord) => { setEditor(record); setValues(Object.fromEntries(config.fields.map((field) => [field.key, record[field.key] ?? (field.type === "checkbox" ? true : "")] ))); setError(""); };
  const save = async (event: FormEvent) => { event.preventDefault(); setSaving(true); try { if (editor) await updateMasterRecord(resource, editor.id, values); else await createMasterRecord(resource, values); setValues({}); setEditor(null); await load(); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo guardar"); } finally { setSaving(false); } };
  const remove = async (record: MasterRecord) => { if (!window.confirm(`¿Eliminar ${config.title.toLowerCase()} #${record.id}?`)) return; try { await deleteMasterRecord(resource, record.id); await load(); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo eliminar"); } };
  const columns = [
    { dataField: "id", text: "ID", sort: true, headerStyle: { width: "78px" } },
    ...config.fields.map((field) => ({
      dataField: field.key,
      text: field.label,
      sort: true,
      formatter: (value: unknown) => field.type === "checkbox" ? (value ? "Sí" : "No") : String(value ?? "—"),
    })),
    {
      dataField: "actions",
      text: "Acciones",
      isDummyField: true,
      formatter: (_value: unknown, record: MasterRecord) => <div className="actions-row master-table-actions">{resource === "clients" && <button className="chip-btn" onClick={() => navigate(`/maestros/clientes/${record.id}`)} type="button">Direcciones</button>}<button className="chip-btn" onClick={() => openEdit(record)} type="button">Editar</button><button className="danger-btn" onClick={() => void remove(record)} type="button">Eliminar</button></div>,
      headerStyle: { width: "190px" },
    },
  ];

  return <div className="grid master-page"><section className="card"><p className="section-label">Configuración · Datos maestros</p><h3>{config.title}</h3><p className="muted">{config.description}</p><button className="primary-btn" onClick={openCreate} type="button">Nuevo registro</button>{error && <p className="error-line">{error}</p>}</section><section className="card"><div className="master-table-wrapper"><BootstrapTable keyField="id" data={records} columns={columns} classes="users-table master-data-table" headerClasses="users-table" bordered={false} noDataIndication="No hay registros todavía." pagination={paginationFactory({ page: 1, pageStartIndex: 1, sizePerPage: 10, sizePerPageList: [{ text: "10", value: 10 }, { text: "25", value: 25 }, { text: "50", value: 50 }], showTotal: true, paginationTotalRenderer: (from: number, to: number, size: number) => `${from} - ${to} de ${size} registros` })} /></div></section>{values && Object.keys(values).length > 0 && <MasterDataEditorModal title={config.title} fields={config.fields} record={editor} values={values} saving={saving} error={error} onChange={(key, value) => setValues((current) => ({ ...current, [key]: value }))} onSubmit={(event) => void save(event)} onClose={() => { setValues({}); setEditor(null); setError(""); }} />}</div>;
}
