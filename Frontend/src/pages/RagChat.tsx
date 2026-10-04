import React, { useState, useRef, useEffect } from 'react';

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
}

export default function RagChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputQuery, setInputQuery] = useState('');
  const [selectedZone, setSelectedZone] = useState<string>('auto'); // Estado para la zona seleccionada
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
      const token = localStorage.getItem('token') || localStorage.getItem('access_token');
      const apiKey = localStorage.getItem('api_key') || import.meta.env.VITE_API_KEY;

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      if (apiKey) {
        headers['X-API-Key'] = apiKey;
      }

      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      
      // Petición al endpoint /api/rag/ask enviando target_zone si no es 'auto'
      const response = await fetch(`${API_URL}/api/rag/ask`, {
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
        { id: (Date.now() + 1).toString(), sender: 'assistant', text: answerText },
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

      {/* Formulario con input de texto y selector de zona */}
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

        {/* Selector de filtro Qdrant */}
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