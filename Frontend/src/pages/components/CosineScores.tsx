type ScoredSource = {
  source: string;
  title?: string;
  page?: number | null;
  score?: number | null;
};

const scoreFormat = new Intl.NumberFormat('es-ES', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export default function CosineScores({ sources }: { sources: ScoredSource[] }) {
  const scoredSources = sources.filter(
    (source) => typeof source.score === 'number' && Number.isFinite(source.score),
  );

  return <div style={{ marginTop: '4px', fontSize: '12px', color: 'var(--text-soft)' }}>
    <strong>Score coseno:</strong>
    {scoredSources.length ? <>
      <ul style={{ margin: '4px 0' }}>
        {scoredSources.map((source, index) => <li key={index}>
          {source.title || source.source}{source.page ? `, p. ${source.page}` : ''}: {scoreFormat.format(source.score!)}
        </li>)}
      </ul>    
    </> : <span> No disponible: no hay fuentes con similitud informada.</span>}
  </div>;
}
