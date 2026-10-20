import { useEffect, useRef, useState } from 'react';
import { getSessionToken } from '../api';
import { streamSchemaUpdate } from '../utils/schemaUpdate';

type Status = {
  can_update: boolean; checksum?: string; statement_count?: number; pending?: boolean;
  last_update?: { applied_at: string; run_id: string; checksum: string } | null;
};

export default function SchemaUpdatePanel() {
  const [status, setStatus] = useState<Status>();
  const [message, setMessage] = useState('Consultando el estado de la base de datos…');
  const [percent, setPercent] = useState(0);
  const [running, setRunning] = useState(false);
  const [failed, setFailed] = useState(false);
  const busy = useRef(false);
  const refresh = async () => {
    const response = await fetch('/api/setup/database/status', {
      headers: { Authorization: `Bearer ${getSessionToken()}` }, cache: 'no-store',
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'No se pudo consultar el estado.');
    setStatus(data);
    return data as Status;
  };
  useEffect(() => {
    refresh().then(() => setMessage('')).catch(error => setMessage(error.message));
  }, []);
  const update = async () => {
    if (busy.current || !status?.checksum || !status.pending) return;
    busy.current = true;
    setRunning(true); setFailed(false); setPercent(0);
    setMessage('Preparando actualización…');
    try {
      await streamSchemaUpdate(getSessionToken(), status.checksum, event => {
        setMessage(event.message);
        if (event.percent !== undefined) setPercent(event.percent);
      });
    } catch (error) {
      setFailed(true);
      setMessage(error instanceof Error ? error.message : 'No se pudo confirmar la actualización.');
    } finally {
      try { await refresh(); } catch { /* preserve migration result; manual status refresh remains available */ }
      busy.current = false; setRunning(false);
    }
  };
  return (
    <section aria-labelledby="schema-update-title" style={{ marginTop: 24 }}>
      <h3 id="schema-update-title">Actualizar base de datos</h3>
      <p className="muted">Aplica el init.sql incluido en la versión del servidor. Si una instrucción o la validación falla, se descartan los cambios de esa ejecución.</p>
      <p className="muted">Solo modifica la base de datos. Cada versión de init.sql se aplica una sola vez; no modifica infraestructura de AWS.</p>
      {status?.can_update === false && <p className="muted">Esta operación está reservada al administrador autorizado.</p>}
      {status?.can_update && <>
        <p className="muted">{status.pending ? 'Esta versión de init.sql todavía no tiene una actualización confirmada desde este panel.' : 'La versión actual de init.sql ya se aplicó correctamente.'} {status.statement_count} instrucciones.</p>
        {status.last_update && <p className="muted">Última actualización confirmada: {new Date(status.last_update.applied_at).toLocaleString()}.</p>}
        <div className="quick-row">
          <button type="button" className="primary-btn" disabled={running || !status.checksum || !status.pending} onClick={update}>{running ? 'Actualizando…' : status.pending === false ? 'Versión ya aplicada' : 'Actualizar base de datos'}</button>
          <button type="button" className="chip-btn" disabled={running} onClick={() => { refresh().then(() => setMessage('Estado actualizado.')).catch(error => setMessage(error.message)); }}>Consultar estado</button>
        </div>
        <label className="field-label" htmlFor="schema-update-progress">Progreso: {percent}%</label>
        <progress id="schema-update-progress" max={100} value={percent} style={{ width: '100%', height: 24 }} />
      </>}
      <p role={failed ? 'alert' : 'status'} aria-live="polite" className="status-line">{message}</p>
    </section>
  );
}
