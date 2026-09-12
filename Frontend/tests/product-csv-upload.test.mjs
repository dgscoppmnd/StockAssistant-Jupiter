import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/utils/productCsvUpload.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } });
const { uploadProductCsv } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

class FakeXHR {
  static latest;
  upload = {};
  headers = {};
  status = 200;
  responseText = "";
  constructor() { FakeXHR.latest = this; }
  open(method, url) { this.method = method; this.url = url; }
  setRequestHeader(name, value) { this.headers[name] = value; }
  send(body) { this.body = body; }
  chunk(text) { this.responseText += text; this.onprogress(); }
}
globalThis.XMLHttpRequest = FakeXHR;
const file = new Blob(["CSV"], { type: "text/csv" });

test("upload progress, partial response lines, authentication and server completion", async () => {
  const seen = [];
  const pending = uploadProductCsv(file, { Authorization: "Bearer test" }, event => seen.push(event));
  const xhr = FakeXHR.latest;
  assert.equal(xhr.headers.Authorization, "Bearer test");
  assert.equal(xhr.url, "/api/products/import-csv?progress=true");
  xhr.upload.onprogress({ lengthComputable: true, loaded: 25, total: 100 });
  assert.equal(seen.at(-1).percent, 25);
  xhr.upload.onload();
  xhr.chunk('{"stage":"validating","percent":');
  assert.equal(seen.at(-1).percent, 0);
  xhr.chunk('70}\n{"stage":"importing","percent":50,"processed":1000,"total":2000}\n');
  assert.equal(seen.at(-1).processed, 1000);
  xhr.upload.onload();
  assert.equal(seen.at(-1).stage, "importing");
  xhr.chunk('{"stage":"committing","percent":100}\n');
  assert.ok(!seen.some(event => event.stage === "complete"));
  xhr.chunk('{"stage":"complete","percent":100,"result":{"imported":1500,"skipped":500,"total":2000}}\n');
  xhr.onload();
  assert.deepEqual(await pending, { imported: 1500, skipped: 500, total: 2000 });
});

test("validation errors streamed with HTTP 200 reject the import", async () => {
  const pending = uploadProductCsv(file, {}, () => {});
  const xhr = FakeXHR.latest;
  xhr.chunk('{"stage":"error","detail":"Línea 30: fecha inválida"}\n');
  xhr.onload();
  await assert.rejects(pending, /Línea 30/);
});

test("a truncated response cannot be mistaken for success", async () => {
  const pending = uploadProductCsv(file, {}, () => {});
  const xhr = FakeXHR.latest;
  xhr.chunk('{"stage":"importing","percent":100}\n');
  xhr.onload();
  await assert.rejects(pending, /sin confirmar/);
});

test("HTTP upload limit and network errors are reported", async () => {
  let pending = uploadProductCsv(file, {}, () => {});
  let xhr = FakeXHR.latest;
  xhr.status = 413;
  xhr.responseText = '{"detail":"El CSV supera el límite de 200 MB."}';
  xhr.onload();
  await assert.rejects(pending, /200 MB/);
  pending = uploadProductCsv(file, {}, () => {});
  xhr = FakeXHR.latest;
  xhr.onerror();
  await assert.rejects(pending, /perdió la conexión/);
});
