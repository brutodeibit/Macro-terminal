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
 let selected=window.__optTicker||(markets[0]?.ticker||'SPY');
 selected=String(selected).toUpperCase();
 const explicitCrypto=(selected==='BTC'||selected==='ETH');
 let m=markets.find(x=>String(x.ticker||x.instrumentCode||'').toUpperCase()===selected)||null;
 if(!m && explicitCrypto){
  m=markets.find(x=>{
   const k=String(x.ticker||x.instrumentCode||'').toUpperCase();
   return k.startsWith(selected+'-')||k.startsWith(selected+'/');
  })||null;
 }
 if(!explicitCrypto && (!m||m.referenceOnly||!Array.isArray(m.profiles)||!m.profiles.length||!Array.isArray(m.profiles[0].topGexStrikes)||!m.profiles[0].topGexStrikes.length)){
  const first=__optionsChainMarket(markets);
  if(first){selected=first.ticker||first.instrumentCode;window.__optTicker=selected;m=first;}
 }
 if(!m)m={ticker:selected,instrumentCode:selected,profiles:[],dataStatus:'SIN CADENA PARA '+selected};
 const p=(m.profiles||[])[0]||{};
 const chart=__optionsInteractiveHtml(m,p);
 const html=__renderOptionsLegacy();
 if(!chart)return html;
 const marker='<div class="metric rounded-xl p-4"><b class="text-sm text-white">METODOLOGÍA</b>';
 const out=html.replace(marker,chart+marker);
 if(Array.isArray(p.topGexStrikes)&&p.topGexStrikes.length)setTimeout(()=>__drawOptionsCharts(m,p),80);
 return out;
};"""
html = html[:opt_start] + options + html[opt_end+3:]
// Patch the legacy options renderer too: its internal chainFirst fallback used
// to reselect BTC when ETH had no chain, undoing the explicit asset selection.
legacy_marker = "function renderOptionsSection(){"
legacy_start = html.find(legacy_marker)
legacy_end = html.find("const __renderOptionsLegacy", legacy_start)
if legacy_start >= 0 and legacy_end > legacy_start:
    legacy = html[legacy_start:legacy_end]
    legacy = re.sub(
        r"const current=\(window\.__optTicker&&markets\.find\(m=>\(m\.ticker\|\|m\.instrumentCode\)===window\.__optTicker\)\)\|\|null; const chainFirst=[\\s\\S]*?window\.__optTicker=selected;",
        """const wanted=String(window.__optTicker||'').toUpperCase();
 const explicitCrypto=(wanted==='BTC'||wanted==='ETH');
 const current=markets.find(m=>String(m.ticker||m.instrumentCode||'').toUpperCase()===wanted)||markets.find(m=>{const k=String(m.ticker||m.instrumentCode||'').toUpperCase();return explicitCrypto&&(k.startsWith(wanted+'-')||k.startsWith(wanted+'/'));})||null;
 const chainFirst=explicitCrypto?current:(markets.find(m=>!m.referenceOnly&&Array.isArray(m.profiles)&&m.profiles.length&&Array.isArray(m.profiles[0].topGexStrikes)&&m.profiles[0].topGexStrikes.length)||markets.find(m=>!m.referenceOnly&&Array.isArray(m.profiles)&&m.profiles.length)||markets[0]||null);
 const selected=current?(current.ticker||current.instrumentCode):(explicitCrypto?wanted:(chainFirst?.ticker||chainFirst?.instrumentCode||'SPY'));
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
 const raw=(p.strikeMap||[]).map(x=>({strike:__optNum(x.strike),gex:__optNum(x.gex)||0,callOi:__optNum(x.callOi)||0,putOi:__optNum(x.putOi)||0})).filter(x=>x.strike!==null).sort((a,b)=>a.strike-b.strike);
 if(!raw.length)return;
 __loadPlotly().then(P=>{
  const cfg={responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d']};
  const spot=__optNum(m.spot),flip=__optNum(p.gammaFlip??p.zeroGamma),pain=__optNum(p.maxPain),callWall=__optNum(p.callWall),putWall=__optNum(p.putWall);
  const marks=[[spot,'Spot'],[flip,'Gamma Flip'],[pain,'Max Pain'],[callWall,'Call Wall'],[putWall,'Put Wall']];
  const shapes=marks.filter(x=>x[0]!==null).map(([v])=>({type:'line',x0:v,x1:v,y0:0,y1:1,yref:'paper',line:{color:'#6b7280',width:1,dash:'dot'}}));
  const anns=marks.filter(x=>x[0]!==null).map(([v,label])=>({x:v,y:1.03,yref:'paper',text:label+' '+fmtNum(v,2),showarrow:false,font:{size:9,color:'#d1d5db'}}));
  P.newPlot('opt-gex-chart',[{x:raw.map(x=>x.strike),y:raw.map(x=>x.gex),type:'bar',name:'GEX',hovertemplate:'Strike %{x}<br>GEX %{y:.3s}<extra></extra>'}],{paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#9ca3af',size:10},margin:{l:65,r:25,t:55,b:50},title:{text:'GEX por strike · escala independiente',font:{size:13,color:'#e5e7eb'}},xaxis:{title:'Strike',gridcolor:'#1f2937'},yaxis:{title:'GEX',gridcolor:'#1f2937',separatethousands:true},shapes,annotations:anns,hovermode:'x unified'},cfg);
  P.newPlot('opt-oi-chart',[{x:raw.map(x=>x.strike),y:raw.map(x=>x.callOi),type:'scatter',mode:'lines+markers',name:'Call OI',hovertemplate:'Strike %{x}<br>Call OI %{y:,.0f}<extra></extra>'},{x:raw.map(x=>x.strike),y:raw.map(x=>x.putOi),type:'scatter',mode:'lines+markers',name:'Put OI',hovertemplate:'Strike %{x}<br>Put OI %{y:,.0f}<extra></extra>'}],{paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#9ca3af',size:10},margin:{l:65,r:25,t:45,b:50},title:{text:'Open Interest por strike · escala OI',font:{size:13,color:'#e5e7eb'}},xaxis:{title:'Strike',gridcolor:'#1f2937'},yaxis:{title:'Contratos OI',gridcolor:'#1f2937',separatethousands:true},hovermode:'x unified'},cfg);
  const profiles=(m.profiles||[]).filter(q=>__optNum(q.daysToExpiry)!==null&&__optNum(q.ivAtm)!==null);
  if(profiles.length)P.newPlot('opt-term-chart',[{x:profiles.map(q=>q.daysToExpiry),y:profiles.map(q=>q.ivAtm),type:'scatter',mode:'lines+markers',name:'ATM IV',hovertemplate:'DTE %{x}<br>Expira %{customdata}<br>ATM IV %{y:.2f}%<extra></extra>',customdata:profiles.map(q=>q.expiration||'—')}],{paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:'#9ca3af',size:10},margin:{l:55,r:20,t:45,b:50},title:{text:'ATM IV por vencimiento',font:{size:13,color:'#e5e7eb'}},xaxis:{title:'Días hasta expiración (DTE)',gridcolor:'#1f2937'},yaxis:{title:'IV %',gridcolor:'#1f2937'},hovermode:'x unified'},cfg);
 }).catch(()=>{});
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
