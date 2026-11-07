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
 const meetings=vm.runInContext('renderMeetingHistory(macroDatabase.eu)',ctx);
 assert.equal(typeof meetings,'string');assert.equal((meetings.match(/class="card /g)||[]).length,3);
 assert(meetings.includes('ecb.europa.eu'));
 ctx.expired={profiles:[{expiration:new Date().toISOString().slice(0,10),expirationAt:new Date(Date.now()-1000).toISOString()}]};
 assert.equal(vm.runInContext('optionsUsableProfiles(expired).length',ctx),0);
 console.log('FX symmetry, meeting links and same-day expiry: OK');
}
