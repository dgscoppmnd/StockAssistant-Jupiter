import type { FormEvent } from "react";
import MasterDataEditorModal from "./MasterDataEditorModal";
import type { MasterRecord } from "../../types";

const addressTypes = ["Dirección principal", "Dirección por defecto", "Dirección de entrega", "Dirección de Recogida"];
export default function ClientAddressEditorModal({ record, values, saving, error, onChange, onSubmit, onClose, title = "dirección del cliente" }: { record: MasterRecord | null; values: Record<string, unknown>; saving: boolean; error: string; onChange: (key: string, value: unknown) => void; onSubmit: (event: FormEvent) => void; onClose: () => void; title?: string }) {
  return <MasterDataEditorModal title={title} record={record} values={values} saving={saving} error={error} onChange={onChange} onSubmit={onSubmit} onClose={onClose} fields={[{ key: "address_line_1", label: "Dirección", required: true }, { key: "address_line_2", label: "Complemento" }, { key: "city", label: "Ciudad", required: true }, { key: "state_province", label: "Provincia / estado" }, { key: "postal_code", label: "Código postal" }, { key: "country_code", label: "Código país", required: true, placeholder: "ES" }, { key: "country_name", label: "País" }, { key: "contact_name", label: "Contacto" }, { key: "contact_phone", label: "Teléfono" }, { key: "contact_email", label: "Email" }, { key: "notes", label: "Notas", type: "textarea" }, { key: "address_type", label: "Tipo de dirección", type: "select", required: true, options: addressTypes.map((type) => ({ value: type, label: type })) }]} />;
}
