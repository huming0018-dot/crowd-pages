'use strict';
// Offline source checks. VM has no browser, real fetch, credentials or device access.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = name => fs.readFileSync(path.join(root, name), 'utf8');
const script = name => source(name).match(/<script>([\s\S]*?)<\/script>/)[1];
function elements() {
  const all = new Map();
  const make = () => ({value:'',textContent:'',innerHTML:'',disabled:false,children:[],dataset:{},style:{},
    classList:{add(){},remove(){},toggle(){}},addEventListener(){},appendChild(x){this.children.push(x);}});
  const get = id => { if (!all.has(id)) all.set(id, make()); return all.get(id); };
  return {get,document:{getElementById:get,createElement:make}};
}
(async () => {
  // Execute the complete owner's page script, including actual click handler and RPC adapter.
  const ui=elements(), calls=[];let result={ok:true};
  const ctx=vm.createContext({document:ui.document,localStorage:{getItem(){return null;},setItem(){}},
    fetch:async (url,opts)=>{const fn=url.split('/').pop();calls.push({fn,body:JSON.parse(opts.body)});
      return {json:async()=>fn==='crowd_fetch_stores'?[]:result};}});
  vm.runInContext(script('owner-rate.html'),ctx);
  ui.get('store').value='演示餐厅';ui.get('reason').value='味道很好服务认真值得再来';ui.get('secret').value='synthetic-only';
  ui.get('stars').children[3].onclick();assert.equal(ui.get('submit').disabled,false);
  await ui.get('submit').onclick();
  const sent=calls.find(x=>x.fn==='crowd_owner_rate');assert.equal(sent.body.p_score,4);
  assert.equal(sent.body.p_store,'演示餐厅');assert.equal(sent.body.p_reason,'味道很好服务认真值得再来');
  assert.match(ui.get('msg').textContent,/已记录/);assert.equal(ui.get('reason').value,'');
  ui.get('reason').value='味道很好服务认真值得再来';ui.get('stars').children[2].onclick();result={ok:false,reason:'forbidden'};
  await ui.get('submit').onclick();assert.match(ui.get('msg').textContent,/失败/);
  assert.equal(ui.get('reason').value,'味道很好服务认真值得再来');
  console.log('PASS owner form: actual payload, success clearing, failure retains input (synthetic RPC only)');

  // Exercise unchanged drainShare source. IndexedDB is synthetic; no network is offered.
  const html=source('submit.html');
  const drain=html.slice(html.indexOf('async function drainShare()'),html.indexOf('// ---------- 启动 ----------'));
  const queued=[{text:'first share'},{text:'second share'}], form=elements();let cleared=false,parsed;
  const db={transaction(_store,mode){const tx={objectStore(){return {
    getAll(){const r={};queueMicrotask(()=>r.onsuccess());r.result=queued.slice();return r;},
    clear(){queued.length=0;cleared=true;queueMicrotask(()=>tx.oncomplete());}
  };}};return tx;}};
  const share=vm.createContext({location:{search:'?share=1'},indexedDB:{open(){const r={result:db};queueMicrotask(()=>r.onsuccess());return r;}},
    $:form.get,toast(){},resolved:null,autoResolve:async()=>{parsed=form.get('noteUrl').value;}});
  vm.runInContext(drain,share);await share.drainShare();
  assert.equal(cleared,true);assert.equal(parsed,'second share');assert.equal(queued.length,0);
  console.log('KNOWN FAILURE reproduced: all shares cleared before resolution; only last item used, failed parse loses both');
})().catch(e=>{console.error(e);process.exitCode=1;});
