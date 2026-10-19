import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
import {test} from 'node:test';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const require=createRequire(import.meta.url);
const compile=path=>ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
const objectives={stock_reorder_proposals:['Reducir roturas manteniendo cobertura y capital'],daily_inventory_report:['Resumen diario permitido']};
const defaults={product_ids:[100],warehouse_ids:[1],products:[{id:100,name:'Producto'}],warehouses:[{id:1,name:'Central',is_active:true}]};
function harness(){
  const states=[],effects=[],calls=[];
  let index=0;
  const module={exports:{}};
  const loader=name=>{
    if(name==='react')return {...React,useRef:()=>({current:null}),useMemo:fn=>fn(),useCallback:fn=>fn,useEffect:fn=>effects.push(fn),useState:initial=>{
      const key=index++;if(!(key in states))states[key]=initial;
      return [states[key],value=>{states[key]=typeof value==='function'?value(states[key]):value;}];
    }};
    if(name==='react-router-dom')return {Link:props=>React.createElement('a',{href:props.to},props.children)};
    if(name==='../api')return {automationRequest:async path=>{
      calls.push(path);return {'/rules':[], '/control':{permissions:['edit']},'/objectives':objectives,'/scope-defaults':defaults}[path];
    }};
    if(name==='./components/RuleScopePicker')return {default:props=>React.createElement('div',{'data-scope':props.label},props.hint)};
    if(name==='../utils/ruleScope')return {parseScopeIds:text=>text?text.split(',').map(Number):[]};
    return require(name);
  };
  vm.runInNewContext(`(function(require,module,exports){${compile('../src/pages/AgentRulesPage.tsx')}\n})`)(loader,module,module.exports);
  return {states,effects,calls,render:()=>{index=0;return module.exports.default();}};
}
const nodes=element=>!element||typeof element!=='object'?[]:[element,...React.Children.toArray(element.props?.children).flatMap(nodes)];

test('merged workspace loads objective catalog and scope defaults and completes its loading state',async()=>{
  const view=harness();view.render();view.effects[0]();
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual([...view.calls],['/rules','/control','/objectives','/scope-defaults']);
  assert.equal(view.states[14],'100');assert.equal(view.states[15],'1');assert.equal(view.states[16],false);
  const html=renderToStaticMarkup(view.render());
  assert.match(html,/rules-workspace/);assert.match(html,/rules-layout/);
  assert.match(html,/Selecciona un objetivo dentro del alcance/);
  assert.match(html,/Compras prioritarias/);assert.match(html,/primer almacén activo/);
  assert.match(html,/Permitir análisis con IA/);
  assert.doesNotMatch(html,/Vacío incluye todos|Máximo de herramientas|Máximo de llamadas IA/);
});

test('changing rule type preserves report restrictions inside the redesigned form',()=>{
  const view=harness();view.render();
  view.states[12]=objectives;
  view.states[2]={...view.states[2],mode:'limited_auto',allowed_actions:['suspend_reorder'],conditions:{mode:'all',items:[{field:'available',operator:'lt',value:'5'}]}};
  const typeSelect=nodes(view.render()).find(node=>node.type==='select'&&node.props.value==='stock_reorder_proposals');
  typeSelect.props.onChange({target:{value:'daily_inventory_report'}});
  assert.equal(view.states[2].objective,objectives.daily_inventory_report[0]);
  assert.equal(view.states[2].mode,'observation');assert.equal(view.states[2].allowed_actions.length,0);
  assert.equal(view.states[2].conditions.items.length,0);
  const html=renderToStaticMarkup(view.render());
  assert.match(html,/Este informe se calcula sin IA/);
  assert.doesNotMatch(html,/Automático limitado|Condiciones declarativas|Permitir análisis con IA/);
});

test('AI toggle retains one model call and zero tools after merge',()=>{
  const view=harness();
  const tree=view.render();
  const label=nodes(tree).find(node=>node.type==='label'&&renderToStaticMarkup(node).includes('Permitir análisis con IA'));
  const checkbox=nodes(label).find(node=>node.type==='input');
  checkbox.props.onChange({target:{checked:false}});
  assert.equal(view.states[2].max_model_calls,0);assert.equal(view.states[2].max_tool_calls,0);
  checkbox.props.onChange({target:{checked:true}});
  assert.equal(view.states[2].max_model_calls,1);assert.equal(view.states[2].max_tool_calls,0);
});
