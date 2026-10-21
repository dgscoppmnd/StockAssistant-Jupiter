import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {test} from 'node:test';
import ts from 'typescript';

// Compile the real API client; isolate browser storage and HTTP per test.
const source = readFileSync(new URL('../src/api.ts', import.meta.url), 'utf8')
  .replaceAll('import.meta.env', '({})');
const compiled = ts.transpileModule(source, {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText;

function harness() {
  const storage = new Map();
  const calls = [];
  const responses = [];
  const module = {exports: {}};
  const context = {
    module, exports: module.exports, require: () => ({}), Headers, FormData,
    window: {localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    }},
    fetch: async (url, options) => {
      calls.push({url, ...options});
      const response = await responses.shift();
      assert.ok(response, 'Unexpected HTTP request');
      return response;
    },
  };
  vm.runInNewContext(compiled, context);
  const respond = (status, body) => responses.push({
    status, ok: status >= 200 && status < 300, text: async () => JSON.stringify(body),
  });
  return {api: module.exports, calls, responses, respond};
}

test('activation permission rejection preserves session for subsequent requests', async () => {
  const {api, calls, respond} = harness();
  api.setSessionToken('test-session');
  respond(403, {detail: 'No tienes permiso de automatización: activate'});
  await assert.rejects(api.updateAutomationRule(1, true), /activate/);
  assert.equal(api.getSessionToken(), 'test-session');
  respond(200, []);
  await api.fetchAutomationRules();
  assert.equal(calls[0].method, 'PUT');
  assert.deepEqual(JSON.parse(calls[0].body), {is_active: true});
  for (const call of calls) {
    assert.equal(call.headers.get('Authorization'), 'Bearer test-session');
    assert.equal(call.headers.has('X-API-Key'), false);
  }
});

test('permission rejections preserve sessions on automation and sales routes', async () => {
  const {api, respond} = harness();
  api.setSessionToken('test-session');
  for (const request of [
    () => api.automationRequest('/control'),
    () => api.fetchSalesPermissions(),
    () => api.fetchMasterRecords('clients'),
  ]) {
    respond(403, {detail: 'Forbidden'});
    await assert.rejects(request(), /Forbidden/);
    assert.equal(api.getSessionToken(), 'test-session');
  }
});

test('401 invalidates the rejected session', async () => {
  const {api, respond} = harness();
  api.setSessionToken('expired-session');
  respond(401, {detail: 'Session expired'});
  await assert.rejects(api.fetchAutomationRules(), /Session expired/);
  assert.equal(api.getSessionToken(), '');
});

test('late 401 from an older request does not clear a newly established session', async () => {
  const {api, responses} = harness();
  api.setSessionToken('old-session');
  let finish;
  responses.push(new Promise(resolve => { finish = resolve; }));
  const pending = api.fetchAutomationRules();
  api.setSessionToken('new-session');
  finish({status: 401, ok: false, text: async () => '{"detail":"Session expired"}'});
  await assert.rejects(pending, /Session expired/);
  assert.equal(api.getSessionToken(), 'new-session');
});
