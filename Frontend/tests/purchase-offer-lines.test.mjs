import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
import {test} from 'node:test';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const require=createRequire(import.meta.url);
const compile=(path)=>ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
const evaluate=(source,loader)=>{
  const compiled={exports:{}};
  vm.runInNewContext(`(function(require,module,exports){${source}\n})`)(loader,compiled,compiled.exports);
  return compiled.exports;
};
const offers=evaluate(compile('../src/utils/proposalOffers.ts'),require);
const selected=[];
const PurchaseOfferLines=evaluate(compile('../src/pages/components/PurchaseOfferLines.tsx'),name=>{
  if(name==='../../api')return {fetchMasterRecords:()=>Promise.resolve([])};
  if(name==='../../utils/proposalOffers')return offers;
  if(name==='./ProductCombobox')return {default:(props)=>{
    selected.push(props.selectedId);
    return React.createElement('input',{'aria-label':props.label,value:props.selectedId,readOnly:true,disabled:props.disabled});
  }};
  return require(name);
}).default;

test('one recommendation line per product preserves every offer field and preselects the recommended product',()=>{
  selected.length=0;
  const rows=offers.recommendedOfferLines([],10,[{phase:'decision',detail:{choices:[
    {product_id:101,warehouse_id:1,action:'replenish'},{product_id:202,warehouse_id:1,action:'replenish'}]}}]);
  const html=renderToStaticMarkup(React.createElement(PurchaseOfferLines,{rows,drafts:{},busy:false,onChange:()=>{}}));
  assert.equal((html.match(/<fieldset/g)??[]).length,2);
  assert.deepEqual(selected,[101,202]);
  for(const label of ['Precio por unidad base (EUR)','Oferta válida hasta','Referencia de oferta'])
    assert.equal(html.split(label).length-1,2);
  assert.equal((html.match(/<label>Proveedor<select/g)??[]).length,2);
  assert.doesNotMatch(html,/Proveedor \(ID\)/);
});

test('empty recommendations render a clear state without an unrelated global offer',()=>{
  const html=renderToStaticMarkup(React.createElement(PurchaseOfferLines,{rows:[],drafts:{},busy:false,onChange:()=>{}}));
  assert.match(html,/Abre una traza/);
  assert.doesNotMatch(html,/<fieldset/);
});
