from pathlib import Path
import re

p = Path("index.html")
html = p.read_text(encoding="utf-8")

# COT: there must be exactly one COT renderer. Remove any injected override
# between the COT professional marker and the Dark Pools renderer.
marker = "/* PROFESSIONAL INTERACTIVE CHARTS · COT + DARK POOLS */"
dp = "const __renderDarkPoolLegacy=renderDarkPoolSection;"
if marker in html and dp in html:
    a = html.find(marker)
    b = html.find(dp, a)
    if b > a:
        segment = html[a:b]
        segment = re.sub(r"renderCotSection=function\(\)\{[\\s\\S]*?\n\};\n?", "", segment)
        html = html[:a] + segment + html[b:]

# Options: explicit BTC/ETH selection must remain on that asset. For non-crypto
# assets we retain the old fallback-to-first-valid-chain behaviour.
opt_start = html.find("renderOptionsSection=function(){")
opt_end = html.find("\n};\n\n" + marker, opt_start)
if opt_start < 0 or opt_end < 0:
    raise SystemExit("ABORT: options renderer boundaries not found")

options = r"""renderOptionsSection=function(){
 const o=macroDatabase.__options||{},markets=o.markets||[];
 let selected=window.__optTicker||'SPX';
 selected=String(selected).toUpperCase();
 const explicitCrypto=(selected==='BTC'||selected==='ETH');
 let m=markets.find(x=>String(x.ticker||x.instrumentCode||'').toUpperCase()===selected)||null;
 if(!m && explicitCrypto){
  m=markets.find(x=>{
   const k=String(x.ticker||x.instrumentCode||'').toUpperCase();
   return k.startsWith(selected+'-')||k.startsWith(selected+'/');
  })||null;
 }
 if(!m)m={ticker:selected,instrumentCode:selected,name:selected,family:(o.catalog||[]).find(x=>x.code===selected)?.family||'Referencia',referenceOnly:true,profiles:[],dataStatus:'REFERENCIA · SIN CADENA COMPLETA',method:'Se mantiene el activo elegido. No hay cadena completa disponible; se muestran solo los datos públicos que existan.'};
 const p=(m.profiles||[])[0]||{};
 const chart=__optionsInteractiveHtml(m,p);
 const html=__renderOptionsLegacy();
 if(!chart)return html;
 const ps=o.providerStatus||{};
 const errText=(ps.errors||[]).slice(0,3).join(' · ');
 const diag='<div class="metric rounded-xl p-3 mt-3"><div class="flex flex-wrap items-center justify-between gap-2"><b class="text-xs text-white">ESTADO DE FUENTES · OPTIONS</b><span class="mini-pill">'+(Number(ps.fullChainMarkets)||0)+' cadenas completas / '+(Number(ps.referenceOnlyMarkets)||0)+' referencias</span></div><p class="text-[10px] text-gray-400 mt-2">Una referencia conserva el activo, pero no tiene cadena suficiente para calcular GEX, Max Pain u OI por strike. No equivale a una cadena vacía de mercado.</p>'+(errText?'<p class="text-[10px] text-amber-300 mt-2">Incidencias proveedor: '+esc(errText)+'</p>':'<p class="text-[10px] text-emerald-300 mt-2">Sin incidencias reportadas por el recolector.</p>')+'</div>';
 const marker='<div class="metric rounded-xl p-4"><b class="text-sm text-white">METODOLOGÍA</b>';
 const out=html.replace(marker,chart+diag+marker);
 setTimeout(()=>__drawOptionsCharts(m,p),80);
 return out;
};"""
html = html[:opt_start] + options + html[opt_end+3:]
# Patch the legacy options renderer too: its internal chainFirst fallback used
# to reselect BTC when ETH had no chain, undoing the explicit asset selection.
legacy_marker = "function renderOptionsSection(){"
legacy_start = html.find(legacy_marker)
legacy_end = html.find("const __renderOptionsLegacy", legacy_start)
if legacy_start >= 0 and legacy_end > legacy_start:
    legacy = html[legacy_start:legacy_end]
    legacy = re.sub(
        r"const current=\(window\.__optTicker&&markets\.find\(m=>\(m\.ticker\|\|m\.instrumentCode\)===window\.__optTicker\)\)\|\|null; const chainFirst=[\\s\\S]*?window\.__optTicker=selected;",
        """const wanted=String(window.__optTicker||'SPX').toUpperCase();
 const explicitCrypto=(wanted==='BTC'||wanted==='ETH');
 const current=markets.find(m=>String(m.ticker||m.instrumentCode||'').toUpperCase()===wanted)||markets.find(m=>{const k=String(m.ticker||m.instrumentCode||'').toUpperCase();return explicitCrypto&&(k.startsWith(wanted+'-')||k.startsWith(wanted+'/'));})||null;
 const selected=current?(current.ticker||current.instrumentCode):wanted;
 window.__optTicker=selected;""",
        legacy,
        count=1
    )
    html = html[:legacy_start] + legacy + html[legacy_end:]



