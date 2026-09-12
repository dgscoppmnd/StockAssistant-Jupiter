import type { FormEvent } from "react";
import MasterDataEditorModal from "./MasterDataEditorModal";
import type { MasterRecord } from "../../types";

export default function ClientEditorModal({ record, types, values, saving, error, onChange, onSubmit, onClose }: { record: MasterRecord | null; types: MasterRecord[]; values: Record<string, unknown>; saving: boolean; error: string; onChange: (key: string, value: unknown) => void; onSubmit: (event: FormEvent) => void; onClose: () => void }) {
  return <MasterDataEditorModal title="cliente" record={record} values={values} saving={saving} error={error} onChange={onChange} onSubmit={onSubmit} onClose={onClose} fields={[{ key: "client_code", label: "Código de cliente" }, { key: "name", label: "Nombre", required: true }, { key: "description", label: "Descripción" }, { key: "fk_type_client", label: "Tipo de cliente", type: "select", required: true, options: types.map((type) => ({ value: String(type.id), label: String(type.name) })) }]} />;
}
