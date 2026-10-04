import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/utils/clientCsvUpload.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } });
const { uploadClientCsv } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

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

test("client upload reports progress and resolves only after server completion", async () => {
  const seen = [];
  const pending = uploadClientCsv(file, { Authorization: "Bearer test" }, event => seen.push(event));
  const xhr = FakeXHR.latest;
  assert.equal(xhr.url, "/api/master-data/clients/import-csv?progress=true");
  assert.equal(xhr.headers.Authorization, "Bearer test");
  xhr.upload.onprogress({ lengthComputable: true, loaded: 50, total: 100 });
  assert.equal(seen.at(-1).percent, 50);
  xhr.chunk('{"stage":"importing","percent":100,"processed":2,"total":2}\n');
  xhr.chunk('{"stage":"complete","percent":100,"result":{"imported":2,"skipped":0,"total":2}}\n');
  xhr.onload();
  assert.deepEqual(await pending, { imported: 2, skipped: 0, total: 2 });
});

test("client validation errors reject the upload", async () => {
  const pending = uploadClientCsv(file, {}, () => {});
  const xhr = FakeXHR.latest;
  xhr.chunk('{"stage":"error","detail":"Tipo de cliente inexistente"}\n');
  xhr.onload();
  await assert.rejects(pending, /inexistente/);
});