# Options charts: separate GEX and Open Interest into independent panels.
chart_start = html.find("function __drawOptionsCharts(m,p){")
chart_end = html.find("\nrenderOptionsSection=function(){", chart_start)
if chart_start >= 0 and chart_end > chart_start:
    chart_fn = r"""function __drawOptionsCharts(m,p){
 const root=document.getElementById('sec-options');if(!root)return;
 const source=(Array.isArray(p?.strikeMap)&&p.strikeMap.length)?p.strikeMap:(Array.isArray(p?.topGexStrikes)?p.topGexStrikes:[]);
 const byStrike=new Map();
 for(const x of source){
  const strike=__optNum(x.strike);if(strike===null)continue;
  const q=byStrike.get(strike)||{strike,gex:0,callOi:0,putOi:0};
  q.gex+=__optNum(x.gex)||0;
  const typ=String(x.type||'').toUpperCase();
  if(typ==='C'||typ==='CALL')q.callOi+=__optNum(x.callOi??x.callOpenInterest??x.oi)||0;
  else if(typ==='P'||typ==='PUT')q.putOi+=__optNum(x.putOi??x.putOpenInterest??x.oi)||0;
  else{q.callOi+=__optNum(x.callOi??x.callOpenInterest)||0;q.putOi+=__optNum(x.putOi??x.putOpenInterest)||0;}
  byStrike.set(strike,q);
 }
 const raw=[...byStrike.values()].sort((a,b)=>a.strike-b.strike);
 const empty=(id,msg)=>{const el=document.getElementById(id);if(el)el.innerHTML='<div class="h-full min-h-[150px] flex items-center justify-center text-center text-xs text-gray-400 px-4">'+msg+'</div>';};
 const ivPct=v=>{let n=__optNum(v);if(n===null||n<=0)return null;if(n<3)n*=100;return n;};
 const term=(m.profiles||[]).map(q=>{
  const dte=__optNum(q.daysToExpiry);
  let iv=ivPct(q.ivAtm??q.atmIV??q.impliedVolatility??q.iv);
  if(iv===null){
   const spot=__optNum(m.spot??q.spot);
   const rows=(Array.isArray(q.strikeMap)&&q.strikeMap.length)?q.strikeMap:(q.topGexStrikes||[]);
   if(spot!==null&&rows.length){
    const calls=rows.filter(x=>['C','CALL'].includes(String(x.type||'').toUpperCase())&&ivPct(x.iv)!==null).sort((a,b)=>Math.abs(Number(a.strike)-spot)-Math.abs(Number(b.strike)-spot));
    const puts=rows.filter(x=>['P','PUT'].includes(String(x.type||'').toUpperCase())&&ivPct(x.iv)!==null).sort((a,b)=>Math.abs(Number(a.strike)-spot)-Math.abs(Number(b.strike)-spot));
    const vals=[calls[0]&&ivPct(calls[0].iv),puts[0]&&ivPct(puts[0].iv)].filter(x=>x!==null&&x!==undefined);
    if(vals.length)iv=vals.reduce((a,b)=>a+b,0)/vals.length;
   }
  }
  return {dte,iv,expiration:q.expiration||'—',bucket:q.bucket||'',source:q.source||m.source||''};
 }).filter(q=>q.dte!==null&&q.dte>=0&&q.iv!==null&&q.iv>0&&q.iv<500).sort((a,b)=>a.dte-b.dte);
 __loadPlotly().then(P=>{
  const cfg={responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d']};
  const spot=__optNum(m.spot),flip=__optNum(p?.gammaFlip??p?.zeroGamma),pain=__optNum(p?.maxPain),callWall=__optNum(p?.callWallOi??p?.callWall),putWall=__optNum(p?.putWallOi??p?.putWall);
  if(raw.length){
   const marks=[[spot,'Spot'],[flip,'Gamma Flip'],[pain,'Max Pain'],[callWall,'Call Wall'],[putWall,'Put Wall']];
   const shapes=marks.filter(x=>x[0]!==null).map(([v])=>({type:'line',x0:v,x1:v,y0:0,y1:1,yref:'paper',line:{color:'#94a3b8',width:1,dash:'dot'}}));
   const anns=marks.filter(x=>x[0]!==null).map(([v,label])=>({x:v,y:1.03,yref:'paper',text:label+' '+fmtNum(v,2),showarrow:false,font:{size:9,color:'#e2e8f0'}}));
   P.newPlot('opt-gex-chart',[{x:raw.map(x=>x.strike),y:raw.map(x=>x.gex),type:'bar',name:'GEX modelado',marker:{color:raw.map(x=>x.gex>=0?'#22c55e':'#f87171')},hovertemplate:'Strike %{x}<br>GEX %{y:.3s}<extra></extra>'}],{paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#cbd5e1',size:11},margin:{l:65,r:25,t:55,b:50},title:{text:'GEX por strike · exposición modelada',font:{size:13,color:'#f1f5f9'}},xaxis:{title:'Strike',gridcolor:'#334155',zerolinecolor:'#64748b'},yaxis:{title:'GEX',gridcolor:'#334155',zerolinecolor:'#64748b',separatethousands:true},shapes,annotations:anns,hovermode:'x unified'},cfg);
   P.newPlot('opt-oi-chart',[{x:raw.map(x=>x.strike),y:raw.map(x=>x.callOi),type:'scatter',mode:'lines+markers',name:'Call OI',line:{color:'#38bdf8',width:2.5},marker:{size:5},hovertemplate:'Strike %{x}<br>Call OI %{y:,.0f}<extra></extra>'},{x:raw.map(x=>x.strike),y:raw.map(x=>x.putOi),type:'scatter',mode:'lines+markers',name:'Put OI',line:{color:'#fb7185',width:2.5},marker:{size:5},hovertemplate:'Strike %{x}<br>Put OI %{y:,.0f}<extra></extra>'}],{paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#cbd5e1',size:11},margin:{l:65,r:25,t:45,b:50},title:{text:'Open interest por strike',font:{size:13,color:'#f1f5f9'}},xaxis:{title:'Strike',gridcolor:'#334155'},yaxis:{title:'Contratos OI',gridcolor:'#334155',separatethousands:true},hovermode:'x unified'},cfg);
  }else{
   empty('opt-gex-chart','Este activo no tiene una cadena completa de strikes disponible en el snapshot actual.');
   empty('opt-oi-chart','El gráfico de OI requiere datos por strike. Se conserva la selección del activo y no se sustituyen sus datos por Bitcoin.');
  }
  if(term.length){
   P.newPlot('opt-term-chart',[{x:term.map(q=>q.dte),y:term.map(q=>q.iv),type:'scatter',mode:'lines+markers',name:'ATM IV',line:{color:'#a78bfa',width:3},marker:{size:7,color:'#c4b5fd',line:{color:'#f8fafc',width:1}},customdata:term.map(q=>[q.expiration,q.bucket,q.source]),hovertemplate:'DTE %{x}<br>Expiración %{customdata[0]}<br>ATM IV %{y:.2f}%<br>%{customdata[1]}<extra></extra>'}],{paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#cbd5e1',size:11},margin:{l:55,r:20,t:45,b:55},title:{text:'Volatility term structure · ATM IV',font:{size:13,color:'#f1f5f9'}},xaxis:{title:'Días hasta expiración (DTE)',gridcolor:'#334155',zerolinecolor:'#64748b'},yaxis:{title:'Volatilidad implícita (%)',gridcolor:'#334155',rangemode:'tozero'},hovermode:'x unified'},cfg);
  }else{
   empty('opt-term-chart','No hay IV ATM verificable para varios vencimientos de este activo. La term structure permanecerá vacía hasta que exista una superficie de volatilidad válida; no se estiman puntos ficticios.');
  }
 }).catch(()=>{
  empty('opt-gex-chart','No se pudo cargar el motor gráfico. Recarga la página para reintentar.');
  empty('opt-oi-chart','No se pudo cargar el motor gráfico. Recarga la página para reintentar.');
  empty('opt-term-chart','No se pudo cargar el motor gráfico. Recarga la página para reintentar.');
 });
}
"""
    html = html[:chart_start] + chart_fn + html[chart_end:]
