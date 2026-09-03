import { FormEvent, useState } from "react";
import { analyzeWithKitiaAgent } from "../api";
import type { AgentChatResponse } from "../types";

const quickPrompts = ["hola", "resume este texto", "analiza este producto"]; 

function getProviderLabel(provider?: string): string {
  if (provider === "openai") {
    return "OpenAI";
  }
  if (provider === "ollama") {
    return "Ollama local";
  }
  return provider || "desconocido";
}

function normalizeAiText(payload: AgentChatResponse): string {
  const sections: string[] = [];
  const aiMeta = payload.meta?.ai;
  const mode = typeof aiMeta?.mode === "string" ? aiMeta.mode : undefined;
  const preferredProvider = typeof aiMeta?.preferred_provider === "string" ? aiMeta.preferred_provider : undefined;
  const selectedProvider = payload.meta?.selected_provider ?? payload.provider ?? preferredProvider;

  if (mode || selectedProvider) {
    sections.push(
      [
        "[estado]",
        `Modo configurado: ${mode ?? "desconocido"}`,
        `Proveedor principal: ${getProviderLabel(selectedProvider)}`,
      ].join("\n")
    );
  }

  const primary = payload.responses?.primary;
  if (primary?.response) {
    sections.push(
      [
        `[respuesta principal: ${getProviderLabel(primary.provider)}]`,
        `Modelo: ${primary.model ?? "desconocido"}`,
        `Fallback usado: ${primary.used_fallback ? "si" : "no"}`,
        "",
        primary.response,
      ].join("\n")
    );
  } else if (payload.response) {
    sections.push(
      [
        `[respuesta principal: ${getProviderLabel(payload.provider)}]`,
        `Modelo: ${payload.model ?? "desconocido"}`,
        `Fallback usado: ${payload.used_fallback ? "si" : "no"}`,
        "",
        payload.response,
      ].join("\n")
    );
  }

  const secondary = payload.responses?.secondary;
  if (secondary?.response) {
    sections.push(
      [
        `[respuesta adicional: ${getProviderLabel(secondary.provider)}]`,
        `Modelo: ${secondary.model ?? "desconocido"}`,
        "",
        secondary.response,
      ].join("\n")
    );
  }

  if (payload.tool_results && Object.keys(payload.tool_results).length > 0) {
    sections.push(`[tools]\n${JSON.stringify(payload.tool_results, null, 2)}`);
  }

  return sections.filter(Boolean).join("\n\n").trim() || "Sin respuesta del modelo.";
}

export default function KitiaPage() {
  const [prompt, setPrompt] = useState("hola");
  const [status, setStatus] = useState("Listo para consultar");
  const [isLoading, setIsLoading] = useState(false);
  const [output, setOutput] = useState("Aqui aparecera la respuesta del modelo.");
  const [useWeb, setUseWeb] = useState(true);
  const [useTools, setUseTools] = useState(true);
  const [provider, setProvider] = useState<"openai" | "ollama">("openai");
  const [sources, setSources] = useState<Array<{ title: string; url: string }>>([]);

  const runPrompt = async (nextPrompt: string) => {
    const safePrompt = nextPrompt.trim();
    if (!safePrompt) {
      setStatus("Debes escribir un prompt valido.");
      return;
    }

    setIsLoading(true);
    setStatus("Consultando a Proyecto Jupiter con agente en /api/agents/kitia/chat ...");
    setOutput("Cargando respuesta...");
    setSources([]);

    try {
      const response: AgentChatResponse = await analyzeWithKitiaAgent({
        prompt: safePrompt,
        provider,
        use_web: useWeb,
        use_tools: useTools,
        max_web_results: 5,
        max_tool_results: 10
      });
      setOutput(normalizeAiText(response));
      const nextSources = (response.web_results ?? [])
        .filter((item) => typeof item.url === "string" && item.url.length > 0)
        .map((item) => ({ title: item.title || item.url, url: item.url }));
      setSources(nextSources);
      setStatus(`Respuesta recibida correctamente. Proveedor: ${response.provider ?? "desconocido"}${response.used_fallback ? " con respaldo" : ""}.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error desconocido";
      setOutput(message);
      const normalized = message.toLowerCase();
      if (normalized.includes("401") || normalized.includes("missing api key")) {
        setStatus("Fallo la consulta: falta API key. Configurala en la seccion Configuracion.");
      } else if (normalized.includes("403") || normalized.includes("invalid api key")) {
        setStatus("Fallo la consulta: API key invalida. Revisa la key en Configuracion.");
      } else {
        setStatus("Fallo la consulta.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await runPrompt(prompt);
  };

  return (
    <div className="grid two-columns">
      <article className="card">
        <p className="section-label">Interacción con Proyecto Jupiter</p>
        <h3>Conector de IA</h3>
        <p className="muted">Elige el proveedor principal. Si el otro está disponible, su respuesta también aparecerá en la salida.</p>

        <form className="stack" onSubmit={onSubmit}>
          <label className="field-label" htmlFor="prompt-input">Prompt</label>
          <input
            id="prompt-input"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Escribe la pregunta que quieras enviar"
            required
          />

          <label className="field-label" htmlFor="provider-select">Proveedor principal</label>
          <select
            id="provider-select"
            onChange={(e) => setProvider(e.target.value as "openai" | "ollama")}
            value={provider}
          >
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama local</option>
          </select>

          <label className="field-label" htmlFor="toggle-web">
            <input
              checked={useWeb}
              id="toggle-web"
              onChange={(e) => setUseWeb(e.target.checked)}
              style={{ marginRight: "8px" }}
              type="checkbox"
            />
            Buscar en web
          </label>

          <label className="field-label" htmlFor="toggle-tools">
            <input
              checked={useTools}
              id="toggle-tools"
              onChange={(e) => setUseTools(e.target.checked)}
              style={{ marginRight: "8px" }}
              type="checkbox"
            />
            Usar tools de productos y contexto operativo
          </label>

          <button className="primary-btn" disabled={isLoading} type="submit">
            {isLoading ? "Consultando..." : "Consultar a Proyecto Jupiter"}
          </button>
        </form>

        <div className="quick-row">
          {quickPrompts.map((item) => (
            <button
              className="chip-btn"
              disabled={isLoading}
              key={item}
              onClick={() => {
                setPrompt(item);
                void runPrompt(item);
              }}
              type="button"
            >
              {item}
            </button>
          ))}
        </div>

        <p className="status-line">{status}</p>
      </article>

      <article className="card">
        <p className="section-label">Respuesta</p>
        <h3>Salida de proveedores IA</h3>
        <pre>{output}</pre>
        <p className="muted" style={{ marginTop: "12px" }}>
          El backend indica qué proveedor ejecutó la respuesta principal y añade la salida de Ollama local cuando está disponible.
        </p>
        {sources.length > 0 && (
          <div className="stack" style={{ marginTop: "12px" }}>
            <p className="section-label">Fuentes web</p>
            <ul>
              {sources.map((source) => (
                <li key={source.url}>
                  <a href={source.url} rel="noreferrer" target="_blank">
                    {source.title}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </article>
    </div>
  );
}
