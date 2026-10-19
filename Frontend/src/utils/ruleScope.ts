export function parseScopeIds(value:string):number[] {
  if (!value.trim()) return [];
  const parts=value.split(',').map(part=>part.trim());
  if(parts.some(part=>!/^\d+$/.test(part))) throw new Error('Indica IDs positivos separados por comas');
  const ids=parts.map(Number);
  if (ids.some(id=>!Number.isSafeInteger(id)||id<=0)) throw new Error('Indica IDs positivos separados por comas');
  const unique=[...new Set(ids)];
  if(unique.length>100) throw new Error('Selecciona como máximo 100 elementos');
  return unique;
}

export function toggleScopeId(value:string,id:number):string {
  const ids=parseScopeIds(value);
  return parseScopeIds((ids.includes(id)?ids.filter(selected=>selected!==id):[...ids,id]).join(',')).join(',');
}
