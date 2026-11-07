// Chart contracts with real feed data; this is not a browser screenshot test.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('claude-preview.html','utf8'),plots=[],timers=[],nodes=new Map();
let observer;
const elem=id=>({id,style:{},dataset:{},clientWidth:980,parentNode:null,classList:{contains:()=>false},querySelector:s=>nodes.get(s.slice(1)),replaceChildren(){},insertAdjacentElement(){},set innerHTML(v){this.markup=v;if(v.includes('id="fg-v2-chart"'))nodes.set('fg-v2-chart',elem('fg-v2-chart'));},get innerHTML(){return this.markup||'';}});
const svg={replaceWith(box){nodes.set('fg-v2',box);}};
nodes.set('sec-sentiment',{querySelector:()=>svg});nodes.set('crypto-etf-flow-chart',elem('crypto-etf-flow-chart'));
const P={newPlot(h,data,layout,config){plots.push({id:typeof h==='string'?h:h.id,data,layout,config});return Promise.resolve();},relayout(){}};
const ctx={console,window:{addEventListener(){}},document:{body:elem('body'),getElementById:id=>nodes.get(id),querySelectorAll:()=>[],createElement:()=>elem('new')},localStorage:{getItem:()=>null},setTimeout:f=>timers.push(f),setInterval(){},getComputedStyle:()=>({getPropertyValue:()=> '#eeeeee'}),MutationObserver:class{constructor(f){observer=f;}observe(){}},location:{protocol:'https:'}};
vm.createContext(ctx);
for(const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi))vm.runInContext(match[1],ctx);
vm.runInContext(fs.readFileSync('v7-ui.js','utf8'),ctx);
ctx.feed=JSON.parse(fs.readFileSync('macro-feed-v7.json','utf8'));
vm.runInContext("Object.assign(macroDatabase,feed.economies);for(const [k,v] of Object.entries(feed))if(k!=='economies')macroDatabase['__'+k]=v;",ctx);
ctx.__loadPlotly=()=>Promise.resolve(P);
const start=html.indexOf('(function(){',html.indexOf('/* CHARTS V2'));
const end=html.indexOf('})();',start)+5;
vm.runInContext(html.slice(start,end),ctx);
(async()=>{
 observer();for(const f of timers.splice(0))f();await new Promise(setImmediate);
 assert.equal(plots.filter(p=>p.id==='fg-v2-chart').length,1);
 assert.equal(plots.filter(p=>p.id==='crypto-etf-flow-chart').length,1);
 const fg=plots.find(p=>p.id==='fg-v2-chart');
 assert.equal(fg.layout.height,550);assert.equal(fg.layout.yaxis.range.join(','),'0,100');
 assert.equal(fg.data.find(t=>t.name==='BTC (USD)').yaxis,'y2');
 assert.equal(fg.layout.yaxis2.overlaying,'y');assert.equal(fg.layout.dragmode,'pan');
 const etf=plots.find(p=>p.id==='crypto-etf-flow-chart');
 for(const t of etf.data){assert.equal(t.type,'bar');assert(t.y.length>=21);for(let i=0;i<t.y.length;i++)assert.equal(t.marker.color[i],t.y[i]>=0?'#22c55e':'#ef4444');}
 for(const p of plots){assert.equal(p.config.scrollZoom,true);assert(p.config.modeBarButtonsToRemove.includes('lasso2d'));}
 for(const id of ['sec-options','opt-gex-chart','opt-oi-chart','opt-term-chart'])nodes.set(id,elem(id));
 vm.runInContext("__drawOptionsCharts(macroDatabase.__options.markets.find(m=>m.ticker==='SPX'),macroDatabase.__options.markets.find(m=>m.ticker==='SPX').profiles[0])",ctx);
 await new Promise(setImmediate);
 const term=plots.find(p=>p.id==='opt-term-chart');assert(term);assert(term.data[0].y.every(v=>v>0&&v<500));
 assert(!nodes.get('opt-term-chart').innerHTML.includes('Cargando'));
 assert.notEqual(plots.find(p=>p.id==='opt-gex-chart').layout.annotations.find(a=>a.text.startsWith('Max Pain')).y,plots.find(p=>p.id==='opt-gex-chart').layout.annotations.find(a=>a.text.startsWith('Spot')).y);
 console.log('Chart contracts: unique FG/ETF plots, separate axes, sign colors, full history, interactivity, IV units and staggered labels OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
