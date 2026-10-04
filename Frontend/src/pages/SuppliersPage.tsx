import { FormEvent, useEffect, useState } from "react";
import BootstrapTable from "react-bootstrap-table-next";
import { addSupplierAddress, createMasterRecord, deleteMasterRecord, deleteSupplierAddress, fetchMasterRecords, fetchSupplierAddresses, importSuppliersCsv, updateMasterRecord, updateSupplierAddress } from "../api";
import type { ClientAddress, MasterRecord } from "../types";
import type { SupplierImportProgress } from "../utils/supplierCsvUpload";
import ClientAddressEditorModal from "./components/ClientAddressEditorModal";
import MasterDataEditorModal from "./components/MasterDataEditorModal";

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<MasterRecord[]>([]); const [selected, setSelected] = useState<MasterRecord | null>(null); const [addresses, setAddresses] = useState<ClientAddress[]>([]); const [supplierValues, setSupplierValues] = useState<Record<string, unknown>>({}); const [addressValues, setAddressValues] = useState<Record<string, unknown>>({}); const [editing, setEditing] = useState<ClientAddress | null>(null); const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  const [showImport, setShowImport] = useState(false); const [csvFile, setCsvFile] = useState<File | null>(null); const [importing, setImporting] = useState(false); const [importError, setImportError] = useState(""); const [importResult, setImportResult] = useState(""); const [importProgress, setImportProgress] = useState<SupplierImportProgress | null>(null);
  const progressLabels = { uploading: "Subiendo archivo (1/3)", validating: "Validando CSV (2/3)", importing: "Importando proveedores (3/3)", committing: "Confirmando el guardado", complete: "Importación completada" };

  const load = async () => { try { const rows = await fetchMasterRecords("suppliers"); setSuppliers(rows); setSelected((current) => rows.find((row) => row.id === current?.id) ?? null); } catch (err) { setError(err instanceof Error ? err.message : "No se pudieron cargar proveedores."); } };
  const loadAddresses = async (supplier: MasterRecord | null) => { if (!supplier) return setAddresses([]); try { setAddresses(await fetchSupplierAddresses(supplier.id)); } catch (err) { setError(err instanceof Error ? err.message : "No se pudieron cargar direcciones."); } };
  useEffect(() => { void load(); }, []); useEffect(() => { void loadAddresses(selected); }, [selected?.id]);

  const onImport = async (event: FormEvent) => {
    event.preventDefault();
    if (!csvFile || importing) return;
    setImportError(""); setImportResult(""); setImportProgress(null);
    if (!csvFile.name.toLowerCase().endsWith(".csv") || csvFile.size > 200 * 1024 * 1024) {
      setImportError("Selecciona un archivo .csv de hasta 200 MB.");
      return;
    }
    setImporting(true);
    try {
      const result = await importSuppliersCsv(csvFile, setImportProgress);
      setImportResult(`Importación completada: ${result.imported} proveedores importados y ${result.skipped} omitidos por código existente, de ${result.total} proveedores.`);
      setCsvFile(null); setShowImport(false);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo importar el CSV.";
      try { const parsed = JSON.parse(message) as { detail?: unknown }; setImportError(typeof parsed.detail === "string" ? parsed.detail : message); }
      catch { setImportError(message); }
    } finally { setImporting(false); }
  };

  const saveSupplier = async (event: FormEvent) => { event.preventDefault(); setSaving(true); try { const data = { supplier_code: supplierValues.supplier_code, name: supplierValues.name, email: supplierValues.email, phone: supplierValues.phone }; if (supplierValues.id) await updateMasterRecord("suppliers", Number(supplierValues.id), data); else await createMasterRecord("suppliers", data); setSupplierValues({}); await load(); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo guardar el proveedor."); } finally { setSaving(false); } };
  const saveAddress = async (event: FormEvent) => { event.preventDefault(); if (!selected) return; setSaving(true); try { const { address_type, id: _associationId, global_address_id: _globalAddressId, ...global } = addressValues; if (editing) { await updateMasterRecord("global-addresses", editing.global_address_id, global); await updateSupplierAddress(selected.id, editing.id, String(address_type)); } else { const created = await createMasterRecord("global-addresses", global); await addSupplierAddress(selected.id, created.id, String(address_type)); } setAddressValues({}); setEditing(null); await loadAddresses(selected); await load(); setError(""); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo guardar la dirección."); } finally { setSaving(false); } };
  const supplierColumns = [{ dataField: "id", text: "ID" }, { dataField: "supplier_code", text: "Código de proveedor", sort: true }, { dataField: "name", text: "Proveedor" }, { dataField: "email", text: "Email" }, { dataField: "actions", text: "Acciones", isDummyField: true, formatter: (_: unknown, row: MasterRecord) => <div className="actions-row"><button className="chip-btn" onClick={() => setSupplierValues({ id: row.id, supplier_code: row.supplier_code ?? "", name: row.name, email: row.email ?? "", phone: row.phone ?? "" })} type="button">Editar</button><button className="danger-btn" disabled={Boolean(row.is_in_use)} onClick={() => void deleteMasterRecord("suppliers", row.id).then(load).catch((err) => setError(err.message))} type="button">Borrar</button></div> }];

  return <div className="grid clients-master-detail">
    <section className="card">
      <div className="actions-row">
        <div><p className="section-label">Configuración · Proveedores</p><h3>Proveedores</h3></div>
        <button className="primary-btn" onClick={() => setSupplierValues({ supplier_code: "", name: "", email: "", phone: "" })} type="button">Agregar proveedor</button>
        <button className="primary-btn" onClick={() => { setShowImport(!showImport); setCsvFile(null); setImportError(""); setImportProgress(null); }} type="button" disabled={importing} aria-expanded={showImport} aria-controls="supplier-csv-import">Importar CSV</button>
      </div>
      {error && <p className="error-line">{error}</p>}
      {importResult && <p role="status">{importResult}</p>}
      {importProgress && !importError && <div style={{ margin: "16px 0" }}>
        <p id="supplier-import-progress-label" role="status" style={{ marginBottom: 6 }}>
          {progressLabels[importProgress.stage]}
          {importProgress.stage !== "committing" && `: ${importProgress.percent}%`}
          {importProgress.stage === "importing" && ` · ${importProgress.processed?.toLocaleString("es-ES")} de ${importProgress.total?.toLocaleString("es-ES")} proveedores procesados`}
        </p>
        <progress aria-labelledby="supplier-import-progress-label" max={100} value={importProgress.stage === "committing" ? undefined : importProgress.percent} style={{ width: "100%", height: 22, accentColor: "#2563eb" }} />
      </div>}
      {showImport && <form id="supplier-csv-import" onSubmit={onImport} className="master-table-wrapper" style={{ padding: 20, marginBottom: 20 }} aria-busy={importing}>
        <h4>Importar proveedores desde CSV</h4>
        <p>Usa el formato de formatoEjemploProveedores.csv: UTF-8, separado por comas, de hasta 200 MB.</p>
        <p style={{ overflowWrap: "anywhere" }}><strong>Cabecera:</strong> supplier_code,name,email,phone</p>
        <p>También se acepta la cabecera code_proveedor,name_supplier,email,phone.</p>
        <p>Se omiten los códigos de proveedor existentes. Los códigos o nombres repetidos y las filas inválidas impiden importar el archivo completo.</p>
        <label htmlFor="supplier-csv-file">Archivo CSV</label>{" "}
        <input id="supplier-csv-file" type="file" accept=".csv,text/csv" disabled={importing} required onChange={(event) => { setCsvFile(event.target.files?.[0] ?? null); setImportError(""); }} />
        <div className="actions-row" style={{ marginTop: 16 }}>
          <button className="primary-btn" type="submit" disabled={!csvFile || importing}>{importing ? "Importando..." : "Importar proveedores"}</button>
          <button className="chip-btn" type="button" disabled={importing} onClick={() => { setShowImport(false); setCsvFile(null); setImportError(""); }}>Cancelar</button>
        </div>
        {importError && <p className="error-line" role="alert">{importError}</p>}
      </form>}
      <div className="master-table-wrapper"><BootstrapTable keyField="id" data={suppliers} columns={supplierColumns} rowEvents={{ onClick: (_: unknown, row: MasterRecord) => setSelected(row) }} classes="users-table master-data-table" bordered={false} noDataIndication="No hay proveedores." /></div>
    </section>
    <section className="card">
      <div className="client-address-tab">Direcciones{selected ? ` · ${String(selected.name)}` : ""}</div>
      {selected ? <><div className="actions-row"><p className="muted">Direcciones asociadas al proveedor seleccionado.</p><button className="primary-btn" onClick={() => { setEditing(null); setAddressValues({ address_type: "Dirección principal", country_code: "ES" }); }} type="button">Agregar dirección</button></div><BootstrapTable keyField="id" data={addresses} columns={[{ dataField: "address_type", text: "Tipo" }, { dataField: "address_line_1", text: "Dirección" }, { dataField: "city", text: "Ciudad" }, { dataField: "actions", text: "Acciones", isDummyField: true, formatter: (_: unknown, row: ClientAddress) => <div className="actions-row"><button className="chip-btn" onClick={() => { setEditing(row); setAddressValues({ ...row }); }} type="button">Editar</button><button className="danger-btn" onClick={() => void deleteSupplierAddress(selected.id, row.id).then(async () => { await loadAddresses(selected); await load(); }).catch((err) => setError(err.message))} type="button">Quitar</button></div> }]} classes="users-table master-data-table" bordered={false} noDataIndication="No hay direcciones asociadas." /></> : <p className="muted">Selecciona un proveedor en la tabla superior.</p>}
    </section>
    {Object.keys(supplierValues).length > 0 && <MasterDataEditorModal title="proveedor" record={supplierValues.id ? { id: Number(supplierValues.id) } : null} values={supplierValues} saving={saving} error={error} onChange={(key, value) => setSupplierValues((current) => ({ ...current, [key]: value }))} onSubmit={(event) => void saveSupplier(event)} onClose={() => setSupplierValues({})} fields={[{ key: "supplier_code", label: "Código de proveedor" }, { key: "name", label: "Nombre", required: true }, { key: "email", label: "Email" }, { key: "phone", label: "Teléfono" }]} />}
    {Object.keys(addressValues).length > 0 && <ClientAddressEditorModal title="dirección del proveedor" record={editing ? { id: editing.id } : null} values={addressValues} saving={saving} error={error} onChange={(key, value) => setAddressValues((current) => ({ ...current, [key]: value }))} onSubmit={(event) => void saveAddress(event)} onClose={() => { setAddressValues({}); setEditing(null); }} />}
  </div>;
}
