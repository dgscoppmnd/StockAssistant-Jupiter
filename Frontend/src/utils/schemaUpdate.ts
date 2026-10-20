export type SchemaProgress = {
  stage: string; percent?: number; message: string; run_id?: string;
  detail?: string; result?: { checksum: string; run_id: string; statement_count: number };
};

export function streamSchemaUpdate(token: string, checksum: string, onProgress: (event: SchemaProgress) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let offset = 0;
    let complete = false;
    let failure = '';
    const consume = (finished = false) => {
      if (xhr.status < 200 || xhr.status >= 300) return;
      let end: number;
      while ((end = xhr.responseText.indexOf('\n', offset)) >= 0 || (finished && offset < xhr.responseText.length)) {
        if (end < 0) end = xhr.responseText.length;
        const line = xhr.responseText.slice(offset, end).trim();
        offset = end + 1;
        if (!line) continue;
        try {
          const event = JSON.parse(line) as SchemaProgress;
          if (event.stage === 'error') failure = event.detail || event.message;
          if (event.stage === 'complete' && event.result) complete = true;
          // Only a confirmed commit may display 100%.
          if (event.percent !== undefined) event.percent = complete ? 100 : Math.min(event.percent, 98);
          onProgress(event);
        } catch {
          failure = 'No se pudo interpretar la respuesta. Consulta el estado antes de reintentar.';
        }
      }
    };
    xhr.open('POST', '/api/setup/database/update');
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('Accept', 'application/x-ndjson');
    xhr.onprogress = () => consume();
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        let detail = `No se pudo iniciar la actualización (HTTP ${xhr.status}).`;
        try { detail = JSON.parse(xhr.responseText).detail || detail; } catch { /* keep HTTP detail */ }
        reject(new Error(detail));
        return;
      }
      consume(true);
      if (failure) reject(new Error(failure));
      else if (complete) resolve();
      else reject(new Error('La conexión terminó sin confirmar el resultado. Consulta el estado antes de reintentar.'));
    };
    xhr.onerror = xhr.onabort = () => reject(new Error('Se perdió la conexión. Consulta el estado para comprobar si los cambios se confirmaron.'));
    xhr.send(JSON.stringify({ expected_checksum: checksum }));
  });
}
