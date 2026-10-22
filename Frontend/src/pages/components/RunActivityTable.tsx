import { useEffect, useState } from 'react';
import ObservedAi from './ObservedAi';
import { describeObservedAi, type ObservedAiRun } from '../../utils/observedAi';

type ActivityRun = ObservedAiRun & {
  id: number;
  rule_name: string;
  rule_version: number;
  started_at: string;
  latency_ms: number | null;
};
type SortColumn = 'id' | 'rule' | 'status' | 'started_at' | 'latency_ms' | 'ai';
const columns: {key: SortColumn; label: string}[] = [
  {key: 'id', label: 'Ejecución'}, {key: 'rule', label: 'Regla'},
  {key: 'status', label: 'Estado'}, {key: 'started_at', label: 'Inicio'},
  {key: 'latency_ms', label: 'Duración'}, {key: 'ai', label: 'IA observada'},
];
const collator = new Intl.Collator('es', {numeric: true, sensitivity: 'base'});
const aiLabel = (run: ActivityRun) => {
  const info = describeObservedAi(run);
  return info.providerName ?? (info.tone === 'critical' ? 'Error' : info.tone === 'warning' ? 'Revisar' : run.status === 'running' ? 'En curso' : 'Sin IA');
};
const sortValue = (run: ActivityRun, column: SortColumn): string | number | null => {
  switch (column) {
    case 'rule': return `${run.rule_name} · v${run.rule_version}`;
    case 'ai': return aiLabel(run);
    case 'started_at': return new Date(run.started_at).getTime();
    default: return run[column];
  }
};

export default function RunActivityTable({runs, onSelect, filterKey}: {
  runs: ActivityRun[];
  onSelect: (id: number) => void;
  filterKey: string;
}) {
  const [sort, setSort] = useState<{column: SortColumn; descending: boolean}>({column: 'started_at', descending: true});
  const [page, setPage] = useState(1), [pageSize, setPageSize] = useState(10);
  const pageCount = Math.max(1, Math.ceil(runs.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  useEffect(() => {setPage(1);}, [filterKey]);
  useEffect(() => {setPage(current => Math.min(current, pageCount));}, [pageCount]);
  const sortedRuns = [...runs].sort((a, b) => {
    const left = sortValue(a, sort.column), right = sortValue(b, sort.column);
    // Missing durations stay at the end in either direction.
    if (left === null || right === null) return left === right ? b.id - a.id : left === null ? 1 : -1;
    const comparison = typeof left === 'number' && typeof right === 'number' ? left - right : collator.compare(String(left), String(right));
    return (sort.descending ? -comparison : comparison) || b.id - a.id;
  });
  const start = (currentPage - 1) * pageSize;
  return <>
    <div className="agent-table-scroll"><table aria-label="Actividad por ejecución">
      <thead><tr>{columns.map(({key, label}) => <th key={key} scope="col" aria-sort={sort.column === key ? (sort.descending ? 'descending' : 'ascending') : 'none'}>
        <button type="button" className="agent-sort-button" onClick={() => {
          setSort(current => ({column: key, descending: current.column === key ? !current.descending : false}));
          setPage(1);
        }}>{label} <span aria-hidden="true">{sort.column === key ? (sort.descending ? '↓' : '↑') : '↕'}</span></button>
      </th>)}</tr></thead>
      <tbody>{sortedRuns.slice(start, start + pageSize).map(run => <tr key={run.id}>
        <td><button type="button" className="chip-btn" onClick={() => onSelect(run.id)}>#{run.id} · trazabilidad</button></td>
        <td>{run.rule_name} · v{run.rule_version}</td>
        <td>{run.status}{run.error_message && <p>{run.error_message}</p>}</td>
        <td>{new Date(run.started_at).toLocaleString()}</td>
        <td>{run.latency_ms ?? 'No disponible'} ms</td>
        <td><ObservedAi run={run} /></td>
      </tr>)}{!runs.length && <tr><td colSpan={columns.length}>No hay ejecuciones para estos filtros.</td></tr>}</tbody>
    </table></div>
    <div className="agent-run-pagination">
      <label>Ejecuciones por página<select value={pageSize} onChange={event => {setPageSize(Number(event.target.value));setPage(1);}}>
        {[10,25,50].map(size => <option key={size} value={size}>{size}</option>)}
      </select></label>
      <span role="status">{runs.length ? start + 1 : 0} - {Math.min(start + pageSize, runs.length)} de {runs.length} ejecuciones</span>
      <nav aria-label="Paginación de actividad por ejecución">
        <button type="button" className="chip-btn" disabled={currentPage === 1} onClick={() => setPage(1)}>Primera</button>
        <button type="button" className="chip-btn" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Anterior</button>
        <span>Página {currentPage} de {pageCount}</span>
        <button type="button" className="chip-btn" disabled={currentPage === pageCount} onClick={() => setPage(currentPage + 1)}>Siguiente</button>
        <button type="button" className="chip-btn" disabled={currentPage === pageCount} onClick={() => setPage(pageCount)}>Última</button>
      </nav>
    </div>
  </>;
}
