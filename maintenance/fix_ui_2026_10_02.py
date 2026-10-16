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
p.write_text(html, encoding="utf-8")
print("UI fixes applied")
