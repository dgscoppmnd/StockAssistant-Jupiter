import { useRef, useState, type FormEvent } from "react";
import { salesAction } from "../../api";
import type { SalesKind } from "../../types";
import SalesModal from "./SalesModal";

export default function SalesActionModal({ kind, id, action, onClose, onSaved }: {
  kind: SalesKind; id: number; action: "delete" | "cancel" | "issue" | "void";
  onClose: () => void; onSaved: (deleted: boolean) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const key = useRef({ fingerprint: "", value: "" });
  const busy = useRef(false);
  const labels = { delete: "Eliminar borrador", cancel: "Cancelar pendientes", issue: "Emitir factura", void: "Anular con rectificativa" };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy.current) return;
    const data = action === "void" || action === "cancel" ? { reason } : {};
    const fingerprint = JSON.stringify(data);
    if (key.current.fingerprint !== fingerprint) key.current = { fingerprint, value: crypto.randomUUID() };
    busy.current = true; setSaving(true); setError("");
    try { const result = await salesAction(kind,id,action,{ ...data, operation_key: key.current.value }); onSaved(Boolean(result.deleted)); }
    catch (err) { setError(String(err)); }
    finally { busy.current = false; setSaving(false); }
  };
  return <SalesModal title={labels[action]} saving={saving} onClose={onClose}>
    {error && <p className="error-line" role="alert">{error}</p>}
    <p>{action === "cancel" ? "Se liberarán reservas pendientes. La mercancía despachada solo vuelve al stock mediante una devolución." :
      action === "void" ? "Se conservará la factura y se creará una rectificativa vinculada. No se modificará inventario." :
      action === "delete" ? "Solo se eliminará este borrador sin operaciones asociadas." : "La factura conservará sus datos históricos. Esta acción no modifica stock."}</p>
    <form className="stack" onSubmit={event => void submit(event)}>
      {(action === "void" || action === "cancel") && <label>Motivo<textarea required minLength={3} maxLength={500} disabled={saving} value={reason} onChange={e => setReason(e.target.value)} /></label>}
      <div className="actions-row"><button className="primary-btn" type="submit" disabled={saving}>{saving ? "Procesando…" : labels[action]}</button>
        <button className="chip-btn" type="button" disabled={saving} onClick={onClose}>Volver</button></div>
    </form>
  </SalesModal>;
}