html = html.replace(
    '<div id="opt-gex-chart" class="w-full h-[470px] mt-2"></div><div class="metric rounded-xl p-4 mt-4">',
    '<div id="opt-gex-chart" class="w-full h-[390px] mt-2"></div><div id="opt-oi-chart" class="w-full h-[360px] mt-3"></div><div class="metric rounded-xl p-4 mt-4>',
    1
)

# Weekly Forex Radar: concise country-level bias + upcoming macro catalysts.
# This patch is idempotent because GitHub Actions reapplies it on every feed run.
weekly_js = r"""function renderWeeklyFxRadar(data){
 const codeMap={us:'USD',eu:'EUR',de:'EUR',uk:'GBP',jp:'JPY',ca:'CAD',au:'AUD',nz:'NZD',ch:'CHF'};
 const code=codeMap[data?.id]||'';
 const fx=macroDatabase.__fx||{},currency=fx.currencies?.[code]||{};
 const cal=macroDatabase.__economicCalendar||{},all=Array.isArray(cal.events)?cal.events:[];
 const matches=all.filter(e=>e.currency===code||e.economyId===data?.id||
  (code==='EUR'&&((data?.id==='eu'&&e.economyId==='de')||(data?.id==='de'&&e.economyId==='eu'))));
 const today=new Date().toISOString().slice(0,10);
 const weekEnd=new Date(Date.now()+7*86400000).toISOString().slice(0,10);
 const upcoming=matches.filter(e=>e.date&&e.date.slice(0,10)>=today&&e.date.slice(0,10)<=weekEnd)
  .sort((a,b)=>String(a.date).localeCompare(String(b.date))).slice(0,5);
 const recent=matches.filter(e=>e.actual!==''&&e.forecast!==''&&Number.isFinite(parseNum(e.actual))&&Number.isFinite(parseNum(e.forecast))&&e.date&&e.date.slice(0,10)<=today&&e.date.slice(0,10)>=new Date(Date.now()-7*86400000).toISOString().slice(0,10))
  .sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0,4);
 const freshIndicators=(data.indicators||[]).filter(ind=>{const t=Date.parse(String(ind.date||''));return Number.isFinite(t)&&t<=Date.now()+86400000&&t>=Date.now()-45*86400000;});
 const radarData={...data,indicators:freshIndicators,bonds:{...(data.bonds||{}),tenors:(data.bonds?.tenors||[]).map(t=>({...t,change:''}))}};
 const macro=macroInterpretation(radarData);
 const exp=Number(macro.exp)||0;
 const tenors=data.bonds?.tenors||[];
 const shortRows=['3M','1Y','2Y'].map(term=>tenors.find(x=>x.term===term)).filter(Boolean);
 const shortVals=shortRows.map(x=>x.change1wBp).filter(v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v))).map(Number);
 const shortBp=shortVals.length?shortVals.reduce((a,b)=>a+b,0)/shortVals.length:NaN;
 const shortOk=shortVals.length>0;
 const trendRaw=currency.change1w,trend=Number(trendRaw);
 const trendOk=trendRaw!==null&&trendRaw!==undefined&&trendRaw!==''&&Number.isFinite(trend);
 const regime=String(macroDatabase.__riskOnOff?.label||'').toUpperCase();
 const riskOn=regime.includes('RISK ON'),riskOff=regime.includes('RISK OFF');
 let score=(Number(macro.score)||0)*0.62+exp*1.55+(shortOk?Math.max(-1.2,Math.min(1.2,shortBp/8)):0)+(trendOk?Math.max(-1.3,Math.min(1.3,trend*0.65)):0);
 if(['AUD','NZD','CAD'].includes(code)){if(riskOn)score+=0.35;if(riskOff)score-=0.55;}
 if(['JPY','CHF'].includes(code)){if(riskOff)score+=0.65;if(riskOn)score-=0.25;}
 if(code==='USD'&&riskOff)score+=0.35;
 const label=fxBiasLabel(score),cls=fxBiasClass(score);
 const evidence=[trendOk,shortOk,freshIndicators.length>0,Math.abs(exp)>0.08,upcoming.length>0].filter(Boolean).length;
 const confidence=evidence>=4?'MEDIA · varias señales':evidence>=2?'BAJA-MEDIA · señales parciales':'BAJA · faltan confirmaciones';
 let baseline=null,biasChanged=false,scoreMoved=false;
 try{const now=new Date(),dow=(now.getUTCDay()+6)%7;now.setUTCDate(now.getUTCDate()-dow);now.setUTCHours(0,0,0,0);const wk=now.toISOString().slice(0,10),key='macroFxRadar:'+code+':'+wk;baseline=JSON.parse(localStorage.getItem(key)||'null');if(!baseline){baseline={score,label,capturedAt:new Date().toISOString()};localStorage.setItem(key,JSON.stringify(baseline));}else{biasChanged=baseline.label!==label;scoreMoved=Number.isFinite(Number(baseline.score))&&Math.abs(score-Number(baseline.score))>=0.9;}}catch(e){}
 const baselineLabel=baseline?.label||'Sin captura inicial';
 const baselineScore=baseline&&Number.isFinite(Number(baseline.score))?Number(baseline.score):null;
 const baselineDate=baseline?.capturedAt?new Date(baseline.capturedAt).toLocaleString('es-ES',{weekday:'short',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}):'primera lectura disponible';
 const revisionNote=biasChanged?'El sesgo cambió desde la lectura inicial de '+baselineLabel+' a '+label+'.':scoreMoved?'La presión monetaria se ha movido de forma material; comprobar si los bonos y la reacción del precio lo confirman.':'No hay cambio material confirmado respecto a la lectura inicial.';
 const weeklySummary='<div class="metric rounded-xl p-4"><div class="text-[10px] uppercase tracking-wider text-gray-500">Plan de la semana · hipótesis y revisión</div><div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-2"><div><div class="text-[9px] text-gray-500">LECTURA INICIAL GUARDADA</div><b class="text-xs text-white">'+esc(baselineLabel)+'</b><div class="text-[10px] text-gray-500 mt-1">'+esc(baselineDate)+'</div></div><div><div class="text-[9px] text-gray-500">SESGO ACTUAL</div><b class="text-xs '+cls+'">'+esc(label)+'</b><div class="text-[10px] text-gray-500 mt-1">'+(baselineScore!==null?'Índice del sesgo: '+baselineScore.toFixed(2)+' → '+Number(score).toFixed(2):'Sin puntuación inicial comparable')+'</div></div><div><div class="text-[9px] text-gray-500">REVISIÓN</div><div class="text-xs text-gray-200">'+esc(revisionNote)+'</div></div></div><p class="text-[10px] text-gray-500 mt-3">La lectura inicial se guarda en este navegador al abrir el radar por primera vez esa semana. Para que represente la preparación del domingo, conviene abrirlo ese día; no se reconstruye retrospectivamente si se abre por primera vez más tarde.</p></div>';
 const recentRows=recent.map(e=>{
  const d=indicatorDirection({name:e.event,actual:e.actual,est:e.forecast,cat:/cpi|inflation|pce|ppi|precios/i.test(e.event)?'INFLACIÓN':/unemployment|jobless|claims|desempleo|paro/i.test(e.event)?'EMPLEO':/gdp|pmi|retail|ventas|industrial|pib|ifo|tankan/i.test(e.event)?'CRECIMIENTO':'MACRO',imp:'★★★'});
  const surprise=d.score>0.15?'SORPRESA HAWKISH ↑':d.score< -0.15?'SORPRESA DOVISH ↓':'EN LÍNEA / MIXTA →';
  const tone=d.score>0.15?'effect-hawkish':d.score< -0.15?'effect-dovish':'effect-neutral';
  return '<div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 py-2 border-b border-gray-800/70"><div class="min-w-0"><div class="text-xs text-gray-200">'+esc(e.event)+'</div><div class="text-[10px] text-gray-500">'+esc(e.date||'')+' · Real '+esc(e.actual)+' / consenso '+esc(e.forecast)+'</div></div><span class="text-[10px] font-bold '+tone+'">'+surprise+'</span></div>';
 }).join('');
 const eventRows=upcoming.map(e=>'<div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 py-2 border-b border-gray-800/70"><div class="min-w-0"><div class="text-xs font-semibold text-gray-200">'+esc(e.event)+'</div><div class="text-[10px] text-gray-500">'+esc(e.date||'')+' · '+esc(e.country||code)+'</div></div><div class="text-[10px] text-gray-400 sm:text-right">Consenso: <b class="text-white">'+esc(e.forecast||'sin previsión')+'</b><div>Previo: '+esc(e.previous||'—')+'</div></div></div>').join('');
 const status=biasChanged?'SESGO REVISADO · cambió respecto a la lectura inicial':scoreMoved?'PRESIÓN MONETARIA CAMBIA · vigilar confirmación':recent.length?'DATOS RECIENTES · revisar reacción de mercado':'SESGO INICIAL / SIN CAMBIO MATERIAL';
 const statusCls=recent.length||biasChanged||scoreMoved?'text-amber-300':'text-blue-300';
 return '<section id="sec-fx-weekly" class="card rounded-2xl p-5 md:p-6 space-y-4"><div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3"><div><div class="text-[10px] uppercase tracking-wider text-gray-500">Forex Radar · semana en curso</div><h2 class="text-lg md:text-xl font-black text-white mt-1">Sesgo semanal de '+esc(code)+' · '+esc(data.name||'')+'</h2><p class="text-xs text-gray-400 mt-1 max-w-3xl">Hipótesis revisable, no señal automática de entrada. Prioriza la trayectoria esperada de tipos frente a lo que el mercado ya descuenta.</p></div><div class="metric rounded-xl p-3 min-w-[190px]"><div class="text-[10px] text-gray-500 uppercase">Sesgo provisional</div><div class="text-lg font-black '+cls+' mt-1">'+(score>=0.35?'↑ ':score<=-0.35?'↓ ':'→ ')+esc(label)+'</div><div class="text-[10px] text-gray-500 mt-1">Confianza: '+confidence+'</div></div></div><div class="flex flex-wrap gap-2 text-[10px]"><span class="mini-pill '+statusCls+'">'+status+'</span><span class="mini-pill">Risk '+(riskOn?'ON ↑':riskOff?'OFF ↓':'mixto / neutral')+'</span><span class="mini-pill">FX 1S '+(trendOk?fmtPct(trend):'N/D')+'</span><span class="mini-pill">Tramo corto 1S '+(shortOk?fmtPct(shortBp,1)+' pb':'N/D')+'</span></div>'+weeklySummary+'<div class="grid grid-cols-1 md:grid-cols-2 gap-4"><div class="metric rounded-xl p-4"><div class="text-[10px] uppercase tracking-wider text-gray-500">Por qué este sesgo</div><ul class="space-y-2 mt-3 text-xs text-gray-300"><li>• Política y datos macro: <b>'+esc(macro.label||'lectura mixta')+'</b>.</li><li>• Pricing de tipos: <b>'+esc(exp>0.08?'más presión de subidas':exp< -0.08?'más presión de bajadas':'sin dirección clara')+'</b>.</li><li>• Tramo corto 3M/1Y/2Y: '+(shortOk?(shortBp>0?'sube y puede confirmar más presión de tipos':'cae y puede señalar menos endurecimiento'):'variación semanal no disponible')+'.</li><li>• Tendencia de divisa 1S: '+(trendOk?(trend>0?'positiva':trend<0?'negativa':'plana'):'sin referencia verificada')+'; el riesgo global es una confirmación contextual, no una regla fija.</li></ul><p class="text-[10px] text-gray-500 mt-3">Lectura heurística: no se presenta como correlación estable ni como predicción garantizada.</p></div><div class="metric rounded-xl p-4"><div class="text-[10px] uppercase tracking-wider text-gray-500">Catalizadores · próximos 7 días</div>'+(eventRows||'<p class="text-xs text-gray-500 mt-3">No hay calendario futuro verificado disponible en el feed. No se muestran eventos inventados; revisar calendario oficial.</p>')+'</div></div>'+(recentRows?'<div class="metric rounded-xl p-4"><div class="text-[10px] uppercase tracking-wider text-gray-500">Datos publicados · posibles sorpresas</div>'+recentRows+'</div>':'')+'</section>';
}""";
if "function renderWeeklyFxRadar(data)" not in html:
    html = html.replace("function renderContent() {", weekly_js + "\nfunction renderContent() {", 1)
