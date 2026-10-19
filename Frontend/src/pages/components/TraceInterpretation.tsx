import { useEffect, useState } from 'react';
import { automationRequest } from '../../api';
import TraceNoteVisuals, {type TraceMetric,type TraceChart} from './TraceNoteVisuals';

type Interpretation = {source:'ai'|'fallback'|'pending'; explanation:string; warning?:string | null;
  next_step?:string;metrics?:TraceMetric[];chart?:TraceChart | null;
  ai:{provider?:string;model?:string;used_fallback?:boolean} | null};

export default function TraceInterpretation({runId, revision, ready}: {runId:number;revision:string;ready:boolean}) {
  const [result,setResult] = useState<Interpretation | null>(null);
  const [error,setError] = useState('');
  const [loading,setLoading] = useState(false);
  const [attempt,setAttempt] = useState(0);
  useEffect(() => {
    setResult(null);setError('');
    if (!ready) return;
    let cancelled = false;
    setLoading(true);
    void automationRequest<Interpretation>(`/runs/${runId}/interpretation${attempt ? '?retry=true' : ''}`,'POST')
      .then(data => {if (!cancelled) setResult(data);})
      .catch(e => {if (!cancelled) setError(e instanceof Error ? e.message : String(e));})
      .finally(() => {if (!cancelled) setLoading(false);});
    return () => {cancelled = true;};
  },[runId,revision,ready,attempt]);
  return <aside className="trace-interpretation" aria-label="Explicación de la traza" aria-busy={loading && ready}>
    <h4>Nota explicativa de la ejecución</h4>
    <div aria-live="polite">
      {!ready ? <p>Esperando los datos de la traza…</p> : loading ? <p>Interpretando la traza con la IA disponible…</p> : null}
      {error && <><p role="alert">No se pudo obtener la explicación: {error}</p><button type="button" className="chip-btn" onClick={() => setAttempt(a=>a+1)}>Reintentar explicación</button></>}
      {result && <>
        <p className="trace-interpretation-text">{result.explanation}</p>
        <TraceNoteVisuals metrics={result.metrics ?? []} chart={result.chart} />
        {result.next_step && <p><strong>Siguiente paso:</strong> {result.next_step}</p>}
        {result.ai && <small>Interpretación con {result.ai.provider === 'ollama' ? 'Ollama' : result.ai.provider === 'openai' ? 'OpenAI' : 'IA'}{result.ai.model ? ` · ${result.ai.model}` : ''}{result.ai.used_fallback ? ' · Respaldo automático' : ''}</small>}
        {result.source === 'fallback' && <><small>Resumen calculado · IA no disponible para esta explicación.</small>{result.warning && <details><summary>Motivo</summary><p>{result.warning}</p></details>}<button type="button" className="chip-btn" onClick={() => setAttempt(a=>a+1)}>Reintentar con IA</button></>}
      </>}
    </div>
    <small>La nota ayuda a interpretar los hechos registrados. Las propuestas, aprobaciones y acciones se consultan en la traza.</small>
  </aside>;
}
