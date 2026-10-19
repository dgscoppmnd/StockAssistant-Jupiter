import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/utils/observedAi.ts', import.meta.url), 'utf8');
const {outputText} = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020}});
const {describeObservedAi} = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const run = (changes = {}) => ({status: 'completed', result: null, error_message: null, ...changes});

test('connection failures explain historical paid-provider policy without inventing a fallback', () => {
  const failure = run({status: 'degraded', result: {degraded_reason: 'Cannot connect to Ollama'}, config_snapshot: {allow_unmetered_paid_ai: false}});
  const info = describeObservedAi(failure);
  assert.equal(info.tone, 'critical');
  assert.equal(info.provider, null);
  assert.match(info.explanation, /no intentó cambiar a OpenAI/);
  for (const snapshot of [null, {allow_unmetered_paid_ai: true}]) {
    assert.doesNotMatch(describeObservedAi({...failure, config_snapshot: snapshot}).explanation, /tenía desautorizado/);
  }
});

test('successful analysis identifies the actual provider and fallback', () => {
  for (const provider of ['ollama', 'openai']) {
    const info = describeObservedAi(run({result: {ai: {provider, model: 'test-model', used_fallback: provider === 'openai'}}}));
    assert.equal(info.tone, 'success');
    assert.equal(info.provider, provider);
    assert.equal(info.model, 'test-model');
    assert.equal(info.explanation.includes('respaldo automático'), provider === 'openai');
  }
});

test('degraded runs never display success even if they contain provider metadata', () => {
  const info = describeObservedAi(run({status: 'degraded', result: {ai: {provider: 'openai'}, degraded_reason: 'Selección del modelo fuera del contrato'}}));
  assert.equal(info.tone, 'warning');
  assert.equal(info.title, 'Respuesta de IA no válida');
});

test('running and deterministic runs do not imply an AI response', () => {
  assert.equal(describeObservedAi(run({status: 'running'})).tone, 'neutral');
  const deterministic = describeObservedAi(run());
  assert.equal(deterministic.provider, null);
  assert.equal(deterministic.title, 'Ejecución completada sin IA');
});

test('configuration, timeout, rejected response and unknown failures remain distinct', () => {
  for (const [reason, title] of [
    ['OpenAI is not configured', 'OpenAI sin configurar'],
    ['Respuesta recibida después del plazo; sin acciones', 'Tiempo de análisis agotado'],
    ['Ollama model is not available', 'Modelo no disponible'],
    ['No hay llamadas al modelo autorizadas', 'Llamadas al modelo deshabilitadas'],
    ['Unexpected problem', 'Análisis no completado'],
  ]) {
    const info = describeObservedAi(run({status: 'failed', error_message: reason}));
    assert.equal(info.title, title);
    assert.equal(info.reason, reason);
    assert.equal(info.tone, 'critical');
  }
});
