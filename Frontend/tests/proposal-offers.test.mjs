import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import ts from 'typescript';
const source=readFileSync(new URL('../src/utils/proposalOffers.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}});
const {recommendedOfferLines,offerKey,emptyOffer,offerError,quoteForProposal}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const proposal=(changes={})=>({id:1,run_id:10,product_id:100,warehouse_id:1,product_name:'Producto A',warehouse_name:'Central',action:'replenish',status:'approved',...changes});
const validOffer=(productId,changes={})=>({...emptyOffer(productId),supplier_id:'7',unit_price:'2.5000',valid_until:'2030-01-01T12:00',reference:'Oferta confirmada',...changes});
const now=new Date('2026-10-19T12:00Z').getTime();

test('two recommended products generate separate lines with their recommended product IDs',()=>{
  const a=proposal(),b=proposal({id:2,product_id:200,product_name:'Producto B'});
  const events=[{phase:'decision',detail:{choices:[{product_id:100,warehouse_id:1,action:'replenish'},{product_id:200,warehouse_id:1,action:'replenish'}]}}];
  const rows=recommendedOfferLines([a,b],10,events);
  assert.equal(rows.length,2);
  assert.deepEqual(rows.map(row=>row.productId),[100,200]);
  assert.deepEqual(rows.map(row=>row.proposalId),[1,2]);
  assert.deepEqual(rows.map(row=>emptyOffer(row.productId).product_id),[100,200]);
});

test('each execution receives only its product and warehouse offer',()=>{
  const a=proposal(),b=proposal({id:2,product_id:200}),otherWarehouse=proposal({warehouse_id:2}),otherRun=proposal({run_id:11});
  const drafts={
    [offerKey(10,100,1)]:validOffer(100),
    [offerKey(10,200,1)]:validOffer(200,{supplier_id:'8',unit_price:'99.1',reference:'Segunda oferta'}),
  };
  assert.equal(quoteForProposal(a,drafts,now).supplier_id,7);
  assert.equal(quoteForProposal(b,drafts,now).unit_price,'99.1');
  assert.throws(()=>quoteForProposal(otherWarehouse,drafts,now),/Completa la oferta/);
  assert.throws(()=>quoteForProposal(otherRun,drafts,now),/Completa la oferta/);
  assert.equal('product_id' in quoteForProposal(a,drafts,now),false);
});

test('changing the selected product cannot silently apply its quote to another proposal',()=>{
  const a=proposal(),drafts={[offerKey(10,100,1)]:validOffer(200)};
  assert.throws(()=>quoteForProposal(a,drafts,now),/producto recomendado #100/);
});

test('unpersisted and non-purchase recommendations remain visible without becoming purchase actions',()=>{
  const rows=recommendedOfferLines([],10,[{phase:'decision',detail:{choices:[
    {product_id:100,warehouse_id:1,action:'replenish'},{product_id:200,warehouse_id:1,action:'wait'}]}}]);
  assert.equal(rows.length,2);
  assert.equal(rows[0].proposalId,undefined);
  assert.equal(rows[1].action,'wait');
});

test('only the selected run and final recorded decision populate the recommendation lines',()=>{
  const rows=recommendedOfferLines([proposal({run_id:11})],10,[
    {phase:'decision',detail:{choices:[{product_id:100,warehouse_id:1,action:'replenish'}]}},
    {phase:'schema_rejected',detail:{choices:[{product_id:999,warehouse_id:1,action:'replenish'}]}},
    {phase:'decision',detail:{choices:[]}},
  ]);
  assert.deepEqual(rows,[]);
});

test('quotes require a supplier, positive price, future date and offer reference',()=>{
  assert.equal(offerError(100,validOffer(100),now),'');
  for(const changes of [{supplier_id:''},{supplier_id:'-1'},{unit_price:'0'},{unit_price:'2.00001'},
    {valid_until:'2020-01-01'},{valid_until:'incorrecta'},{reference:'ab'}]){
    assert.notEqual(offerError(100,validOffer(100,changes),now),'');
  }
});

test('without a selected trace only outstanding purchase proposals require quote lines',()=>{
  const rows=recommendedOfferLines([proposal(),proposal({id:2,product_id:200,status:'pending_approval'}),
    proposal({product_id:300,status:'executed'}),proposal({product_id:400,action:'wait'})],null,[]);
  assert.deepEqual(rows.map(row=>row.productId),[100,200]);
});
