import { FormEvent, useRef, useState } from "react";
import { clearApiKey, getApiKey, setApiKey, validateApiKeyCandidate } from "../api";

export default function ConfigPage() {
  const initialApiKey = useRef<string>(getApiKey());
  const [apiKeyInput, setApiKeyInput] = useState<string>(initialApiKey.current);
  const [message, setMessage] = useState<string>(initialApiKey.current ? "API key cargada desde este navegador" : "API key no configurada");
  const [saving, setSaving] = useState(false);

  const onSave = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = apiKeyInput.trim();
    if (!trimmed) {
      clearApiKey();
      initialApiKey.current = "";
      setMessage("API key eliminada");
      return;
    }

    setSaving(true);
    setMessage("Validando la API key contra el backend...");
    try {
      await validateApiKeyCandidate(trimmed);
      setApiKey(trimmed);
      initialApiKey.current = trimmed;
      setMessage("API key valida. Guardada en este navegador.");
    } catch (error) {
      setApiKeyInput(initialApiKey.current);
      setMessage(
        error instanceof Error
          ? `La validacion fallo y se restauro la clave anterior: ${error.message}`
          : "La validacion fallo y se restauro la clave anterior."
      );
    } finally {
      setSaving(false);
    }
  };

  const onClear = () => {
    clearApiKey();
    setApiKeyInput("");
    setMessage("API key eliminada");
  };

  return (
    <div className="card single-card">
      <p className="section-label">Configuracion</p>
      <h3>Estado de los servicios</h3>
      <ul className="status-list">
        <li><strong>Frontend:</strong> React + TypeScript en `D:\MasterPontiaIA\ProyectoupiterV3\Frontend`</li>
        <li><strong>API:</strong> FastAPI detras de /api</li>
        <li><strong>Base de datos:</strong> `supply_chain` ampliada con entidades operativas de Proyecto Jupiter</li>
        <li><strong>IA principal:</strong> OpenAI por el agente `/api/agents/stockassistant/chat`</li>
        <li><strong>IA secundaria:</strong> Ollama local se muestra tambien cuando esta disponible</li>
      </ul>

      <h3 style={{ marginTop: "20px" }}>API key para endpoints IA</h3>
      <p className="muted">Se guarda solo en este navegador, se muestra oculta y se valida antes de reemplazar la anterior.</p>
      <form className="stack" onSubmit={onSave}>
        <label className="field-label" htmlFor="api-key-input">X-API-Key</label>
        <input
          id="api-key-input"
          value={apiKeyInput}
          onChange={(e) => setApiKeyInput(e.target.value)}
          placeholder="Pega aqui tu API key"
          type="password"
        />
        <div className="quick-row">
          <button className="primary-btn" disabled={saving} type="submit">{saving ? "Validando..." : "Guardar API key"}</button>
          <button className="chip-btn" type="button" onClick={onClear}>Eliminar API key</button>
        </div>
      </form>
      <p className="status-line">{message}</p>
    </div>
  );
}