if "['sec-fx-weekly','FOREX RADAR']" not in html:
    html = html.replace("['sec-tipos','TIPOS']", "['sec-fx-weekly','FOREX RADAR'],['sec-tipos','TIPOS']", 1)
slot = "$" + "{renderWeeklyFxRadar(data)}"
if slot not in html:
    tick = chr(96)
    old = "container.innerHTML = " + tick + "\n                <div class=\"grid grid-cols-1 lg:grid-cols-3 gap-6\" id=\"sec-tipos\">"
    new = "container.innerHTML = " + tick + "\n                " + slot + "\n                <div class=\"grid grid-cols-1 lg:grid-cols-3 gap-6\" id=\"sec-tipos\">"
    html = html.replace(old, new, 1)
html = html.replace("const map={riskOnOff:'__riskOnOff'", "const map={economicCalendar:'__economicCalendar',riskOnOff:'__riskOnOff'", 1)
if "macroDatabase.__economicCalendar = macroDatabase.__economicCalendar ||" not in html:
    html = html.replace("macroDatabase.__riskOnOff = macroDatabase.__riskOnOff ||", "macroDatabase.__economicCalendar = macroDatabase.__economicCalendar || {events:[],dataStatus:'UNAVAILABLE'};\n        macroDatabase.__riskOnOff = macroDatabase.__riskOnOff ||", 1)


