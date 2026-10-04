import { FormEvent, useEffect, useState } from "react";
import BootstrapTable from "react-bootstrap-table-next";
import { addClientAddress, createMasterRecord, deleteClientAddress, deleteMasterRecord, fetchClientAddresses, fetchMasterRecords, importClientsCsv, updateClientAddress, updateMasterRecord } from "../api";
import type { ClientAddress, MasterRecord } from "../types";
import type { ClientImportProgress } from "../utils/clientCsvUpload";
import ClientAddressEditorModal from "./components/ClientAddressEditorModal";
import ClientEditorModal from "./components/ClientEditorModal";

export default function ClientsPage() {
  const [clients, setClients] = useState<MasterRecord[]>([]); const [types, setTypes] = useState<MasterRecord[]>([]); const [selected, setSelected] = useState<MasterRecord | null>(null); const [addresses, setAddresses] = useState<ClientAddress[]>([]); const [clientValues, setClientValues] = useState<Record<string, unknown>>({}); const [addressValues, setAddressValues] = useState<Record<string, unknown>>({}); const [editingAddress, setEditingAddress] = useState<ClientAddress | null>(null); const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  const [showImport, setShowImport] = useState(false); const [csvFile, setCsvFile] = useState<File | null>(null); const [importing, setImporting] = useState(false); const [importError, setImportError] = useState(""); const [importResult, setImportResult] = useState(""); const [importProgress, setImportProgress] = useState<ClientImportProgress | null>(null);
  const progressLabels = { uploading: "Subiendo archivo (1/3)", validating: "Validando CSV (2/3)", importing: "Importando clientes (3/3)", committing: "Confirmando el guardado", complete: "Importación completada" };
  const load = async () => { try { const [nextClients, nextTypes] = await Promise.all([fetchMasterRecords("clients"), fetchMasterRecords("client-types")]); setClients(nextClients); setTypes(nextTypes); setSelected((current) => nextClients.find((item) => item.id === current?.id) ?? null); } catch (err) { setError(err instanceof Error ? err.message : "No se pudieron cargar los clientes."); } };
  const loadAddresses = async (client: MasterRecord | null) => { if (!client) return setAddresses([]); try { setAddresses(await fetchClientAddresses(client.id)); } catch (err) { setError(err instanceof Error ? err.message : "No se pudieron cargar las direcciones."); } };
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
      const result = await importClientsCsv(csvFile, setImportProgress);
      setImportResult(`Importación completada: ${result.imported} clientes importados y ${result.skipped} omitidos por código existente, de ${result.total} clientes.`);
      setCsvFile(null); setShowImport(false);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo importar el CSV.";
      try {
        const parsed = JSON.parse(message) as { detail?: unknown };
        setImportError(typeof parsed.detail === "string" ? parsed.detail : message);
      } catch {
        setImportError(message);
      }
    } finally {
      setImporting(false);
    }
  };
  const saveClient = async (event: FormEvent) => { event.preventDefault(); setSaving(true); try { if (clientValues.id) await updateMasterRecord("clients", Number(clientValues.id), { client_code: clientValues.client_code, name: clientValues.name, description: clientValues.description, fk_type_client: Number(clientValues.fk_type_client) }); else await createMasterRecord("clients", { client_code: clientValues.client_code, name: clientValues.name, description: clientValues.description, fk_type_client: Number(clientValues.fk_type_client) }); setClientValues({}); await load(); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo guardar el cliente."); } finally { setSaving(false); } };
  const saveAddress = async (event: FormEvent) => { event.preventDefault(); if (!selected) return; setSaving(true); try { const { address_type, id: _associationId, global_address_id: _globalAddressId, ...globalValues } = addressValues; if (editingAddress) { await updateMasterRecord("global-addresses", editingAddress.global_address_id, globalValues); await updateClientAddress(selected.id, editingAddress.id, String(address_type)); } else { const global = await createMasterRecord("global-addresses", globalValues); await addClientAddress(selected.id, global.id, String(address_type)); } setAddressValues({}); setEditingAddress(null); await loadAddresses(selected); await load(); setError(""); } catch (err) { setError(err instanceof Error ? err.message : "No se pudo guardar la dirección."); } finally { setSaving(false); } };
  const columns = [{ dataField: "id", text: "ID", sort: true }, { dataField: "client_code", text: "Código de cliente", sort: true }, { dataField: "name", text: "Cliente", sort: true }, { dataField: "fk_type_client", text: "Tipo", formatter: (value: number) => types.find((type) => type.id === value)?.name ?? value }, { dataField: "actions", text: "Acciones", isDummyField: true, formatter: (_: unknown, row: MasterRecord) => <div className="actions-row"><button className="chip-btn" onClick={() => setClientValues({ id: row.id, client_code: row.client_code ?? "", name: row.name, description: row.description ?? "", fk_type_client: row.fk_type_client })} type="button">Editar</button><button className="danger-btn" disabled={Boolean(row.is_in_use)} onClick={() => void deleteMasterRecord("clients", row.id).then(load).catch((err) => setError(err.message))} type="button">Borrar</button></div> }];
  return <div className="grid clients-master-detail">
    <section className="card"><div className="actions-row"><div>
      <p className="section-label">Configuración · Clientes</p>
      <h3>Clientes</h3>
    </div>
      <button className="primary-btn"
        onClick={() => setClientValues(
          {
            client_code: "",
            name: "",
            description: "",
            fk_type_client: types.find((type) => type.id === 1)?.id ?? types[0]?.id ?? ""
          })} type="button">Agregar cliente</button>
      <button className="primary-btn"
        onClick={() => { setShowImport(!showImport); setCsvFile(null); setImportError(""); setImportProgress(null); }}
        type="button" disabled={importing} aria-expanded={showImport} aria-controls="client-csv-import">
        Importar CSV
      </button>
    </div>{
        error && <p className="error-line">{error}</p>}
      {importResult && <p role="status">{importResult}</p>}
      {importProgress && !importError && <div style={{ margin: "16px 0" }}>
        <p id="client-import-progress-label" role="status" style={{ marginBottom: 6 }}>
          {progressLabels[importProgress.stage]}
          {importProgress.stage !== "committing" && `: ${importProgress.percent}%`}
          {importProgress.stage === "importing" && ` · ${importProgress.processed?.toLocaleString("es-ES")} de ${importProgress.total?.toLocaleString("es-ES")} clientes procesados`}
        </p>
        <progress aria-labelledby="client-import-progress-label" max={100} value={importProgress.stage === "committing" ? undefined : importProgress.percent} style={{ width: "100%", height: 22, accentColor: "#2563eb" }} />
      </div>}
      {showImport && <form id="client-csv-import" onSubmit={onImport} className="master-table-wrapper" style={{ padding: 20, marginBottom: 20 }} aria-busy={importing}>
        <h4>Importar clientes desde CSV</h4>
        <p>Usa el formato de formatoEjemploClientes.csv: UTF-8, separado por comas, de hasta 200 MB.</p>
        <p style={{ overflowWrap: "anywhere" }}><strong>Cabecera:</strong> code_cliente,name_client,description,tipo_cliente</p>
        <p>El tipo debe coincidir con el nombre de un tipo de cliente existente. También se acepta “tipo cliente” como nombre de la última columna.</p>
        <p>Se omiten los códigos de cliente existentes. Los códigos repetidos dentro del CSV, tipos inexistentes o filas inválidas impiden importar el archivo completo.</p>
        <label htmlFor="client-csv-file">Archivo CSV</label>{" "}
        <input id="client-csv-file" type="file" accept=".csv,text/csv" disabled={importing} required onChange={(event) => { setCsvFile(event.target.files?.[0] ?? null); setImportError(""); }} />
        <div className="actions-row" style={{ marginTop: 16 }}>
          <button className="primary-btn" type="submit" disabled={!csvFile || importing}>{importing ? "Importando..." : "Importar clientes"}</button>
          <button className="chip-btn" type="button" disabled={importing} onClick={() => { setShowImport(false); setCsvFile(null); setImportError(""); }}>Cancelar</button>
        </div>
        {importError && <p className="error-line" role="alert">{importError}</p>}
      </form>}
      <div className="master-table-wrapper">
        <BootstrapTable keyField="id"
          data={clients}
          columns={columns}
          rowEvents={{
            onClick: (_event: unknown, row: MasterRecord) => setSelected(row)
          }
          } classes="users-table master-data-table"
          bordered={false}
          noDataIndication="No hay clientes." />
      </div>
    </section>
    <section className="card">
      <div className="client-address-tab">Direcciones{selected ? ` · ${String(selected.name)}` : ""}
      </div>
      {selected ? <><div className="actions-row">
          <p className="muted">Direcciones asociadas al cliente seleccionado.</p>
          <button className="primary-btn"
            onClick={() => {
              setEditingAddress(null);
              setAddressValues(
                {
                  address_type: "Dirección principal",
                  country_code: "ES"
                });
            }}
            type="button">Agregar dirección</button>
        </div>
        <div className="master-table-wrapper">
          <BootstrapTable keyField="id"
            data={addresses}
            columns={
              [{ dataField: "address_type", text: "Tipo" },
              { dataField: "address_line_1", text: "Dirección" },
              { dataField: "city", text: "Ciudad" },
              { dataField: "country_code", text: "País" },
              { dataField: "actions", text: "Acciones", isDummyField: true,
                formatter: (_: unknown, row: ClientAddress) => <div className="actions-row">
                  <button className="chip-btn"
                          onClick={() => { setEditingAddress(row);
                                          setAddressValues({ ...row }); }}
                          type="button">Editar
                  </button>
                  <button className="danger-btn"
                    onClick={() => void deleteClientAddress(selected.id, row.id).then(async () => {
                                                                                          await loadAddresses(selected);
                                                                                          await load();
                                                                                        }).catch((err) => setError(err.message))}
                    type="button">Quitar</button>
                </div>
              }]}
            classes="users-table master-data-table"
            bordered={false}
            noDataIndication="No hay direcciones asociadas." />
          </div></> : <p className="muted">Selecciona un cliente en la tabla superior para ver sus direcciones.</p>
        }</section>
    {Object.keys(clientValues).length > 0 && <ClientEditorModal
      record={clientValues.id ? { id: Number(clientValues.id) } : null}
      types={types}
      values={clientValues}
      saving={saving}
      error={error}
      onChange={(key, value) => setClientValues((current) => ({ ...current, [key]: value }))}
      onSubmit={(event) => void saveClient(event)}
      onClose={() => setClientValues({})} />}
    {Object.keys(addressValues).length > 0 && <ClientAddressEditorModal
      record={editingAddress ? { id: editingAddress.id } : null}
      values={addressValues} saving={saving} error={error}
      onChange={(key, value) => setAddressValues((current) => ({ ...current, [key]: value }))}
      onSubmit={(event) => void saveAddress(event)}
      onClose={() => { setAddressValues({}); setEditingAddress(null); }} />}
  </div>;
}
