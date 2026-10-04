import { FormEvent, useEffect, useRef, useState } from "react";
import { askCustomerSupport } from "../../api";
import type { CustomerSupportAnswer, ProductOption, SupportTurn } from "../../types";
import ProductCombobox from "./ProductCombobox";
import SectionIcon from "./SectionIcon";

type ChatMessage = SupportTurn & { result?: CustomerSupportAnswer; failed?: boolean };

export default function CustomerSupportChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [product, setProduct] = useState<ProductOption | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [messages, pending]);

  const send = async (event: FormEvent) => {
    event.preventDefault();
    const text = question.trim();
    if (pending || text.length < 2) return;
    const history = messages.filter((message) => !message.failed).slice(-12)
      .map(({ role, content }) => ({ role, content: content.slice(0, 4000) }));
    setMessages((current) => [...current, { role: "user", content: text }]);
    setQuestion(""); setPending(true);
    try {
      const result = await askCustomerSupport(text, product?.pk_product, history);
      setMessages((current) => [...current, { role: "assistant", content: result.answer, result }]);
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", failed: true,
        content: error instanceof Error ? error.message : "No se pudo consultar la base de conocimiento." }]);
      setQuestion(text);
    } finally { setPending(false); }
  };

  return <article className="card">
    <p className="section-label">Atención al cliente · RAG</p>
    <h3><SectionIcon kind="assistant" />Asistente con fuentes vigentes</h3>
    <p className="muted">Consulta los documentos procesados de Base de conocimiento. Puedes añadir un producto para consultar su stock actual.</p>
    <label>Producto opcional</label>
    <ProductCombobox selectedProduct={product} selectedId={product?.pk_product ?? 0} disabled={pending}
      onSelect={(next) => { setProduct(next); setMessages([]); }} />
    {product && <button className="chip-btn" disabled={pending} type="button" onClick={() => { setProduct(null); setMessages([]); }}>Quitar producto</button>}
    <div className="support-chat-messages" role="log" aria-label="Conversación con atención al cliente" aria-live="polite">
      {!messages.length && <p className="muted">Pregunta por una política, un procedimiento o el contenido de tus documentos.</p>}
      {messages.map((message, index) => <div key={index} className={`support-chat-message ${message.role}${message.failed ? " error-line" : ""}`}>
        <strong>{message.role === "user" ? "Tú" : "Asistente"}</strong>
        <p style={{ whiteSpace: "pre-wrap" }}>{message.content}</p>
        {!!message.result?.sources.length && <details><summary>Fuentes consultadas ({message.result.sources.length})</summary>
          {message.result.sources.map((source, sourceIndex) => <div className="agent-result" key={sourceIndex}>
            <strong>{source.citation ? `[${source.citation}] ` : ""}{source.title}{source.page ? ` · Página ${source.page}` : ""}</strong>
            {source.excerpt && <p>{source.excerpt}</p>}
            {source.expires_at && <small>Vigencia: {new Date(source.expires_at).toLocaleString("es-ES")}</small>}
          </div>)}
        </details>}
        {!!message.result?.stock.length && <div className="agent-result"><strong>Stock confirmado</strong>
          {message.result.stock.map((stock, stockIndex) => <p key={stockIndex}>{stock.warehouse}: {stock.available_qty} {stock.unit}</p>)}
        </div>}
        {message.result?.ai && <small>Proveedor: {message.result.ai.provider === "openai" ? "OpenAI" : "Ollama"}{message.result.ai.used_fallback ? " · Respaldo automático" : ""}</small>}
        {!!message.result?.ingestion_warnings?.length && <details><summary>Documentos pendientes o incidencias</summary>
          <ul>{message.result.ingestion_warnings.map((warning, warningIndex) => <li key={warningIndex}>{warning}</li>)}</ul>
        </details>}
      </div>)}
      {pending && <p role="status">Consultando documentos y preparando la respuesta…</p>}
      <div ref={end} />
    </div>
    <form className="stack" onSubmit={send}>
      <label htmlFor="support-question">Pregunta del cliente</label>
      <textarea id="support-question" required minLength={2} maxLength={2000} disabled={pending}
        placeholder="Escribe tu pregunta o continúa la conversación" value={question}
        onChange={(event) => setQuestion(event.target.value)} rows={3} />
      <div className="actions-row">
        <button className="primary-btn" disabled={pending || question.trim().length < 2} type="submit">{pending ? "Consultando…" : "Enviar"}</button>
        <button className="chip-btn" disabled={pending || !messages.length} type="button" onClick={() => setMessages([])}>Nueva conversación</button>
      </div>
    </form>
  </article>;
}
