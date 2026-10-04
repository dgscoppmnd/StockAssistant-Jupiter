import React, { useState, useRef, useEffect } from 'react';
import { getApiKey, getSessionToken } from '../api';

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  citations?: { source: string; page?: number | null; score: number }[];
  provider?: string;
  ingestionWarnings?: string[];
}

export default function RagChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputQuery, setInputQuery] = useState('');
  const [selectedZone, setSelectedZone] = useState<string>('auto');
  const [isLoading, setIsLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: inputQuery.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputQuery('');
    setIsLoading(true);

    try {
      const token = getSessionToken();
      const apiKey = getApiKey();

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      if (apiKey) {
        headers['X-API-Key'] = apiKey;
      }

      
      const response = await fetch('/api/rag/ask', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          question: userMessage.text,
          top_k: 3,
          target_zone: selectedZone === 'auto' ? null : selectedZone, 
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `Error ${response.status}: ${response.statusText}`
        );
      }

      const data = await response.json();
      const answerText = data.answer || 'Sin respuesta devuelta por el servidor.';

      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), sender: 'assistant', text: answerText,
          citations: data.citations, provider: data.provider, ingestionWarnings: data.ingestion_warnings },
      ]);
    } catch (error: any) {
      console.error('Error en RAG:', error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: 'assistant',
          text: `⚠️ Error: ${error.message || 'No se pudo conectar con el servidor RAG.'}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', minHeight: '520px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid var(--border-color, #ccc)' }}>
        <span style={{ fontSize: '20px' }}>🤖</span>
        <h2 style={{ margin: 0 }}>Asistente RAG Jupiter</h2>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', marginBottom: '16px', display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '60vh' }}>
        {messages.length === 0 ? (
          <p style={{ textAlign: 'center', opacity: 0.6, margin: 'auto' }}>
            Haz una pregunta sobre la documentación técnica o inventario.
          </p>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '80%',
                padding: '10px 14px',
                borderRadius: '8px',
                background: msg.sender === 'user' ? '#4f46e5' : 'rgba(255,255,255,0.08)',
                color: msg.sender === 'user' ? '#fff' : 'inherit',
                whiteSpace: 'pre-wrap',
              }}
            >
              <strong>{msg.sender === 'user' ? 'Tú: ' : 'IA: '}</strong>
              {msg.text}
              {msg.citations && msg.citations.length > 0 && (
                <div style={{ marginTop: '8px', fontSize: '12px', opacity: 0.8 }}>
                  <strong>Fuentes:</strong>
                  <ul style={{ margin: '4px 0' }}>
                    {msg.citations.map((citation, index) => (
                      <li key={index}>{citation.source}{citation.page ? `, p. ${citation.page}` : ''}</li>
                    ))}
                  </ul>
                  {msg.provider && <span>Proveedor: {msg.provider === 'openai' ? 'OpenAI' : 'Ollama'}</span>}
                </div>
              )}
              {msg.ingestionWarnings && msg.ingestionWarnings.length > 0 && (
                <div style={{ marginTop: '8px', fontSize: '12px' }} role="status">
                  <strong>Documentos pendientes de procesar:</strong>
                  <ul>{msg.ingestionWarnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', opacity: 0.7 }}>
            <span>⏳</span>
            <span>Consultando la base de conocimiento...</span>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <form onSubmit={handleSend} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder="Escribe tu pregunta sobre inventario, ventas, etc..."
            disabled={isLoading}
            style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #ccc' }}
          />
          <button type="submit" disabled={isLoading || !inputQuery.trim()} style={{ padding: '10px 16px', cursor: 'pointer' }}>
            Enviar
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
          <label htmlFor="zone-select" style={{ opacity: 0.8 }}>Filtrar zona:</label>
          <select 
            id="zone-select"
            value={selectedZone} 
            onChange={(e) => setSelectedZone(e.target.value)}
            disabled={isLoading}
            style={{ padding: '6px', borderRadius: '4px', border: '1px solid #ccc', background: 'var(--bg-input, #fff)', color: 'inherit' }}
          >
            <option value="general">🔍 General</option>
            <option value="auto">🔍 Automático (toda la base)</option>
            <option value="inventario">📦 Inventario</option>
            <option value="ventas">💰 Ventas</option>
            <option value="logistica">🚚 Logística</option>
            <option value="analiticas">📊 Analíticas</option>
            <option value="metricas">📈 Métricas</option>
            <option value="producto">🏷️ Producto</option>
            <option value="proveedores">🤝 Proveedores</option>
          </select>
        </div>
      </form>
    </div>
  );
}