# Keep these data-quality and layout fixes persistent across automated feed refreshes.
old_pct = "function fmtPct(v,d=2){ const n=Number(v); return Number.isFinite(n)?(n>=0?'+':'')+n.toFixed(d)+'%':'—'; }"
new_pct = "function fmtPct(v,d=2){ if(v===null||v===undefined||v==='')return '—'; const n=Number(v); return Number.isFinite(n)?(n>=0?'+':'')+n.toFixed(d)+'%':'—'; }"
if old_pct in html: html = html.replace(old_pct, new_pct, 1)
old_num = "function fmtNum(v,d=2){ const n=Number(v); return Number.isFinite(n)?n.toFixed(d):'—'; }"
new_num = "function fmtNum(v,d=2){ if(v===null||v===undefined||v==='')return '—'; const n=Number(v); return Number.isFinite(n)?n.toFixed(d):'—'; }"
if old_num in html: html = html.replace(old_num, new_num, 1)
old_score = " const score=Number(fg.score), angle=Number.isFinite(score)?-90+score*1.8:-90, hist=(fg.history||[]).slice(-60);"
new_score = " const scoreRaw=fg.score,score=scoreRaw!==null&&scoreRaw!==undefined&&scoreRaw!==''&&Number.isFinite(Number(scoreRaw))&&Number(scoreRaw)>=0&&Number(scoreRaw)<=100?Number(scoreRaw):NaN,angle=Number.isFinite(score)?-90+score*1.8:-90,hist=(fg.history||[]).filter(x=>x&&x.value!==null&&x.value!==undefined&&x.value!==''&&Number.isFinite(Number(x.value))&&Number(x.value)>=0&&Number(x.value)<=100).slice(-60);"
if old_score in html: html = html.replace(old_score, new_score, 1)
old_lvl = " const lvl=v=>{const n=Number(v);return Number.isFinite(n)?fmtNum(n,2):'—';};"
new_lvl = " const lvl=v=>{if(v===null||v===undefined||v==='')return '—';const n=Number(v);return Number.isFinite(n)?fmtNum(n,2):'—';};"
if old_lvl in html: html = html.replace(old_lvl, new_lvl, 1)
if "new Date(Date.now()-3*86400000).toISOString().slice(0,10)" in html:
    html = html.replace("new Date(Date.now()-3*86400000).toISOString().slice(0,10)", "new Date(Date.now()-7*86400000).toISOString().slice(0,10)")
