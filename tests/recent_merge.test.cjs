'use strict';
// Dependency-free isolated samples; never imports admin.py or calls the network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const paths = process.argv.slice(2);
if (!paths.length) paths.push(fs.existsSync('status.html') ? 'status.html' : 'workspace/food-cloud-v2/admin.py');
const marker = /\/\/ BEGIN crowd recent merge v1[\s\S]*?\/\/ END crowd recent merge v1/;
let reference, checks = 0;
const row = (at, extra = {}) => ({created_at: at, participant_id: 'P-123456789-A', matched_store: 'sample-store', gate_status: 'accepted', ...extra});
const at = (minutes) => new Date(Date.UTC(2026,9,10,1,0) + minutes * 60000).toISOString();
for (const path of paths) {
  const file = fs.readFileSync(path, 'utf8');
  const source = path.endsWith('.py') ? file.split('HTML = r"""')[1].split('"""')[0] : file;
  const helper = source.match(marker)?.[0];
  assert.ok(helper, path + ': shared helper present');
  if (reference) assert.equal(helper, reference, 'both views must use identical rules');
  reference = helper;
  const ctx = vm.createContext({});
  vm.runInContext(helper, ctx);
  const merge = (rows) => JSON.parse(JSON.stringify(ctx.mergeCrowdRecent(rows)));
  const check = (name, rows, counts, latest) => {
    const before = JSON.stringify(rows);
    const out = merge(rows);
    assert.deepEqual(out.map(x => x.n), counts, path + ': ' + name);
    assert.equal(out.reduce((n,x) => n+x.n,0), rows.length, name + ': count preserved');
    assert.equal(JSON.stringify(rows), before, name + ': input unchanged');
    if (latest) assert.equal(out[0].at, latest, name + ': newest timestamp preserved');
    checks++;
  };
  for (const order of ['ascending','descending']) {
    for (const [gap,counts] of [[2,[2]],[10,[1,1]],[60,[1,1]],[9.999,[2]],[10.001,[1,1]]]) {
      const rows = [row(at(0)),row(at(gap))];
      if (order === 'descending') rows.reverse();
      check(order + ' gap ' + gap, rows, counts, at(gap));
    }
    for (const [name,extra] of [
      ['participant same visible prefix',{participant_id:'P-123456789-B'}],
      ['store',{matched_store:'other-store'}],
      ['status',{gate_status:'rejected'}],
      ['duplicate status',{gate_status:'duplicate'}],
      ['missing participant',{participant_id:null}],
      ['missing store',{matched_store:null}],
      ['missing status',{gate_status:null}]
    ]) {
      const rows = [row(at(0)), row(at(2),extra)];
      if (order === 'descending') rows.reverse();
      check(order + ' different ' + name,rows,[1,1],at(2));
    }
    for (const [name,rows,counts] of [
      ['cross midnight',[row('2026-10-09T23:59:00+08:00'),row('2026-10-10T00:01:00+08:00')],[2]],
      ['cross day 60m',[row('2026-10-09T23:30:00+08:00'),row('2026-10-10T00:30:00+08:00')],[1,1]],
      ['fixed anchor prevents chain',[row(at(0)),row(at(8)),row(at(16))],[2,1]]
    ]) {
      if (order === 'descending') rows.reverse();
      check(order + ' ' + name,rows,counts);
    }
  }
  check('out of order',[row(at(0)),row(at(60)),row(at(2))],[1,2],at(60));
  check('equal time',[row(at(0)),row(at(0))],[2],at(0));
  check('timezone equivalence',[row('2026-10-10T09:00:00+08:00'),row('2026-10-10T01:00:00Z')],[2]);
  check('invalid timestamps',[row('invalid'),row('invalid')],[1,1]);
  check('missing timestamps',[row(null),row(null)],[1,1]);
  check('unknown identities',[row(at(0),{participant_id:null}),row(at(2),{participant_id:null})],[1,1]);
  check('intervening store',[row(at(0)),row(at(1),{matched_store:'other-store'}),row(at(2))],[1,1,1]);
  check('empty',[],[]);
  assert.deepEqual(merge(undefined),[]);
  checks++;

  // Run the real view loader with a synthetic RPC response and a stub DOM.
  // A 2m pair must render ×2 at newest time, with a 60m submission separate.
  const elements = {};
  const get = id => elements[id] ||= {style:{},textContent:'',innerHTML:''};
  const sample = {
    ok:true,generated_at:at(65),recent:[row(at(0)),row(at(60)),row(at(62))],
    flow:{accepted_total:3,rejected_total:0,accepted_today:3},
    tasks:{total:1,open:1,in_progress:0,fulfilled:0,closed:0},
    participants:{total:1,active_24h:1}
  };
  const ui = vm.createContext({
    document:{getElementById:get,addEventListener(){}},
    window:{addEventListener(){}},
    setInterval(){}, fetch:async () => ({json:async () => sample}),
    j:async () => sample, $:get, monTime:x=>x
  });
  if (path.endsWith('.html')) {
    const scripts = [...source.matchAll(/<script>([\s\S]*?)<\/script>/g)];
    scripts.forEach(s=>new vm.Script(s[1])); // parse complete browser JS
    vm.runInContext(scripts.map(s=>s[1]).join('\n'),ui);
  } else {
    const scripts = [...source.matchAll(/<script>([\s\S]*?)<\/script>/g)];
    scripts.forEach(s=>new vm.Script(s[1]));
    const loader = source.slice(source.indexOf('async function loadMonitor(manual)'),source.indexOf("setInterval(()=>{if($('page-dashboard')"));
    vm.runInContext(helper+'\n'+loader+'\nloadMonitor();',ui);
  }
  // Both async loaders finish through promise microtasks.
  globalThis.pending ||= [];
  globalThis.pending.push(new Promise(resolve=>setImmediate(()=>{
    const feed = get(path.endsWith('.html')?'feed':'mon-feed').innerHTML;
    assert.equal((feed.match(/×2/g)||[]).length,1,'real renderer: 2m pair merged');
    assert.equal((feed.match(/sample-store/g)||[]).length,2,'real renderer: 60m row separate');
    assert.ok(!feed.includes('×3'),'real renderer: no overmerge');
    const heart = get(path.endsWith('.html')?'genAt':'mon-at').textContent;
    assert.ok(heart.includes('最近'),'real renderer: heartbeat rendered');
    if (path.endsWith('.py')) assert.ok(heart.includes(at(62)),'heartbeat uses newest event');
    checks++;
    resolve();
  })));
}
Promise.all(globalThis.pending).then(()=>console.log('PASS: '+checks+' checks across '+paths.length+' view(s)'));
