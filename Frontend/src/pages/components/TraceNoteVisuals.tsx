import { useId } from 'react';

export type TraceMetric = {label:string;value:string;unit:string};
export type TraceChart = {title:string;unit:string;points:{label:string;value:string}[]};
const number = (value:string) => Number(value).toLocaleString('es-ES',{maximumFractionDigits:4});

export default function TraceNoteVisuals({metrics,chart}: {metrics:TraceMetric[];chart?:TraceChart | null}) {
  const titleId = useId();
  const points = (chart?.points ?? []).filter(p=>p.value.trim()!=='' && Number.isFinite(Number(p.value))).slice(0,8);
  const min = Math.min(0,...points.map(p=>Number(p.value))), max = Math.max(0,...points.map(p=>Number(p.value)));
  const span = max-min || 1;
  const x = (value:number) => 160+(value-min)/span*240;
  const zero = x(0);
  return <>
    {!!metrics.length && <dl className="trace-note-metrics">{metrics.map((metric,index)=><div key={index}>
      <dt>{metric.label}</dt><dd>{number(metric.value)} <small>{metric.unit}</small></dd>
    </div>)}</dl>}
    {chart && points.length>=2 && max!==min && <figure className="trace-note-chart">
      <figcaption id={titleId}>{chart.title} · {chart.unit}</figcaption>
      <svg viewBox={`0 0 520 ${points.length*38+12}`} role="img" aria-labelledby={titleId}>
        <desc>{points.map(p=>`${p.label}: ${number(p.value)} ${chart.unit}`).join('; ')}</desc>
        <line x1={zero} y1="0" x2={zero} y2={points.length*38} stroke="currentColor" opacity=".4" />
        {points.map((point,index)=>{
          const value=Number(point.value),end=x(value);
          return <g key={index}>
            <text x="0" y={index*38+23} fill="currentColor" fontSize="13">{point.label}</text>
            <rect x={Math.min(zero,end)} y={index*38+6} width={Math.abs(end-zero)} height="24" rx="3" fill="var(--cyan)" />
            <text x="414" y={index*38+23} fill="currentColor" fontSize="13">{number(point.value)}</text>
          </g>;
        })}
      </svg>
      <details><summary>Ver valores de la gráfica</summary><table><thead><tr><th>Indicador</th><th>Valor ({chart.unit})</th></tr></thead>
        <tbody>{points.map((p,index)=><tr key={index}><td>{p.label}</td><td>{number(p.value)}</td></tr>)}</tbody></table></details>
    </figure>}
  </>;
}
