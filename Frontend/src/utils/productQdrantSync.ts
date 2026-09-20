export type ProductQdrantSyncResult = { indexed: number; total: number };

export type ProductQdrantSyncProgress = {
  stage: "indexing" | "complete";
  percent: number;
  processed: number;
  total: number;
};

export function runProductQdrantSync(
  headers: Record<string, string>,
  onProgress: (progress: ProductQdrantSyncProgress) => void,
): Promise<ProductQdrantSyncResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let offset = 0;
    let result: ProductQdrantSyncResult | undefined;
    let failure = "";

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
          const event = JSON.parse(line) as ProductQdrantSyncProgress & {
            detail?: string;
            result?: ProductQdrantSyncResult;
          };
          if (event.detail) failure = event.detail;
          else if (event.stage === "indexing" || event.stage === "complete") {
            if (event.stage === "complete") result = event.result;
            onProgress(event);
          }
        } catch {
          failure = "No se pudo interpretar el progreso de Qdrant.";
        }
      }
    };

    xhr.open("POST", "/api/products/sync-qdrant");
    Object.entries(headers).forEach(([name, value]) => xhr.setRequestHeader(name, value));
    xhr.setRequestHeader("Accept", "application/x-ndjson");
    xhr.onprogress = () => consume();
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(`No se pudo sincronizar Qdrant (HTTP ${xhr.status}).`));
        return;
      }
      consume(true);
      if (failure) reject(new Error(failure));
      else if (result) resolve(result);
      else reject(new Error("La conexión terminó sin confirmar la sincronización de Qdrant."));
    };
    xhr.onerror = () => reject(new Error("Se perdió la conexión durante la sincronización de Qdrant."));
    xhr.onabort = () => reject(new Error("Se interrumpió la sincronización de Qdrant."));
    xhr.send();
  });
}