if "function renderCryptoBondSection(){" in html and "const compVal=k=>" not in html:
    marker_fg = " const levelPct=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v))?Number(v).toFixed(1)+'%':'—';"
    breadth_add = r""" 
 const compVal=k=>{const v=fg.components?.[k];return v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v))?Number(v):null;};
 const breadthProxy=macroDatabase.__rotation?.breadthProxy||{};
 const breadthCell=(label,value)=>'<div class="rounded-lg bg-slate-950/70 border border-gray-800 p-2"><div class="text-[9px] text-gray-500">'+label+'</div><b class="text-sm text-white">'+(value===null||value===undefined?'—':Number(value).toFixed(1)+' / 100')+'</b></div>';
 const relCell=(label,x)=>'<div class="rounded-lg bg-slate-950/70 border border-gray-800 p-2"><div class="text-[9px] text-gray-500">'+label+'</div><b class="text-xs '+(x!==undefined&&x!==null&&Number(x)>=0?'risk-up':'risk-down')+'">'+fmtPct(x,2)+'</b></div>';
 const breadthMini='<div class="space-y-2"><div class="text-[10px] uppercase tracking-wider text-gray-400">Amplitud y dispersión · contexto adicional</div><div class="grid grid-cols-2 gap-2">'+breadthCell('CNN · AMPLITUD',compVal('stock_price_breadth'))+breadthCell('CNN · FUERZA DE PRECIO',compVal('stock_price_strength'))+relCell('S&P 500 · RSP vs SPY · 5S',breadthProxy.sp500EqualWeightVsCap?.fiveSessionRelativePct)+relCell('Nasdaq · QQEW vs QQQ · 5S',breadthProxy.nasdaqEqualWeightVsCap?.fiveSessionRelativePct)+'</div><div class="text-[9px] text-gray-500">RSP/SPY y QQEW/QQQ miden si el índice equiponderado acompaña al ponderado por capitalización. No equivalen a un recuento de acciones.</div><div class="text-[9px] text-amber-300">Avances/descensos, % sobre medias de 50/200 días y nuevos máximos/mínimos: conteo exacto pendiente de una fuente pública verificable; no se sustituye por estimaciones.</div></div>';
"""
    if marker_fg in html: html = html.replace(marker_fg, marker_fg + breadth_add, 1)
