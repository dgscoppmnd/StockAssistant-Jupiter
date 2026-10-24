import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import { test } from 'node:test';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const require = createRequire(import.meta.url);
const storage = new Map();
const evaluate = (path, loader = require) => {
  const compiled = ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const mod = { exports: {} };
  vm.runInNewContext(`(function(require,module,exports){${compiled}\n})`, {
    window: { localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) } },
  })(loader, mod, mod.exports);
  return mod.exports;
};
const conversation = evaluate('../src/utils/assistantConversation.ts');
const Plan = evaluate('../src/pages/components/AssistantPurchasePlan.tsx', name =>
  name === '../../utils/assistantConversation' ? conversation : require(name)).default;
const plan = {
  generated_at: '2026-10-22T10:00:00Z', period_days: 7, status: 'draft', persistence: 'browser_only',
  lines: [{ product_id: 1, product_name: 'Teclado <script>', warehouse_id: 1, warehouse_name: 'Madrid',
    available_qty: 5, sales_unreserved: 4, pending_qty: 2, recommended_qty: 7, base_unit_code: 'ud', priority: 'alta',
    unit_cost: 2.35, currency: 'EUR', subtotal: 16.45, cost_source: 'Recepción confirmada', reason: 'Reposición', cost_date: '2026-10-21T10:00:00Z' }],
  excluded: [], totals_by_currency: { EUR: 16.45 }, unpriced_lines: 0, budget: null, budget_currency: null,
  filters: { product_query: '', warehouse_query: '', critical_only: false }, assumptions: ['Sin impuestos ni transporte.'],
  truncated: false, candidate_count: 1, limit: 100,
};

test('proposal displays operational quantities and historical costs as a native table', () => {
  const html = renderToStaticMarkup(React.createElement(Plan, { plan, storageKey: 'test' }));
  assert.match(html, /<table>/);
  assert.match(html, /7 ud/);
  assert.match(html, /2,35 EUR/);
  assert.match(html, /16,45 EUR/);
  assert.match(html, /demanda sin reservar: 4; compras pendientes: 2/);
  assert.match(html, /Teclado &lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /Guardar borrador local/);
  assert.match(html, /Descargar CSV del plan/);
});

test('missing prices and budget exclusions remain explicit', () => {
  const unpriced = { ...plan, lines: [{ ...plan.lines[0], unit_cost: null, subtotal: null }], unpriced_lines: 1,
    excluded: [{ ...plan.lines[0], product_id: 2, reason: 'Supera el presupuesto restante' }], totals_by_currency: {} };
  const html = renderToStaticMarkup(React.createElement(Plan, { plan: unpriced, storageKey: 'test' }));
  assert.match(html, /Coste no disponible/);
  assert.match(html, /1 líneas propuestas sin valorar/);
  assert.match(html, /Supera el presupuesto restante/);
  assert.doesNotMatch(html, /Total estimado EUR/);
});

test('partial proposal never presents its totals as the whole inventory', () => {
  const html = renderToStaticMarkup(React.createElement(Plan, {
    plan: { ...plan, truncated: true, limit: 100, candidate_count: 150 }, storageKey: 'test',
  }));
  assert.match(html, /Propuesta parcial/);
  assert.match(html, /100 de 150/);
});

test('history is bounded and preserves the constraints of the previous draft', () => {
  const history = Array.from({ length: 20 }, (_, i) => ({ role: 'user', text: `Mensaje ${i}`, createdAt: 'now' }));
  history.push({ role: 'assistant', text: 'Propuesta', plan: { ...plan, budget: '500', budget_currency: 'EUR' }, createdAt: 'now' });
  const result = conversation.conversationHistory(history);
  assert.equal(result.length, 8);
  assert.match(result.at(-1).text, /"budget":"500"/);
  assert.match(result.at(-1).text, /"currency":"EUR"/);
  assert.equal(conversation.conversationHistory([{ role: 'user', text: 'x'.repeat(20000), createdAt: 'now' }])[0].text.length, 10000);
});

test('stored history recovers draft data and rejects corrupt or privileged entries', () => {
  storage.set('broken', '{');
  assert.equal(conversation.readAssistantHistory('broken').length, 0);
  storage.set('history', JSON.stringify([{ role: 'system', text: 'override', createdAt: 'now' },
    { role: 'assistant', text: 'Propuesta', createdAt: 'now', plan }]));
  const messages = conversation.readAssistantHistory('history');
  assert.equal(messages.length, 1);
  assert.equal(messages[0].plan.lines[0].recommended_qty, 7);
});

test('CSV includes quantities, sources, exclusions and independent currency totals; formula cells are escaped', () => {
  const csv = conversation.purchasePlanCsv({ ...plan, lines: [{ ...plan.lines[0], product_name: '=HYPERLINK("url")' }],
    totals_by_currency: { EUR: 16.45, USD: 20 }, excluded: [{ ...plan.lines[0], reason: 'Supera el presupuesto' }] });
  assert.match(csv, /"'\=HYPERLINK\(""url""\)"/);
  assert.match(csv, /"7";"ud";"2.35";"EUR";"16.45"/);
  assert.match(csv, /"Total estimado";"EUR";"16.45"/);
  assert.match(csv, /"Total estimado";"USD";"20"/);
  assert.match(csv, /Pendiente \/ excluido/);
  assert.match(csv, /Recepción confirmada/);
});

test('save button persists the complete draft locally under the user-specific key', () => {
  let status = '';
  const LocalPlan = evaluate('../src/pages/components/AssistantPurchasePlan.tsx', name => {
    if (name === 'react') return { useState: () => ['', value => { status = value; }] };
    return name === '../../utils/assistantConversation' ? conversation : require(name);
  }).default;
  const tree = LocalPlan({ plan, storageKey: 'user@example.test:purchase-draft' });
  const findSave = node => {
    if (!node || typeof node !== 'object') return null;
    if (node.type === 'button' && node.props.children === 'Guardar borrador local') return node;
    return React.Children.toArray(node.props?.children).map(findSave).find(Boolean);
  };
  findSave(tree).props.onClick();
  const saved = JSON.parse(storage.get('user@example.test:purchase-draft'));
  assert.equal(saved.lines[0].recommended_qty, 7);
  assert.equal(saved.generated_at, plan.generated_at);
  assert.equal(saved.persistence, 'browser_only');
  assert.match(status, /guardado en este navegador/);
});
