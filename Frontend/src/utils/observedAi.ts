export type ObservedAiRun = {
  status: string;
  result: Record<string, unknown> | null;
  error_message: string | null;
  config_snapshot?: {allow_unmetered_paid_ai?: boolean} | null;
};

export function describeObservedAi(run: ObservedAiRun) {
  const ai = run.result?.ai as {provider?: string; model?: string; used_fallback?: boolean} | null;
  const provider = ai?.provider === 'ollama' || ai?.provider === 'openai' ? ai.provider : null;
  const providerName = provider === 'ollama' ? 'Ollama' : provider === 'openai' ? 'OpenAI' : null;
  const reason = run.error_message || String(run.result?.degraded_reason ?? '');
  const failed = run.status === 'failed' || run.status === 'degraded' || Boolean(run.result?.degraded);
  let tone: 'critical' | 'warning' | 'success' | 'neutral' = 'neutral';
  let title = 'Sin llamada al modelo';
  let explanation = 'No consta una respuesta de IA en esta ejecución. Puede no haber entidades que requieran análisis o tratarse de un informe sin modelo.';
  if (run.status === 'running') {
    title = 'Análisis en curso';
    explanation = 'La ejecución todavía no ha terminado. El proveedor y el resultado se mostrarán cuando estén disponibles.';
  } else if (failed || reason) {
    tone = run.status === 'failed' ? 'critical' : 'warning';
    title = 'Análisis no completado';
    explanation = 'Consulta la causa registrada y la trazabilidad de esta ejecución para conocer el paso que no pudo completarse.';
    if (/Cannot connect to (Ollama|OpenAI)/i.test(reason)) {
      tone = 'critical';
      const unavailable = /Cannot connect to Ollama/i.test(reason) ? 'Ollama' : 'OpenAI';
      title = `Sin conexión con ${unavailable}`;
      explanation = `El servidor no pudo conectarse con ${unavailable}; la petición pudo ser rechazada, interrumpirse o agotar el tiempo de espera.`;
      if (unavailable === 'Ollama' && run.config_snapshot?.allow_unmetered_paid_ai === false) {
        explanation += ' Esta ejecución tenía desautorizado el uso de IA de pago, por lo que no intentó cambiar a OpenAI. Para permitirlo, edita la regla y activa «Autorizar IA cuyo proveedor no facilita coste».';
      } else if (unavailable === 'Ollama') {
        explanation += ' No consta una respuesta de OpenAI. Revisa la política del proveedor y la traza antes de atribuir la causa a su configuración.';
      }
    } else if (/OpenAI is not configured/i.test(reason)) {
      title = 'OpenAI sin configurar';
      explanation = 'El servidor no tiene una clave de OpenAI configurada para esta llamada.';
    } else if (/model is not available/i.test(reason)) {
      title = 'Modelo no disponible';
      explanation = 'Ollama no encontró el modelo solicitado. Revisa que esté instalado y que su nombre coincida con la configuración.';
    } else if (/request rejected|server error|temporarily unavailable/i.test(reason)) {
      title = 'Proveedor no disponible o petición rechazada';
      explanation = 'El proveedor devolvió un error. Revisa su disponibilidad, las credenciales y los límites en la trazabilidad.';
    } else if (/validation error|contrato|JSON|json|Sin decisión final/i.test(reason)) {
      title = 'Respuesta de IA no válida';
      explanation = 'La respuesta no cumplió el formato o las restricciones de la regla y no pudo utilizarse para decidir acciones.';
    } else if (/deadline|plazo|temporal/i.test(reason)) {
      title = 'Tiempo de análisis agotado';
      explanation = 'El análisis no terminó dentro del plazo de esta ejecución.';
    } else if (/No hay llamadas al modelo autorizadas/i.test(reason)) {
      title = 'Llamadas al modelo deshabilitadas';
      explanation = 'La regla tiene un límite de cero llamadas al modelo. Aumenta ese límite para permitir el análisis con IA.';
    }
    if (run.status === 'degraded') explanation += ' Se conserva el análisis determinista; la decisión con IA no se completó.';
  } else if (run.status === 'completed') {
    tone = 'success';
    title = providerName ? `Análisis completado con ${providerName}` : 'Ejecución completada sin IA';
    explanation = providerName
      ? 'La IA revisó los datos de inventario y comparó las opciones de la regla para recomendar qué hacer. También podía recomendar mantener el stock como estaba o indicar que necesitaba más datos para recomendar cambios. Solo se aceptaron recomendaciones para los productos y almacenes incluidos en la regla y las acciones que esta permite. En el detalle de la ejecución puedes ver qué recomendó y por qué.'
      : 'La ejecución terminó sin una decisión de IA registrada: puede ser un informe determinista o no haber entidades que analizar.';
  }
  if (ai?.used_fallback === true) explanation += ` Se utilizó ${providerName ?? 'un proveedor alternativo'} como respaldo automático.`;
  return {tone, title, explanation, reason, provider, providerName, model: ai?.model};
}
