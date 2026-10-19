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
const evaluate=(path,loader)=>{const module={exports:{}};vm.runInNewContext(`(function(require,module,exports){${compile(path)}\n})`)(loader,module,module.exports);return module.exports;};
const offers=evaluate('../src/utils/proposalOffers.ts',require);
const drafts=evaluate('../src/utils/stockOrderDrafts.ts',name=>name==='./proposalOffers'?offers:require(name));
const sample={key:'1-5',warehouse_id:1,warehouse_name:'Central',supplier_id:5,supplier_name:'Proveedor de prueba',supplier_code:'PRUEBA',
  valid_until:'2030-01-01T12:00:00Z',notes:'Este pedido viene de una Revisar propuestas y resultados.',purchase_order_number:'REC-1-1-5',
  confirmed:false,operation_key:'recommendation-stock-1-1-5',lines:[
    {product_id:100,quantity:'12.0000',unit_code:'kg',unit_price:'2.5000'},
    {product_id:200,quantity:'3.0000',unit_code:'unit',unit_price:'8.7500'}]};

test('all prepared products, quantities, base units and prices populate distinct stock form lines',()=>{
  assert.deepEqual(drafts.stockDraftLines(sample).map(line=>[line.product_id,line.quantity,line.unit_code,line.unit_price]),[
    [100,12,'kg',2.5],[200,3,'unit',8.75]]);
  assert.equal(drafts.stockDraftLines(undefined),undefined);
});

test('conversion payload includes every recommended row and its supplier quote before navigation',()=>{
  const rows=[{key:'10:100:1',runId:10,productId:100,warehouseId:1,productName:'A'},
    {key:'10:200:2',runId:10,productId:200,warehouseId:2,productName:'B'}];
  const quote=product_id=>({product_id,supplier_id:'5',unit_price:'2.5',reference:'Oferta documentada',valid_until:'2030-01-01T12:00'});
  const payload=drafts.stockDraftPayload(rows,{'10:100:1':quote(100),'10:200:2':quote(200)});
  assert.deepEqual(payload.lines.map(line=>[line.product_id,line.warehouse_id,line.quote.supplier_id]),[[100,1,5],[200,2,5]]);
  assert.throws(()=>drafts.stockDraftPayload(rows,{}),/Completa la oferta/);
});

test('manual conversion accepts the screenshot case: wait decisions and empty commercial references',()=>{
  const rows=[199999,200000].map(productId=>({key:`19:${productId}:1`,runId:19,productId,warehouseId:1,productName:`Producto #${productId}`,action:'wait'}));
  const quotes=Object.fromEntries(rows.map((row,index)=>[row.key,{product_id:row.productId,supplier_id:String(index+1),unit_price:String(17-index),valid_until:'2030-11-01T12:22',reference:''}]));
  const payload=drafts.stockDraftPayload(rows,quotes);
  assert.equal(payload.lines.length,2);
  assert.deepEqual(payload.lines.map(line=>line.quote.reference),['','']);
  assert.match(offers.offerError(rows[0].productId,quotes[rows[0].key]),/referencia/);
  assert.throws(()=>drafts.stockDraftPayload(rows,{...quotes,[rows[0].key]:{...quotes[rows[0].key],supplier_id:''}}),/proveedor/);
});

test('conversion button waits for the saved recommendation then navigates to its inventory form',async()=>{
  const rows=[{key:'19:199999:1',runId:19,productId:199999,warehouseId:1,productName:'Camiseta',action:'wait'}];
  const quote={product_id:199999,supplier_id:'3',unit_price:'17',valid_until:'2030-10-31T12:21',reference:''};
  let stateIndex=0,button,resolveSave;
  const navigation=[],calls=[];
  const saved=new Promise(resolve=>{resolveSave=resolve;});
  const jsx=(type,props)=>{
    if(type==='button'&&props.children==='Convertir en pedido de stock')button=props;
    return {type,props};
  };
  const Page=evaluate('../src/pages/AgentControlPage.tsx',name=>{
    if(name==='react')return {useEffect:()=>{},useState:initial=>{
      const index=stateIndex++;
      return [index===18?['edit']:index===21?{[rows[0].key]:quote}:initial,()=>{}];
    }};
    if(name==='react/jsx-runtime')return {jsx,jsxs:jsx};
    if(name==='react-router-dom')return {useNavigate:()=>url=>navigation.push(url),Link:()=>null};
    if(name==='../api')return {automationRequest:(...args)=>{calls.push(args);return saved;}};
    if(name==='../utils/proposalOffers')return {...offers,recommendedOfferLines:()=>rows};
    if(name==='../utils/stockOrderDrafts')return drafts;
    if(name.startsWith('./components/'))return {default:()=>null};
    return require(name);
  }).default;
  Page();
  assert.equal(button.disabled,false);
  button.onClick();
  assert.equal(calls[0][0],'/stock-order-drafts');
  assert.equal(calls[0][2].lines[0].quote.reference,'');
  assert.deepEqual(navigation,[]);
  resolveSave({id:123});
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(navigation,['/inventario?recommendation=123']);
});

test('reusable card keeps its form structure and preselects supplier, warehouse, notes and every price',()=>{
  const supplierSelections=[],products=[];
  const Card=evaluate('../src/pages/components/StockOrderCard.tsx',name=>{
    if(name==='../../utils/stockOrderDrafts')return drafts;
    if(name==='../../api')return {fetchMasterRecords:async()=>[]};
    if(name==='./SupplierCombobox')return {default:props=>{supplierSelections.push(props.selectedId);return React.createElement('input',{'aria-label':'Proveedor (código o nombre)',value:props.selectedId??'',readOnly:true});}};
    if(name==='./ProductCombobox')return {default:props=>{products.push(props.selectedId);return React.createElement('input',{value:props.selectedId,readOnly:true});}};
    if(name==='./InventoryCardInfo'||name==='./SectionIcon')return {default:()=>null};
    if(name==='./InventoryCrudCard')return {default:props=>React.createElement('article',{className:props.className},
      React.createElement('h3',null,props.title),React.createElement('form',null,props.children,props.footer))};
    return require(name);
  }).default;
  const props={dashboard:{warehouses:[{id:1,name:'Central',code:'C'},{id:2,name:'Secundaria',code:'S'}],stock_snapshot:[]},busy:false,
    setBusy:()=>{},setError:()=>{},runOperation:async()=>true,recommendationId:1};
  const html=renderToStaticMarkup(React.createElement(React.Fragment,null,
    React.createElement(Card,{...props,initialDraft:sample}),
    React.createElement(Card,{...props,initialDraft:{...sample,key:'2-6',supplier_id:6,warehouse_id:2}})));
  assert.deepEqual(supplierSelections,[5,6]);
  assert.deepEqual(products,[100,200,100,200]);
  assert.equal((html.match(/Crear pedido de stock/g)??[]).length,2);
  assert.match(html,/stock-order-meta/);assert.match(html,/stock-order-lines/);
  assert.match(html,/value="2.5"/);assert.match(html,/value="8.75"/);
  assert.equal((html.match(/Revisar propuestas y resultados/g)??[]).length,2);
  assert.match(html,/value="2" selected=""/);
  const ids=[...html.matchAll(/ id="([^"]+)"/g)].map(match=>match[1]);
  assert.equal(new Set(ids).size,ids.length);
});