old_gauge = """<div class="relative mt-4"><div class="sentiment-gauge"><div class="sentiment-needle" style="transform:rotate('+angle+'deg)"></div></div><div class="absolute inset-x-0 bottom-3 z-10 text-center"><b class="text-3xl text-white">'+(Number.isFinite(score)?score.toFixed(0):'—')+'</b><div class="text-xs text-gray-400 uppercase">'+esc(fg.rating||'—')+'</div></div></div><div class="grid grid-cols-4 gap-2 mt-3 text-center text-[10px]">"""
new_gauge = """<div class="grid grid-cols-1 md:grid-cols-[minmax(150px,0.85fr)_1fr] gap-3 items-center mt-3"><div class="relative mt-2"><div class="sentiment-gauge"><div class="sentiment-needle" style="transform:rotate('+angle+'deg)"></div></div><div class="absolute inset-x-0 bottom-3 z-10 text-center"><b class="text-3xl text-white">'+(Number.isFinite(score)?score.toFixed(0):'—')+'</b><div class="text-xs text-gray-400 uppercase">'+esc(Number.isFinite(score)?(fg.rating||'—'):'SIN DATO VÁLIDO')+'</div></div></div>'+breadthMini+'</div><div class="grid grid-cols-4 gap-2 mt-3 text-center text-[10px]">"""
if old_gauge in html and "breadthMini+'</div>" not in html: html = html.replace(old_gauge, new_gauge, 1)
html = html.replace("1D · 1S · 1M","1D · 5S · 21S")
html = html.replace("<th class=\"text-right py-2 px-2\">1S</th><th class=\"text-right py-2 px-2\">1M</th>","<th class=\"text-right py-2 px-2\">5S</th><th class=\"text-right py-2 px-2\">21S</th>")
html = html.replace("1D / 1S / 1M.","1D / 5 sesiones / 21 sesiones.")
html = html.replace("1D '+fmtPct(q.change1d)+' · 1S ","1D '+fmtPct(q.change1d)+' · 5S ")
html = html.replace(" · 1M '+fmtPct(q.change1m)"," · 21S '+fmtPct(q.change1m)")
html = html.replace("(x.change1w>=0?'risk-up':'risk-down')+'\">'+fmtPct(x.change3d)","(x.change3d>=0?'risk-up':'risk-down')+'\">'+fmtPct(x.change3d)")
html = html.replace("const lvl=v=>{const n=Number(v);return Number.isFinite(n)?fmtNum(n,2):'—';};","const lvl=v=>{if(v===null||v===undefined||v==='')return '—';const n=Number(v);return Number.isFinite(n)?fmtNum(n,2):'—';};")

p.write_text(html, encoding="utf-8")
print("UI fixes applied")
