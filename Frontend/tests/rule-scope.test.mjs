import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import ts from 'typescript';
const source=readFileSync(new URL('../src/utils/ruleScope.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}});
const {parseScopeIds,toggleScopeId}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('saved comma-separated IDs restore checked selections across searches and pages',()=>{
  const saved='12, 34,56';
  const selected=new Set(parseScopeIds(saved));
  assert.equal(selected.has(34),true);assert.equal(selected.has(78),false);
  const added=toggleScopeId(saved,78);
  assert.equal(added,'12,34,56,78');
  assert.equal(toggleScopeId(added,34),'12,56,78');
});
test('manual changes, duplicates and empty default scope remain consistent with checkboxes',()=>{
  assert.deepEqual(parseScopeIds(''),[]);
  assert.deepEqual(parseScopeIds('4,4, 9'),[4,9]);
  assert.equal(toggleScopeId('4',4),'');
  assert.equal(toggleScopeId('',9),'9');
});
test('invalid input and over 100 selections are rejected without silently changing scope',()=>{
  for(const value of ['1,','0','-1','12,SKU','1e3','1.1','9007199254740992']) assert.throws(()=>parseScopeIds(value));
  const all=Array.from({length:100},(_,index)=>index+1).join(',');
  assert.throws(()=>toggleScopeId(all,101));
  assert.equal(parseScopeIds(toggleScopeId(all,1)).length,99);
});
