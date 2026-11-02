const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8');
const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(x=>x[1]);
const element=()=>({innerHTML:'',textContent:'',className:'',classList:{add(){},remove(){}},querySelectorAll:()=>[]});
const ctx={console,window:{addEventListener(){}},document:{getElementById:element,querySelector:element,querySelectorAll:()=>[]},localStorage:{getItem:()=>null,setItem(){}},setTimeout(){},setInterval(){},location:{protocol:'https:'}};
vm.createContext(ctx); for(const script of scripts)vm.runInContext(script,ctx);
assert.equal(vm.runInContext('__optNum(null)',ctx),null);
assert.equal(vm.runInContext("__optNum('')",ctx),null);
assert.equal(vm.runInContext('__optNum(0)',ctx),0);
assert.equal(vm.runInContext("parseRate('3.75–4.00%')",ctx),3.875);
assert.equal(vm.runInContext("parseRate('-0.25%')",ctx),-.25);
for(const [score,expected] of [[null,0],[50,0],[35,-1],[65,1]]){
 ctx.riskScore=score;assert.equal(vm.runInContext('macroDatabase.__riskOnOff={score:riskScore};fxRiskRegime()',ctx),expected);
}
const feed=JSON.parse(fs.readFileSync('macro-feed.json','utf8'));ctx.feed=feed;
vm.runInContext(`Object.assign(macroDatabase,feed.economies); for(const [k,v] of Object.entries(feed)) if(k!=='economies')macroDatabase['__'+k]=v;`,ctx);
for(const fn of ['renderRiskOnOff','renderFxComparator','renderGlobalMarkets','renderCotSection','renderOptionsSection','renderDarkPoolSection','renderRotationSection','renderCryptoBondSection']){
 const result=vm.runInContext(fn+'()',ctx);assert.equal(typeof result,'string');assert(result.length>0);console.log(fn+': OK');
}
vm.runInContext("macroDatabase.__riskOnOff={score:null,assets:[]}",ctx);
assert(!vm.runInContext('renderRiskOnOff()',ctx).includes('>0/100<'),'Missing risk score must not become zero');
