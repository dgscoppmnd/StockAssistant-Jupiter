import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';
const source = readFileSync(new URL('../src/utils/schemaUpdate.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { streamSchemaUpdate } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
class FakeXHR {
  static latest;
  headers = {}; status = 200; responseText = '';
  constructor() { FakeXHR.latest = this; }
  open(method, url) { this.url = url; }
  setRequestHeader(key, value) { this.headers[key] = value; }
  send(body) { this.body = body; }
  chunk(text) { this.responseText += text; this.onprogress(); }
}
globalThis.XMLHttpRequest = FakeXHR;
test('partial progress, session auth and 100% only after confirmed commit', async () => {
  const seen = [];
  const pending = streamSchemaUpdate('session', 'a'.repeat(64), event => seen.push(event));
  const xhr = FakeXHR.latest;
  assert.equal(xhr.headers.Authorization, 'Bearer session');
  assert.deepEqual(JSON.parse(xhr.body), { expected_checksum:'a'.repeat(64) });
  xhr.chunk('{"stage":"applying","percent":');
  assert.equal(seen.length, 0);
  xhr.chunk('25,"message":"Applying"}\n{"stage":"committing","percent":100}\n');
  assert.equal(seen.at(-1).percent, 98);
  xhr.chunk('{"stage":"complete","percent":100,"result":{"run_id":"test"}}\n');
  xhr.onload();
  await pending;
  assert.equal(seen.at(-1).percent, 100);
});
test('server validation failure is a rejected update even with HTTP 200', async () => {
  const pending = streamSchemaUpdate('session', 'hash', () => {});
  FakeXHR.latest.chunk('{"stage":"error","detail":"Los cambios se han descartado."}\n');
  FakeXHR.latest.onload();
  await assert.rejects(pending, /descartado/);
});
test('truncation and network failure never claim successful commit or rollback', async () => {
  let pending = streamSchemaUpdate('session', 'hash', () => {});
  FakeXHR.latest.chunk('{"stage":"validating","percent":90}\n');
  FakeXHR.latest.onload();
  await assert.rejects(pending, /sin confirmar/);
  pending = streamSchemaUpdate('session', 'hash', () => {});
  FakeXHR.latest.onerror();
  await assert.rejects(pending, /comprobar si los cambios se confirmaron/);
});
test('authorization and stale schema errors preserve server details', async () => {
  const pending = streamSchemaUpdate('session', 'hash', () => {});
  FakeXHR.latest.status = 409;
  FakeXHR.latest.responseText = '{"detail":"init.sql cambió"}';
  FakeXHR.latest.onload();
  await assert.rejects(pending, /init.sql cambió/);
});
