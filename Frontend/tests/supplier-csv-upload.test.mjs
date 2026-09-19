import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/utils/supplierCsvUpload.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } });
const { uploadSupplierCsv } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

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

test("supplier upload uses its endpoint and waits for confirmed completion", async () => {
  const seen = [];
  const pending = uploadSupplierCsv(file, { Authorization: "Bearer test" }, event => seen.push(event));
  const xhr = FakeXHR.latest;
  assert.equal(xhr.url, "/api/master-data/suppliers/import-csv?progress=true");
  assert.equal(xhr.headers.Authorization, "Bearer test");
  xhr.chunk('{"stage":"importing","percent":100,"processed":2,"total":2}\n');
  xhr.chunk('{"stage":"complete","percent":100,"result":{"imported":2,"skipped":0,"total":2}}\n');
  xhr.onload();
  assert.deepEqual(await pending, { imported: 2, skipped: 0, total: 2 });
  assert.equal(seen.at(-1).stage, "complete");
});

test("supplier validation errors reject the upload", async () => {
  const pending = uploadSupplierCsv(file, {}, () => {});
  const xhr = FakeXHR.latest;
  xhr.chunk('{"stage":"error","detail":"supplier_code repetido"}\n');
  xhr.onload();
  await assert.rejects(pending, /repetido/);
});
