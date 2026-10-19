import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { describeObservedAi, type ObservedAiRun } from '../../utils/observedAi';

export default function ObservedAi({run}: {run: ObservedAiRun}) {
  const info = describeObservedAi(run);
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{top: number; left: number} | null>(null);
  useEffect(() => {
    if (!position) return;
    const closeOutside = (event: PointerEvent) => {
      if (!popup.current?.contains(event.target as Node) && !button.current?.contains(event.target as Node)) setPosition(null);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {setPosition(null); button.current?.focus();}
    };
    const close = () => setPosition(null);
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', closeOnEscape);
    window.addEventListener('resize', close);
    window.addEventListener('scroll', close, true);
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('keydown', closeOnEscape);
      window.removeEventListener('resize', close);
      window.removeEventListener('scroll', close, true);
    };
  }, [position]);
  return <>
    <button ref={button} type="button" className={`observed-ai observed-ai--${info.tone}`}
      aria-label={`${info.title}. Ver explicación`} aria-expanded={!!position} aria-controls={position ? id : undefined}
      onClick={() => {
        if (position) {setPosition(null); return;}
        const rect = button.current!.getBoundingClientRect();
        setPosition({left: Math.max(12, Math.min(rect.left, window.innerWidth - 348)), top: Math.max(12, Math.min(rect.bottom + 8, window.innerHeight - 300))});
      }}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        {info.tone === 'success' ? <><circle cx="12" cy="12" r="9" /><path d="m7.5 12 3 3 6-6" /></>
          : info.tone === 'critical' ? <><path d="m12 3 10 18H2Z" /><path d="M12 9v5m0 3v1" /></>
          : info.tone === 'warning' ? <><circle cx="12" cy="12" r="9" /><path d="M12 7v7m0 3v1" /></>
          : run.status === 'running' ? <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>
          : <><circle cx="12" cy="12" r="9" /><path d="M8 12h8" /></>}
      </svg>
      {info.provider && <img className="observed-ai-logo" src={`/icons/${info.provider}.svg`} alt={info.providerName!} />}
      <span>{info.providerName ?? (info.tone === 'critical' ? 'Error' : info.tone === 'warning' ? 'Revisar' : run.status === 'running' ? 'En curso' : 'Sin IA')}</span>
    </button>
    {position && createPortal(<div ref={popup} id={id} role="region" aria-label={info.title}
      className="observed-ai-popup" style={{left: position.left, top: position.top, maxHeight: `calc(100dvh - ${position.top + 12}px)`}}>
      <strong className={`observed-ai--${info.tone}`}>{info.title}</strong>
      <p>{info.explanation}</p>
      {info.model && <p><strong>Modelo:</strong> {info.model}</p>}
      {info.reason && <p className="observed-ai-cause"><strong>Causa registrada:</strong> {info.reason}</p>}
    </div>, document.body)}
  </>;
}
