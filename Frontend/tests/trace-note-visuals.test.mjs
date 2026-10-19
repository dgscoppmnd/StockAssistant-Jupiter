import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import { test } from 'node:test';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const source = readFileSync(new URL('../src/pages/components/TraceNoteVisuals.tsx',import.meta.url),'utf8');
const {outputText} = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}});
const compiled = {exports:{}};
vm.runInNewContext(`(function(require,module,exports){${outputText}\n})`)(createRequire(import.meta.url),compiled,compiled.exports);
const Visuals = compiled.exports.default;

test('source values, unit and accessible data table accompany the chart',()=>{
  const html=renderToStaticMarkup(React.createElement(Visuals,{metrics:[{label:'Pendientes',value:'2',unit:'propuestas'}],
    chart:{title:'Estado de propuestas',unit:'propuestas',points:[{label:'Pendientes',value:'2'},{label:'Aprobadas',value:'1'}]}}));
  assert.match(html,/Estado de propuestas/);
  assert.match(html,/Ver valores de la gráfica/);
  assert.match(html,/<table>/);
  assert.match(html,/Valor \(propuestas\)/);
});

test('negative stock values use a finite chart scale',()=>{
  const html=renderToStaticMarkup(React.createElement(Visuals,{metrics:[],chart:{title:'Stock',unit:'kg',
    points:[{label:'Disponible',value:'-2'},{label:'Pendiente',value:'5'}]}}));
  assert.match(html,/<svg/);
  assert.match(html,/-2/);
  assert.doesNotMatch(html,/NaN|Infinity|width="-/);
});

test('insufficient chart data does not produce an empty or invalid graphic',()=>{
  for(const points of [[{label:'Dato',value:'4'}],[{label:'A',value:'0'},{label:'B',value:'0'}],
    [{label:'A',value:'NaN'},{label:'B',value:'Infinity'}]]){
    const html=renderToStaticMarkup(React.createElement(Visuals,{metrics:[],chart:{title:'Datos',unit:'unit',points}}));
    assert.doesNotMatch(html,/<svg/);
  }
});
