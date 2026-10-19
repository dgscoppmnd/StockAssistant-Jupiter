import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
import {test} from 'node:test';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const require=createRequire(import.meta.url);
const code=ts.transpileModule(readFileSync(new URL('../src/pages/StockOrdersPage.tsx',import.meta.url),'utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
const rows=[{id:1,purchase_order_number:'PO-NUEVO',supplier_name:'Proveedor A',warehouse_name:'Central',editable:true},
  {id:2,purchase_order_number:'PO-RECIBIDO',supplier_name:'Proveedor B',warehouse_name:'Otra',editable:false}];

function harness(requestHandler){
  const states=[rows,[],[],[],false,false,'','','',null,null,false],calls=[];
  let index=0;
  const selectionRequest={current:0};
  const module={exports:{}};
  const loader=name=>{
    if(name==='react')return {...React,useEffect:()=>{},useCallback:fn=>fn,useRef:()=>selectionRequest,useState:initial=>{
      const id=index++;if(!(id in states))states[id]=initial;
      return [states[id],value=>{states[id]=typeof value==='function'?value(states[id]):value;}];
    }};
    if(name==='../api')return {stockOrdersRequest:async(...args)=>{calls.push(args);return requestHandler?requestHandler(...args):[]},fetchMasterRecords:async()=>[],fetchInventoryDashboard:async()=>({warehouses:[],stock_snapshot:[]})};
    if(name==='./components/InventoryCrudCard')return {default:props=>React.createElement('article',null,
      React.createElement('h3',null,props.title),props.headerAction,
      props.table?props.table.data.map(row=>React.createElement('div',{key:row.id},row.purchase_order_number,
        props.table.columns.find(c=>c.dataField==='actions').formatter(null,row))):React.createElement('form',null,props.children,props.footer))};
    if(name==='./components/ProductCombobox'||name==='./components/SupplierCombobox')return {default:()=>null};
    return require(name);
  };
  vm.runInNewContext(`(function(require,module,exports){${code}\n})`)(loader,module,module.exports);
  return {render:()=>{index=0;return module.exports.default();},states,calls};
}

test('stock order list exposes icon actions and protects received orders',()=>{
  const view=harness();
  const html=renderToStaticMarkup(view.render());
  for(const label of ['Agregar pedido de stock','Actualizar listado','Editar PO-NUEVO','Borrar PO-NUEVO','Editar PO-RECIBIDO'])
    assert.ok(html.includes(`aria-label="${label}"`));
  assert.match(html,/aria-label="Solo se pueden borrar borradores sin entradas de stock" disabled=""/);
  assert.ok((html.match(/<svg/g)??[]).length>=6);
});

test('selecting table records replaces the editor with all lines of the selected order',async()=>{
  const view=harness(path=>({...rows[Number(path.slice(1))-1],supplier_id:1,warehouse_id:1,notes:`Notas ${path}`,lines:[
    {product_id:Number(path.slice(1)),quantity:'12',unit_code:'unit',unit_price:'17'}]}));
  const select=order=>view.render().props.children[1].props.table.onSelectRow(order);
  select(rows[0]);await new Promise(resolve=>setImmediate(resolve));
  assert.equal(view.states[10].id,1);assert.equal(view.states[9].notes,'Notas /1');
  select(rows[1]);await new Promise(resolve=>setImmediate(resolve));
  assert.equal(view.states[10].id,2);assert.equal(view.states[9].notes,'Notas /2');
  assert.equal(view.states[9].lines[0].product_id,2);
  assert.equal(view.states[9].lines[0].quantity,12);
  assert.equal(view.render().props.children[1].props.table.selectedKey,2);
});

test('a delayed response from a previous selection cannot overwrite the latest order',async()=>{
  const pending={};
  const view=harness(path=>new Promise(resolve=>{pending[path]=resolve;}));
  const select=order=>view.render().props.children[1].props.table.onSelectRow(order);
  select(rows[0]);select(rows[1]);
  pending['/2']({...rows[1],notes:'Último pedido',lines:[]});
  await new Promise(resolve=>setImmediate(resolve));
  pending['/1']({...rows[0],notes:'Pedido anterior',lines:[]});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(view.states[10].id,2);assert.equal(view.states[9].notes,'Último pedido');
});

test('received order editor saves number and notes without resubmitting inventory lines',async()=>{
  const view=harness();
  view.states[9]={supplier_id:1,warehouse_id:1,purchase_order_number:'PO-CORREGIDO',notes:'Nota corregida',expected_updated_at:'2026-10-19T10:00:00Z',
    lines:[{product_id:1,quantity:2,unit_code:'unit',unit_price:17}]};
  view.states[10]=rows[1];view.states[11]=true;
  const tree=view.render();
  const html=renderToStaticMarkup(tree);
  assert.match(html,/aria-label="Guardar pedido"/);
  assert.match(html,/id="stock-order-editor-notes"[^>]*>Nota corregida/);
  assert.doesNotMatch(html,/id="stock-order-editor-notes"[^>]*disabled/);
  await tree.props.children[2].props.onSubmit({preventDefault:()=>{}});
  assert.deepEqual(view.calls[0].slice(0,2),['/2','PATCH']);
  assert.equal(view.calls[0][2].notes,'Nota corregida');
  assert.equal(view.calls[0][2].purchase_order_number,'PO-CORREGIDO');
  assert.equal('lines' in view.calls[0][2],false);
});

test('stock order editor supports multiple product lines, supplier and notes with icon save and close',()=>{
  const view=harness();
  view.states[9]={supplier_id:1,warehouse_id:1,purchase_order_number:'PO-NUEVO',notes:'Origen de la propuesta',lines:[
    {product_id:1,quantity:2,unit_code:'unit',unit_price:17},{product_id:2,quantity:12,unit_code:'kg',unit_price:16}]};
  const html=renderToStaticMarkup(view.render());
  assert.equal((html.match(/Precio por unidad base/g)??[]).length,2);
  for(const label of ['Guardar pedido','Cerrar formulario','Agregar línea de producto','Eliminar línea 1','Eliminar línea 2'])
    assert.ok(html.includes(`aria-label="${label}"`));
  assert.match(html,/Origen de la propuesta/);
  assert.match(html,/value="17"/);assert.match(html,/value="16"/);
});
