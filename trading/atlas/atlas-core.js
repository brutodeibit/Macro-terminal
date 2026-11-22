/* Atlas P1: pure functions; no network, DOM, or implicit data repair. */
(function(root){
'use strict';
function csv(text){
  text=String(text).replace(/^\uFEFF/,'');
  const first=text.split(/\r?\n/)[0];
  const counts=[',',';','\t'].map(sep=>{let n=0,q=false;for(const c of first){if(c==='"')q=!q;else if(c===sep&&!q)n++;}return [sep,n];}).sort((a,b)=>b[1]-a[1]);
  const sep=counts[0][0], rows=[];let row=[],cell='',quoted=false,ended=false;
  const push=()=>{row.push(cell);cell='';ended=false;};
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(quoted){if(c==='"'){if(text[i+1]==='"'){cell+='"';i++;}else {quoted=false;ended=true;}}else cell+=c;continue;}
    if(c==='"'){if(cell.length||ended)throw Error('Comillas CSV mal formadas');quoted=true;}
    else if(c===sep)push();
    else if(c==='\n'||c==='\r'){if(c==='\r'&&text[i+1]==='\n')i++;push();if(row.some(x=>x.trim()))rows.push(row);row=[];}
    else {if(ended&&!/\s/.test(c))throw Error('Contenido después de comillas');if(!ended)cell+=c;}
  }
  if(quoted)throw Error('Comillas CSV sin cerrar');
  push();if(row.some(x=>x.trim()))rows.push(row);
  if(rows.length<2)throw Error('CSV vacío o sin observaciones');
  return {rows,sep};
}
function date(value){
  const s=String(value).trim();let iso=s;
  if(/^\d{2}\/\d{2}\/\d{4}$/.test(s)){const [d,m,y]=s.split('/');iso=`${y}-${m}-${d}`;}
  if(!/^\d{4}-\d{2}-\d{2}$/.test(iso))throw Error('Fecha diaria requerida: AAAA-MM-DD o DD/MM/AAAA; convierte timestamps según la zona de sesión');
  const t=Date.parse(iso+'T00:00:00Z');
  if(!Number.isFinite(t)||new Date(t).toISOString().slice(0,10)!==iso)throw Error('Fecha inexistente: '+s);
  return iso;
}
function number(value,sep){
  let s=String(value??'').trim();if(sep!==',')s=s.replace(',','.');
  if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(s))throw Error('Número vacío, corrupto o separador de miles ambiguo');
  const n=Number(s);if(!Number.isFinite(n))throw Error('Número fuera de rango');return n;
}
function prices(text,options={}){
  const {rows:table,sep}=csv(text),head=table[0].map(x=>x.trim().toLowerCase());
  if(new Set(head).size!==head.length)throw Error('Cabeceras duplicadas');
  const find=(names)=>{const hits=names.map(x=>head.indexOf(x)).filter(x=>x>=0);if(hits.length>1)throw Error('Columnas ambiguas: '+names.join('/'));return hits[0];};
  const ix={date:find(['date','fecha','time','datetime','timestamp']),close:find(['close','cierre','c']),open:find(['open','apertura','o']),high:find(['high','max','máximo','h']),low:find(['low','min','mínimo','l']),volume:find(['volume','volumen']),symbol:find(['symbol','ticker','instrument','activo']),contract:find(['contract','contrato'])};
  if(ix.date===undefined||ix.close===undefined)throw Error('Se requieren date y close sin ajustar; no se mezcla Adj Close con OHLC');
  const requested=String(options.instrument||'').trim().toUpperCase();
  if(ix.symbol===undefined&&!requested)throw Error('Identifica el instrumento antes de cargar el CSV');
  const symbols=new Set(),contracts=new Set();
  const rows=table.slice(1).map((a,i)=>{
    try{
      if(a.length!==head.length)throw Error('Número de columnas incompatible');
      const symbol=ix.symbol===undefined?requested:a[ix.symbol].trim().toUpperCase();if(!symbol)throw Error('Símbolo vacío');symbols.add(symbol);
      if(requested&&symbol!==requested)throw Error('Símbolo distinto del instrumento declarado');
      if(ix.contract!==undefined){if(!a[ix.contract].trim())throw Error('Contrato vacío');contracts.add(a[ix.contract].trim());}
      const r={date:date(a[ix.date]),symbol};r.time=r.date;
      for(const k of ['close','open','high','low','volume'])r[k]=ix[k]===undefined?null:number(a[ix[k]],sep);
      for(const k of ['close','open','high','low'])if(r[k]!==null&&r[k]<=0)throw Error('Precios no positivos no soportados: requiere tratamiento específico del instrumento');
      if(r.volume!==null&&r.volume<0)throw Error('Volumen negativo');
      if(r.high!==null&&r.high<Math.max(r.close,r.open??r.close,r.low??r.close))throw Error('Máximo OHLC incompatible');
      if(r.low!==null&&r.low>Math.min(r.close,r.open??r.close,r.high??r.close))throw Error('Mínimo OHLC incompatible');
      return r;
    }catch(e){throw Error(`Fila ${i+2}: ${e.message}`);}
  });
  if(symbols.size!==1)throw Error('El CSV mezcla símbolos');if(contracts.size>1)throw Error('Corte de contrato: separa contratos y documenta el rollover');
  const reordered=rows.some((r,i)=>i&&r.date<rows[i-1].date);rows.sort((a,b)=>a.date.localeCompare(b.date));
  let gaps=0,jumps=0;
  rows.forEach((r,i)=>{if(!i)return;const p=rows[i-1];if(p.date===r.date)throw Error('Fechas duplicadas: una vela diaria por instrumento');if((Date.parse(r.date)-Date.parse(p.date))/86400000>4)gaps++;if(Math.abs(r.close/p.close-1)>.3)jumps++;});
  const closes=rows.map(r=>r.close);let min=Infinity,max=0;for(const c of closes){min=Math.min(min,c);max=Math.max(max,c);}if(!Number.isFinite(100*(max/min-1)))throw Error('Rango de precios fuera de precisión numérica soportada');
  if(rows.length<(options.minRows??2))throw Error('Observaciones insuficientes');
  rows.meta={instrument:[...symbols][0],contract:[...contracts][0]||null,asof:rows.at(-1).date,first:rows[0].date,reordered,gaps,jumps,calendar:'no verificado',dateConvention:'ISO o DD/MM/AAAA; sesión declarada por proveedor'};
  return rows;
}
function stats(values){const a=values.filter(Number.isFinite),n=a.length;if(!n)return {n:0,avg:null,med:null,std:null,pos:0};const sorted=[...a].sort((a,b)=>a-b),avg=a.reduce((s,x)=>s+x,0)/n;return {n,avg,med:n%2?sorted[(n-1)/2]:(sorted[n/2-1]+sorted[n/2])/2,std:n>1?Math.sqrt(a.reduce((s,x)=>s+(x-avg)**2,0)/(n-1)):null,pos:a.filter(x=>x>0).length};}
function excursion(rows,index,n){
  if(index<0||index+n>=rows.length)return null;
  const base=rows[index].close,seg=rows.slice(index+1,index+n+1),ohlc=seg.every(r=>Number.isFinite(r.high)&&Number.isFinite(r.low));
  let peak=base,dd=0;for(const r of seg){peak=Math.max(peak,r.close);dd=Math.min(dd,100*(r.close/peak-1));}
  return {ret:100*(seg.at(-1).close/base-1),mae:ohlc?100*(Math.min(base,...seg.map(r=>r.low))/base-1):null,mfe:ohlc?100*(Math.max(base,...seg.map(r=>r.high))/base-1):null,dd,ohlc};
}
function study(rows,events,{complete=true,prior='all'}={}){
  if(!rows.length)return [];const result=[];
  for(const event of events){let i=-1;for(let j=0;j<rows.length&&rows[j].date<=event;j++)i=j;
    if(i<0||(Date.parse(event)-Date.parse(rows[i].date))/86400000>7)continue;
    if(complete&&i+126>=rows.length)continue;
    const close=rows[i].close,pre=n=>i>=n?100*(close/rows[i-n].close-1):null,pre20=pre(20);
    if(prior!=='all'&&(pre20===null||!(prior==='up'?pre20>2:prior==='down'?pre20< -2:Math.abs(pre20)<=2)))continue;
    const e={year:Number(event.slice(0,4)),event,anchor:rows[i].date,pre5:pre(5),pre20,complete:i+126<rows.length};
    for(const n of [1,5,20,63,126])e['p'+n]=excursion(rows,i,n)?.ret??null;
    e.v20=excursion(rows,i,20);e.v126=excursion(rows,i,126);result.push(e);
  }return result;
}
function monthly(rows){
  const map=new Map();for(const r of rows)map.set(r.date.slice(0,7),r);const months=[...map.entries()],out=[];
  for(let i=1;i<months.length;i++){const [ym,r]=months[i],[prev,p]=months[i-1];const diff=(+ym.slice(0,4)- +prev.slice(0,4))*12+(+ym.slice(5,7)- +prev.slice(5,7));
    // Candidate observations only: neither calendar completeness nor exchange closes are inferred.
    out.push({month:ym,anchor:p.date,end:r.date,ret:diff===1&&+r.date.slice(8)>=25&&+p.date.slice(8)>=25?100*(r.close/p.close-1):null,validated:false});
  }return out;
}
function csvCell(v){let s=String(v??'');if(/^[\s\uFEFF]*[=+@-]/.test(s)||/^[\t\r\n]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';}
function records(input){
  if(!Array.isArray(input))throw Error('Registros no válidos');const ids=new Set();
  return input.map(r=>{
    if(!r||typeof r!=='object'||!/^[-\w]{1,120}$/.test(r.id)||ids.has(r.id))throw Error('ID inválido o duplicado');ids.add(r.id);
    if(typeof r.date!=='string'||!/^\d{4}-\d{2}-\d{2}(?:T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?)?$/.test(r.date))throw Error('Fecha/hora de señal inválida');date(r.date.slice(0,10));
    for(const k of ['asset','currency','direction','status','state'])if(typeof r[k]!=='string'||!r[k].trim())throw Error('Campo obligatorio: '+k);
    if(!/^[A-Z0-9]{3,8}$/.test(r.currency)||!['long','short'].includes(r.direction)||!['operada','simulada','descartada','pendiente'].includes(r.status)||!['abierta','cerrada','descartada','pendiente'].includes(r.state))throw Error('Divisa, dirección o estado inválido');
    if((r.status==='descartada')!==(r.state==='descartada')||(r.status==='pendiente')!==(r.state==='pendiente'))throw Error('Estado incompatible');
    if(!Number.isFinite(r.mult)||r.mult<=0||!Number.isFinite(r.costs)||r.costs<0||!Array.isArray(r.legs))throw Error('Multiplicador, costes o ejecuciones inválidos');
    if(['descartada','pendiente'].includes(r.status)?r.legs.length!==0:r.legs.length===0)throw Error('Ejecuciones incompatibles con estado');
    for(const l of r.legs){if(!l||!['entry','stop','qty'].every(k=>Number.isFinite(l[k])&&l[k]>0))throw Error('Ejecución inválida');if(r.direction==='long'?l.stop>=l.entry:l.stop<=l.entry)throw Error('Stop incorrecto');if(r.state==='cerrada'?!(Number.isFinite(l.exit)&&l.exit>0):l.exit!==null)throw Error('Salida incompatible');if(l.date!==undefined&&typeof l.date!=='string')throw Error('Fecha de ejecución inválida');}
    for(const k of ['source','tf','strategy','setup','context','wyckoff','profile','zone','trigger','regime','decision','notes','session','entryStyle','marketRegime','sample','thesis','invalid1h','invalid5m','hypothesisOutcome','capture','plannedAt'])if(r[k]!==undefined&&typeof r[k]!=='string')throw Error('Texto inválido: '+k);
    validateResearch(r);const copy=JSON.parse(JSON.stringify(r));const m=metrics(copy);if(m&&![m.gross,m.net,m.risk,m.R].every(Number.isFinite))throw Error('Resultado fuera de rango');return copy;
  });
}
function metrics(r){if(['descartada','pendiente'].includes(r.status)||r.state!=='cerrada'||!r.legs.length)return null;const sign=r.direction==='long'?1:-1,gross=r.legs.reduce((s,l)=>s+sign*(l.exit-l.entry)*l.qty*r.mult,0),risk=r.legs.reduce((s,l)=>s+Math.abs(l.entry-l.stop)*l.qty*r.mult,0),net=gross-r.costs;return {gross,net,risk,R:risk>0?net/risk:null,win:net>0,breakeven:Math.abs(net)<1e-8};}
function rSummary(rows){const a=rows.map(metrics).filter(Boolean).map(x=>x.R).filter(Number.isFinite),wins=a.filter(x=>x>0),loss=a.filter(x=>x<0),gain=wins.reduce((x,y)=>x+y,0),lost=-loss.reduce((x,y)=>x+y,0);return {n:a.length,expectancy:a.length?a.reduce((x,y)=>x+y,0)/a.length:null,winRate:a.length?wins.length/a.length:null,profitFactor:lost?gain/lost:null};}
// Drawdown of cumulative closed-trade R, never account equity. Equal closes are grouped.
function researchSummary(rows){
 const closed=rows.filter(r=>r.status==='simulada'&&metrics(r));
 const eligible=closed.filter(r=>r.costBasis==='Completo');
 const result=rSummary(eligible);let equity=0,peak=0,dd=0;
 const dated=eligible.filter(r=>validClose(r.closedAt));
 const groups=new Map();for(const r of dated){const t=Date.parse(r.closedAt);groups.set(t,(groups.get(t)||0)+metrics(r).R);}
 for(const [,R] of [...groups].sort((a,b)=>a[0]-b[0])){equity+=R;peak=Math.max(peak,equity);dd=Math.max(dd,peak-equity);}
 return {...result,excluded:closed.length-eligible.length,drawdownR:eligible.length&&dated.length===eligible.length?dd:null,
 mae:stats(eligible.map(r=>r.maeR)).avg,mfe:stats(eligible.map(r=>r.mfeR)).avg,
 maeN:eligible.filter(r=>Number.isFinite(r.maeR)).length,mfeN:eligible.filter(r=>Number.isFinite(r.mfeR)).length};
}
function validClose(s){return typeof s==='string'&&/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)$/.test(s)&&Number.isFinite(Date.parse(s))&&(()=>{try{date(s.slice(0,10));return true;}catch{return false;}})();}
function validateResearch(r){
 for(const k of ['movement','hypothesisId','costBasis','closedAt','excursionSource','executionQuality','availableUntil'])if(r[k]!==undefined&&typeof r[k]!=='string')throw Error('Texto inválido: '+k);
 if(r.costBasis&&!['Completo','Parcial','Desconocido'].includes(r.costBasis))throw Error('Cobertura de costes inválida');
 if(r.closedAt&&!validClose(r.closedAt))throw Error('Cierre: usa fecha ISO con zona, por ejemplo 2026-11-14T16:00+01:00');
 for(const k of ['maeR','mfeR'])if(r[k]!=null&&(!Number.isFinite(r[k])||r[k]<0))throw Error('Excursión inválida: magnitud positiva en R');
 if((r.maeR!=null||r.mfeR!=null)&&!r.excursionSource?.trim())throw Error('Indica la fuente y ventana de MAE/MFE');
 if(r.initialPlan!==undefined&&(!r.initialPlan||typeof r.initialPlan!=='object'||Array.isArray(r.initialPlan)))throw Error('Plan inicial inválido');
}
const api={csv,date,prices,stats,excursion,study,monthly,csvCell,records,metrics,rSummary,researchSummary,validateResearch};if(typeof module!=='undefined')module.exports=api;root.AtlasCore=api;
})(typeof globalThis!=='undefined'?globalThis:this);
