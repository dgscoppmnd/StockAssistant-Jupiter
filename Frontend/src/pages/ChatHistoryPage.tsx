import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchChatConversations,
  fetchChatHistory,
  sendChatMessage,
} from "../api";
import type {
  ChatConversation,
  ChatMessage,
  ChatProvider,
} from "../types";


function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("es-ES", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}


export default function ChatHistoryPage() {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [prompt, setPrompt] = useState("");
  const [provider, setProvider] = useState<ChatProvider>("openai");
  const [status, setStatus] = useState("Selecciona una conversación o crea una nueva.");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.id === conversationId) ?? null,
    [conversations, conversationId]
  );

  const loadConversations = useCallback(async () => {
    try {
      const result = await fetchChatConversations();
      setConversations(result.conversations);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error desconocido";
      setStatus(`No se pudo cargar el historial: ${message}`);
    }
  }, []);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  const openConversation = async (nextConversationId: number) => {
    setIsLoadingHistory(true);
    setStatus("Cargando conversación...");

    try {
      const result = await fetchChatHistory(nextConversationId);
      setConversationId(nextConversationId);
      setMessages(result.messages);
      setStatus("Conversación cargada.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error desconocido";
      setStatus(`No se pudo cargar la conversación: ${message}`);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const startNewConversation = () => {
    setConversationId(null);
    setMessages([]);
    setPrompt("");
    setStatus("Nueva conversación preparada.");
  };

  const submitMessage = async (event: FormEvent) => {
    event.preventDefault();

    const safePrompt = prompt.trim();
    if (!safePrompt || isLoading) {
      return;
    }

    setIsLoading(true);
    setStatus("Consultando al asistente...");

    try {
      const response = await sendChatMessage({
        prompt: safePrompt,
        conversation_id: conversationId,
        provider,
        agent_key: "stockassistant",
      });

      const temporaryMessages: ChatMessage[] = [
        ...messages,
        {
          id: -Date.now(),
          role: "user",
          content: safePrompt,
          created_at: new Date().toISOString(),
        },
        {
          id: -(Date.now() + 1),
          role: "assistant",
          content: response.response,
          created_at: new Date().toISOString(),
        },
      ];

      setConversationId(response.conversation_id);
      setMessages(temporaryMessages);
      setPrompt("");

      try {
        const savedHistory = await fetchChatHistory(response.conversation_id);
        setMessages(savedHistory.messages);
      } catch {
        // La respuesta ya está visible aunque falle esta recarga puntual.
      }

      await loadConversations();
      setStatus(
        `Respuesta recibida con ${response.provider} (${response.model}).`
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error desconocido";
      setStatus(`No se pudo enviar el mensaje: ${message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-history-layout">
      <aside className="card chat-history-sidebar">
        <div className="chat-history-sidebar-header">
          <div>
            <p className="section-label">Memoria del LLM</p>
            <h3>Conversaciones</h3>
          </div>

          <button
            className="primary-btn"
            onClick={startNewConversation}
            type="button"
          >
            Nueva
          </button>
        </div>

        <div className="chat-conversation-list">
          {conversations.length === 0 && (
            <p className="muted">Todavía no hay conversaciones guardadas.</p>
          )}

          {conversations.map((conversation) => (
            <button
              className={`chat-conversation-item${
                conversation.id === conversationId ? " active" : ""
              }`}
              disabled={isLoadingHistory}
              key={conversation.id}
              onClick={() => void openConversation(conversation.id)}
              type="button"
            >
              <strong>{conversation.title || "Conversación sin título"}</strong>
              <span>
                {conversation.message_count ?? 0} mensajes
                {conversation.updated_at
                  ? ` · ${formatDate(conversation.updated_at)}`
                  : ""}
              </span>
            </button>
          ))}
        </div>
      </aside>

      <section className="card chat-history-panel">
        <header className="chat-history-panel-header">
          <div>
            <p className="section-label">Chat con memoria</p>
            <h3>
              {selectedConversation?.title || "Nueva conversación"}
            </h3>
          </div>

          <label className="chat-provider-field">
            <span>Proveedor</span>
            <select
              disabled={isLoading}
              onChange={(event) =>
                setProvider(event.target.value as ChatProvider)
              }
              value={provider}
            >
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama local</option>
            </select>
          </label>
        </header>

        <div
          aria-live="polite"
          className="chat-message-list"
        >
          {messages.length === 0 && (
            <div className="chat-empty-state">
              <h4>Empieza una conversación</h4>
              <p className="muted">
                Los mensajes quedarán guardados para que el asistente pueda
                mantener el contexto.
              </p>
            </div>
          )}

          {messages.map((message) => (
            <article
              className={`chat-message chat-message-${message.role}`}
              key={message.id}
            >
              <strong>
                {message.role === "user" ? "Tú" : "Asistente"}
              </strong>
              <p>{message.content}</p>
              <time dateTime={message.created_at}>
                {formatDate(message.created_at)}
              </time>
            </article>
          ))}
        </div>

        <form className="chat-composer" onSubmit={submitMessage}>
          <label className="field-label" htmlFor="chat-history-prompt">
            Mensaje
          </label>

          <textarea
            disabled={isLoading}
            id="chat-history-prompt"
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Escribe tu mensaje..."
            rows={4}
            value={prompt}
          />

          <div className="chat-composer-actions">
            <p className="status-line">{status}</p>

            <button
              className="primary-btn"
              disabled={isLoading || !prompt.trim()}
              type="submit"
            >
              {isLoading ? "Enviando..." : "Enviar"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}