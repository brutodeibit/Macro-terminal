const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[2]||'index.html','utf8');
const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(x=>x[1]);
const element=()=>({innerHTML:'',textContent:'',className:'',classList:{add(){},remove(){}},querySelectorAll:()=>[]});
const ctx={console,window:{addEventListener(){}},document:{getElementById:element,querySelector:element,querySelectorAll:()=>[]},localStorage:{getItem:()=>null,setItem(){}},setTimeout(){},setInterval(){},location:{protocol:'https:'}};
vm.createContext(ctx); for(const script of scripts)vm.runInContext(script,ctx);
if(process.argv[2]==='claude-preview.html')vm.runInContext(fs.readFileSync('v7-ui.js','utf8'),ctx);
assert.equal(vm.runInContext('__optNum(null)',ctx),null);
assert.equal(vm.runInContext("__optNum('')",ctx),null);
assert.equal(vm.runInContext('__optNum(0)',ctx),0);
assert.equal(vm.runInContext("parseRate('3.75–4.00%')",ctx),3.875);
assert.equal(vm.runInContext("parseRate('-0.25%')",ctx),-.25);
for(const [score,expected] of [[null,0],[50,0],[35,-1],[65,1]]){
 ctx.riskScore=score;assert.equal(vm.runInContext('macroDatabase.__riskOnOff={score:riskScore};fxRiskRegime()',ctx),expected);
}
const feed=JSON.parse(fs.readFileSync(process.argv[2]==='claude-preview.html'?'macro-feed-v7.json':'macro-feed.json','utf8'));ctx.feed=feed;
vm.runInContext(`Object.assign(macroDatabase,feed.economies); for(const [k,v] of Object.entries(feed)) if(k!=='economies')macroDatabase['__'+k]=v;`,ctx);
for(const fn of ['renderRiskOnOff','renderFxComparator','renderGlobalMarkets','renderCotSection','renderOptionsSection','renderDarkPoolSection','renderRotationSection','renderCryptoBondSection']){
 const result=vm.runInContext(fn+'()',ctx);assert.equal(typeof result,'string');assert(result.length>0);console.log(fn+': OK');
}
vm.runInContext("macroDatabase.__riskOnOff={score:null,assets:[]}",ctx);
assert(!vm.runInContext('renderRiskOnOff()',ctx).includes('>0/100<'),'Missing risk score must not become zero');
if(process.argv[2]==='claude-preview.html'){
 const fx=vm.runInContext('buildFxComparator()',ctx);
 for(let i=0;i<fx.matrix.length;i++)for(let j=0;j<fx.matrix.length;j++){
  const a=fx.matrix[i].cols[j],b=fx.matrix[j].cols[i];
  if(a===null)assert.equal(b,null);else assert(Math.abs(a+b)<1e-10,'FX matrix must be antisymmetric');
 }
 // A delayed verified yield remains visible, but must not become a current carry input.
 vm.runInContext("window.__savedChBonds=macroDatabase.ch.bonds;macroDatabase.ch.bonds={tenors:[{term:'2Y',yield:'0.238%',observedAt:'2020-01-02',source:'SNB'}]}",ctx);
 assert(vm.runInContext("sovereignCell('CHF','2Y')",ctx).includes('0.238%'));
 assert(vm.runInContext("sovereignCell('CHF','2Y')",ctx).includes('retrasado'));
 assert(Number.isNaN(vm.runInContext("buildFxComparator().rows.find(x=>x.code==='CHF').y2",ctx)));
 vm.runInContext("macroDatabase.ch.bonds=window.__savedChBonds",ctx);
 const table=vm.runInContext('renderFxComparator()',ctx);
 assert(table.includes('>1Y</th>')&&table.includes('>5Y</th>'));
 assert(!table.includes('—%'),'Missing yields must not be formatted as a percentage');
 // The matrix and the USD row use the same partial comparison, without a fake macro zero.
 vm.runInContext("window.__savedJp=macroDatabase.jp;window.__savedFx=macroDatabase.__fx;macroDatabase.jp={...macroDatabase.jp,indicators:[],conference:{}};macroDatabase.__fx={...macroDatabase.__fx,currencies:{...macroDatabase.__fx.currencies,JPY:{observedAt:new Date().toISOString(),change5s:1,change21s:2},USD:{observedAt:new Date().toISOString(),change5s:0,change21s:0}}}",ctx);
 const partial=vm.runInContext('buildFxComparator()',ctx);
 const jpy=partial.rows.find(x=>x.code==='JPY');
 assert(Number.isNaN(jpy.pol),'Absent macro evidence is not a neutral observation');
 assert.equal(partial.matrix.find(x=>x.base==='JPY').cols[7],jpy.score);
 assert(jpy.label.startsWith('Parcial'));
 vm.runInContext("macroDatabase.jp=window.__savedJp;macroDatabase.__fx=window.__savedFx",ctx);
 const meetings=vm.runInContext('renderMeetingHistory(macroDatabase.eu)',ctx);
 assert.equal(typeof meetings,'string');assert.equal((meetings.match(/class="card /g)||[]).length,3);
 assert(meetings.includes('ecb.europa.eu'));
 ctx.expired={profiles:[{expiration:new Date().toISOString().slice(0,10),expirationAt:new Date(Date.now()-1000).toISOString()}]};
 assert.equal(vm.runInContext('optionsUsableProfiles(expired).length',ctx),0);
 vm.runInContext("window.__optTicker='DJX';window.__optFamily='Dow Jones'",ctx);
 assert(vm.runInContext('renderOptionsSection()',ctx).includes('Dow Jones · DJIA / DJI'));
 ctx.sameDayContracts={profiles:[{expiration:'2099-11-20',contractCode:'ODAX'},{expiration:'2099-11-20',contractCode:'ODAP'}]};
 vm.runInContext("window.__optExpiration='ODAP:2099-11-20'",ctx);
 assert.equal(vm.runInContext('optionsSelectedProfile(sameDayContracts).contractCode',ctx),'ODAP');
 vm.runInContext("window.__optExpiration='ODAX:2099-11-20'",ctx);
 assert.equal(vm.runInContext('optionsSelectedProfile(sameDayContracts).contractCode',ctx),'ODAX');
 assert.equal(vm.runInContext("weeklyEventPriority({event:'Core PCE Price Index'})",ctx),3);
 assert.equal(vm.runInContext("weeklyEventPriority({event:'Jefferson Speaks'})",ctx),0);
 assert.equal(vm.runInContext("weeklyEventPriority({event:'Import Price Index'})",ctx),0);
 assert(vm.runInContext('renderWeeklyFxRadar(macroDatabase.us)',ctx).includes('Qué confirma o cambia la hipótesis'));
 const europe=vm.runInContext("optionsDisplayCatalog(macroDatabase.__options).filter(x=>x.family==='EURO STOXX').map(x=>x.code)",ctx);
 for(const code of ['SX5E','FEZ','SXXP','EXSA'])assert(europe.includes(code));
 console.log('FX symmetry, meeting links and same-day expiry: OK');
}
