export type ClientImportResult = { imported: number; skipped: number; total: number };
export type ClientImportProgress = {
  stage: "uploading" | "validating" | "importing" | "committing" | "complete";
  percent: number;
  processed?: number;
  total?: number;
};

// XHR permite medir la subida y recibir el progreso del servidor en la misma petición.
export function uploadClientCsv(
  file: File,
  headers: Record<string, string>,
  onProgress: (progress: ClientImportProgress) => void,
): Promise<ClientImportResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);
    let offset = 0;
    let result: ClientImportResult | undefined;
    let failure = "";
    let serverStarted = false;

    const consume = (finished = false) => {
      if (xhr.status < 200 || xhr.status >= 300) return;
      const response = xhr.responseText;
      let end: number;
      while ((end = response.indexOf("\n", offset)) >= 0 || (finished && offset < response.length)) {
        if (end < 0) end = response.length;
        const line = response.slice(offset, end).trim();
        offset = end + 1;
        if (!line) continue;
        try {
          const event = JSON.parse(line) as ClientImportProgress & { detail?: string; result?: ClientImportResult };
          serverStarted = true;
          if (event.detail) {
            failure = event.detail;
          } else if (["validating", "importing", "committing", "complete"].includes(event.stage)) {
            if (event.stage === "complete") result = event.result;
            onProgress(event);
          }
        } catch {
          failure = "No se pudo interpretar el progreso de la importación.";
        }
      }
    };

    xhr.open("POST", "/api/master-data/clients/import-csv?progress=true");
    Object.entries(headers).forEach(([name, value]) => xhr.setRequestHeader(name, value));
    xhr.setRequestHeader("Accept", "application/x-ndjson");
    xhr.upload.onprogress = (event) => {
      if (!serverStarted && event.lengthComputable) {
        onProgress({ stage: "uploading", percent: Math.min(100, Math.floor(event.loaded * 100 / event.total)) });
      }
    };
    xhr.upload.onload = () => {
      if (!serverStarted) onProgress({ stage: "validating", percent: 0 });
    };
    xhr.onprogress = () => consume();
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        let message = `No se pudo importar el CSV (HTTP ${xhr.status}).`;
        try {
          const body = JSON.parse(xhr.responseText) as { detail?: string };
          if (typeof body.detail === "string") message = body.detail;
        } catch { /* El proxy puede devolver HTML para errores de subida. */ }
        reject(new Error(message));
        return;
      }
      consume(true);
      if (failure) reject(new Error(failure));
      else if (result) resolve(result);
      else reject(new Error("La conexión terminó sin confirmar la importación. Actualiza la lista antes de reintentarlo."));
    };
    xhr.onerror = () => reject(new Error("Se perdió la conexión. No se pudo confirmar la importación; actualiza la lista antes de reintentarlo."));
    xhr.onabort = () => reject(new Error("Se interrumpió la conexión de importación."));
    onProgress({ stage: "uploading", percent: 0 });
    xhr.send(formData);
  });
}
