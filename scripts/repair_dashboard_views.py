from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_function(text, name, replacement, next_name):
    pattern = rf"function {name}\(\)\{{.*?\n        \}}\n\n        function {next_name}"
    new, count = re.subn(pattern, replacement.rstrip() + f"\n\n        function {next_name}", text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"Could not replace {name} -> {next_name}; matches={count}")
    return new


def repair_python():
    p = ROOT / "market_features.py"
    s = p.read_text(encoding="utf-8")
    if "def _option_risk_metrics" not in s:
        helper = r'''
def _option_risk_metrics(rows, spot):
 """Derived chain metrics; descriptive calculations, not dealer-book data."""
 calls=[x for x in rows if x.get("type")=="C"]
 puts=[x for x in rows if x.get("type")=="P"]
 def oi(items, predicate):
  return sum(float(x.get("openInterest") or 0) for x in items if predicate(float(x.get("strike") or 0)))
 total=sum(float(x.get("openInterest") or 0) for x in rows)
 above=oi(rows,lambda k:k>spot); below=oi(rows,lambda k:k<spot); at=oi(rows,lambda k:abs(k-spot)<max(spot*0.005,0.01))
 def nearest_delta(items, target):
  valid=[x for x in items if x.get("delta") is not None and x.get("iv") is not None and abs(abs(float(x.get("delta"))) - target)<=0.12]
  return min(valid,key=lambda x:abs(abs(float(x.get("delta")))-target)) if valid else None
 c25=nearest_delta(calls,0.25); p25=nearest_delta(puts,0.25)
 civ=float(c25.get("iv") or 0) if c25 else None; piv=float(p25.get("iv") or 0) if p25 else None
 if civ and civ<3:civ*=100
 if piv and piv<3:piv*=100
 return {
  "oiAboveSpot":above,"oiBelowSpot":below,"oiAtSpot":at,
  "oiAbovePct":above/total*100 if total else None,
  "oiBelowPct":below/total*100 if total else None,
  "oiAtPct":at/total*100 if total else None,
  "call25dIv":civ,"put25dIv":piv,
  "skew25d":(piv-civ) if piv is not None and civ is not None else None,
  "riskReversal25d":(civ-piv) if piv is not None and civ is not None else None,
  "call25dStrike":c25.get("strike") if c25 else None,
  "put25dStrike":p25.get("strike") if p25 else None,
 }
'''
        s = s.replace("def _option_summary(rows,spot,expiration,oi_prev=None):", helper + "\n\ndef _option_summary(rows,spot,expiration,oi_prev=None):", 1)
    marker = '"topGexStrikes":sorted(gex_by,key=lambda z:abs(z["gex"]),reverse=True)[:10]'
    if '"oiAboveSpot"' not in s:
        s = s.replace(marker, marker + ',\n  **_option_risk_metrics(rows,spot)', 1)
    p.write_text(s, encoding="utf-8")


def repair_html():
    p = ROOT / "index.html"
    s = p.read_text(encoding="utf-8")
    options = r'''function renderOptionsSection(){
            const o=macroDatabase.__options||{updated:'—',markets:[]};
            const markets=o.markets||[];
            const keys=markets.map(m=>m.ticker||m.name).filter(Boolean);
            const selected=(window.__optTicker&&markets.find(m=>(m.ticker||m.name)===window.__optTicker))?window.__optTicker:(keys[0]||'SPY');
            window.__optTicker=selected;
            const m=markets.find(x=>(x.ticker||x.name)===selected)||{};
            const profiles=m.profiles||[];
            const p=profiles[0]||m;
            const pm=profiles[1]||{};
            const finite=v=>Number.isFinite(Number(v));
            const value=(v,d=2)=>finite(v)?fmtNum(v,d):'No disponible';
            const level=(v)=>finite(v)?fmtNum(v,2)+' · '+fmtNum(Number(v)-Number(m.spot),2)+' ('+fmtPct(Number(v)/Number(m.spot)*100-100,2)+')':'No disponible';
            const metric=(label,main,sub='',tone='text-white')=>'<div class="metric p-4"><div class="text-[10px] uppercase tracking-wider text-gray-400">'+label+'</div><b class="block text-xl mt-1 '+tone+'">'+main+'</b>'+(sub?'<div class="text-[10px] text-gray-300 mt-1">'+sub+'</div>':'')+'</div>';
            const rows=(p.topGexStrikes||[]).slice(0,16);
            const maxG=Math.max(...rows.map(x=>Math.abs(Number(x.gex)||0)),1);
            const bars=rows.map(x=>{const g=Number(x.gex)||0;const w=Math.max(3,Math.round(Math.abs(g)/maxG*100));return '<div class="grid grid-cols-[52px_1fr_90px] items-center gap-2 text-xs"><span class="text-right text-gray-200">'+fmtNum(x.strike,0)+'</span><div class="h-3 rounded bg-gray-800 overflow-hidden"><div class="h-3 rounded '+(g>=0?'bg-emerald-400':'bg-red-400')+'" style="width:'+w+'%"></div></div><span class="text-right '+(g>=0?'text-emerald-300':'text-red-300')+'">'+fmtCompactMoney(g)+'</span></div>';}).join('');
            const select=keys.map(k=>'<option value="'+esc(k)+'" '+(k===selected?'selected':'')+'>'+esc(k)+' · '+esc(instrumentName(k))+'</option>').join('');
            const profileCards=profiles.map((q,i)=>'<div class="metric rounded-xl p-4"><div class="flex justify-between gap-2"><b class="text-sm text-white">'+(i===0?'PRÓXIMO VENCIMIENTO':'VENCIMIENTO MENSUAL')+'</b><span class="mini-pill">'+esc(q.expiration||'—')+' · '+value(q.daysToExpiry,1)+' días</span></div><div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 text-xs"><div><span class="text-gray-400">Max Pain</span><b class="block text-white">'+level(q.maxPain)+'</b></div><div><span class="text-gray-400">Gamma Flip</span><b class="block text-white">'+level(q.gammaFlip??q.zeroGamma)+'</b></div><div><span class="text-gray-400">Call Wall</span><b class="block text-white">'+value(q.callWall,2)+'</b></div><div><span class="text-gray-400">Put Wall</span><b class="block text-white">'+value(q.putWall,2)+'</b></div><div><span class="text-gray-400">ATM IV</span><b class="block text-white">'+value(q.ivAtm,2)+'%</b></div><div><span class="text-gray-400">Expected Move</span><b class="block text-white">'+(finite(q.expectedMove)?'±'+value(q.expectedMove,2)+' ('+value(q.expectedMovePct,2)+'%)':'No disponible: IV insuficiente')+'</b></div><div><span class="text-gray-400">25D skew</span><b class="block text-white">'+value(q.skew25d,2)+' pp</b></div><div><span class="text-gray-400">OI above / below</span><b class="block text-white">'+value(q.oiAbovePct,1)+'% / '+value(q.oiBelowPct,1)+'%</b></div><div><span class="text-gray-400">GEX neto</span><b class="block '+(Number(q.gammaNet)>=0?'text-emerald-300':'text-red-300')+'">'+fmtCompactMoney(q.gammaNet)+'</b></div><div><span class="text-gray-400">Régimen gamma</span><b class="block text-white">'+esc(q.gammaRegime||'No disponible')+'</b></div><div><span class="text-gray-400">DEX proxy</span><b class="block text-white">'+fmtCompactMoney(q.dexProxy)+'</b></div><div><span class="text-gray-400">Vanna / Charm</span><b class="block text-white">'+fmtCompactMoney(q.vannaProxy)+' / '+fmtCompactMoney(q.charm)+'</b></div></div></div>').join('');
            return '<section id="sec-options" class="space-y-4"><div class="glass rounded-2xl p-5"><div class="flex flex-col md:flex-row md:items-center justify-between gap-3"><div><div class="text-[10px] uppercase tracking-wider text-gray-400">OPTIONS DESK · CADENA PÚBLICA RETRASADA</div><h2 class="text-xl font-black text-white mt-1">OPTIONS · RIESGO Y CONCENTRACIÓN</h2><p class="text-sm text-gray-300 mt-1">Max Pain y OI son descriptivos; Gamma Flip, GEX, DEX, Vanna y Charm son cálculos/proxies y no representan el libro real de dealers.</p><p class="text-[10px] text-gray-400 mt-1">Actualizado: '+esc(o.updated||'—')+' · Fuente: '+esc(m.source||o.source||'fuente no indicada')+'</p></div><select onchange="window.__optTicker=this.value;renderContent()" class="bg-gray-900 border border-gray-600 text-white rounded-lg px-3 py-2">'+select+'</select></div><div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mt-4">'+metric('Spot observado',value(m.spot),'Precio de referencia')+metric('Max Pain · OI',level(p.maxPain),'Strike · distancia al spot')+metric('Gamma Flip · proxy',level(p.gammaFlip??p.zeroGamma),'Modelo calculado')+metric('GEX neto · modelado',fmtCompactMoney(p.gammaNet),p.gammaRegime||'',''+(Number(p.gammaNet)>=0?'text-emerald-300':'text-red-300'))+metric('Expected Move',finite(p.expectedMove)?'±'+value(p.expectedMove,2):'No disponible','Requiere IV y vencimiento válidos')+metric('ATM IV observada',finite(p.ivAtm)?value(p.ivAtm,2)+'%':'No disponible','Volatilidad implícita')+'</div></div><div class="grid grid-cols-1 xl:grid-cols-[1.55fr_1fr] gap-4"><div class="metric rounded-xl p-5"><div class="flex justify-between items-center gap-2"><div><b class="text-sm text-white">'+esc(selected)+' · GEX POR STRIKE</b><div class="text-[10px] text-gray-400 mt-1">Concentración de exposición estimada; barras más largas = mayor magnitud absoluta.</div></div><span class="mini-pill">'+esc(p.expiration||'—')+'</span></div><div class="space-y-3 mt-5">'+(bars||'<div class="text-xs text-gray-400">No hay desglose por strike disponible en la fuente actual.</div>')+'</div><div class="flex flex-wrap gap-4 mt-4 text-[10px]"><span class="text-emerald-300">● Gamma positivo · posible amortiguación</span><span class="text-red-300">● Gamma negativo · posible amplificación</span></div></div><div class="metric rounded-xl p-5"><b class="text-sm text-white">NIVELES Y DISTRIBUCIÓN DE OI</b><div class="grid grid-cols-2 gap-3 mt-4">'+['Max Pain|'+level(p.maxPain),'Call Wall|'+value(p.callWall,2),'Put Wall|'+value(p.putWall,2),'Gamma Flip|'+level(p.gammaFlip??p.zeroGamma),'OI sobre spot|'+value(p.oiAbovePct,1)+'%','OI bajo spot|'+value(p.oiBelowPct,1)+'%','25D skew|'+value(p.skew25d,2)+' pp','P/C OI|'+value(p.putCallOi,2)].map(x=>{const z=x.split('|');return '<div class="p-3 rounded-lg bg-gray-900 border border-gray-800"><div class="text-[10px] text-gray-400">'+z[0]+'</div><b class="block text-white mt-1">'+z[1]+'</b></div>';}).join('')+'</div></div></div><div class="space-y-4">'+profileCards+'</div></section>';
        }'''
    cot = r'''function renderCotSection(){
            const c=macroDatabase.__cot||{updated:'—',markets:[]}; const markets=c.markets||[];
            const keys=markets.map(m=>m.name).filter(Boolean); const selected=(window.__cotMarket&&markets.find(m=>m.name===window.__cotMarket))?window.__cotMarket:(keys[0]||''); window.__cotMarket=selected;
            const m=markets.find(x=>x.name===selected)||markets[0]||{}; const history=m.history||[]; const range=window.__cotRange||52; const visible=history.slice(0,range).reverse();
            const ni=v=>Number.isFinite(Number(v))?Number(v).toLocaleString('es-ES'):'—'; const sg=v=>Number.isFinite(Number(v))?(Number(v)>=0?'+':'')+Number(v).toLocaleString('es-ES'):'—'; const pc=v=>Number.isFinite(Number(v))?Number(v).toFixed(1)+'%':'—';
            const nums=history.map(x=>Number(x.net)).filter(Number.isFinite); const lo=nums.length?Math.min(...nums):0,hi=nums.length?Math.max(...nums):1,span=Math.max(hi-lo,1); const W=980,H=360,L=72,R=24,T=28,B=62;
            const px=i=>L+i*(W-L-R)/Math.max(visible.length-1,1); const py=v=>T+(hi-v)*(H-T-B)/span; const points=visible.map((x,i)=>px(i).toFixed(1)+','+py(Number(x.net)).toFixed(1)).join(' ');
            const ticks=[0,.2,.4,.6,.8,1].map(t=>{const y=T+t*(H-T-B);const v=hi-t*span;return '<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y+'" y2="'+y+'" stroke="#263244" stroke-dasharray="3 5"/><text x="'+(L-10)+'" y="'+(y+4)+'" text-anchor="end" fill="#cbd5e1" font-size="11">'+ni(v)+'</text>';}).join('');
            const labels=visible.map((x,i)=>{if(i!==0&&i!==visible.length-1&&i%Math.max(1,Math.floor(visible.length/6))!==0)return '';return '<text x="'+px(i)+'" y="'+(H-26)+'" text-anchor="middle" fill="#cbd5e1" font-size="10">'+esc(x.date)+'</text>';}).join('');
            const dots=visible.map((x,i)=>'<circle cx="'+px(i)+'" cy="'+py(Number(x.net))+'" r="4" fill="#facc15" stroke="#111827" stroke-width="1.5"><title>'+esc(x.date)+' · Neto '+ni(x.net)+' · Largos '+ni(x.long)+' · Cortos '+ni(x.short)+'</title></circle>').join('');
            const chart=visible.length>1?'<svg viewBox="0 0 '+W+' '+H+'" class="w-full h-[360px]">'+ticks+'<polyline points="'+points+'" fill="none" stroke="#facc15" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'+dots+labels+'</svg>':'<div class="h-[360px] flex items-center justify-center text-xs text-gray-400">Histórico COT insuficiente.</div>';
            const selector=keys.map(k=>'<option value="'+esc(k)+'" '+(k===selected?'selected':'')+'>'+esc(k)+'</option>').join(''); const ranges=[4,13,26,52,104,260].map(n=>'<button onclick="window.__cotRange='+n+';renderContent()" class="mini-pill">'+(n===4?'4S':n===13?'13S':n===26?'26S':n===52?'52S':n===104?'2A':'5A')+'</button>').join('');
            const table=visible.slice().reverse().slice(0,range).map(x=>'<tr class="border-b border-gray-800"><td class="py-2 px-2 text-xs text-gray-200">'+esc(x.date)+'</td><td class="py-2 px-2 text-xs text-right">'+ni(x.long)+'</td><td class="py-2 px-2 text-xs text-right">'+ni(x.short)+'</td><td class="py-2 px-2 text-xs text-right font-bold '+(Number(x.net)>=0?'text-emerald-300':'text-red-300')+'">'+sg(x.net)+'</td></tr>').join('');
            return '<section id="sec-cot" class="space-y-4"><div class="glass rounded-2xl p-5"><div class="flex flex-col lg:flex-row lg:items-center justify-between gap-3"><div><div class="text-[10px] uppercase tracking-wider text-gray-400">CFTC · POSICIONAMIENTO SEMANAL</div><h2 class="text-xl font-black text-white mt-1">COT · FUTURES</h2><p class="text-sm text-gray-300 mt-1">Neto = largos menos cortos de la categoría seleccionada. El gráfico muestra cada observación semanal con fecha y tooltip.</p></div><div class="flex items-center gap-2"><span class="mini-pill">Actualizado '+esc(c.updated||'—')+'</span><select onchange="window.__cotMarket=this.value;renderContent()" class="bg-gray-900 border border-gray-600 text-white rounded-lg px-3 py-2">'+selector+'</select></div></div></div><div class="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3">'+[['NETO',sg(m.net)],['LARGOS',ni(m.long)],['CORTOS',ni(m.short)],['Δ 1 SEM.',sg(m.change1w??m.netChange)],['Δ 4 SEM.',sg(m.change4w)],['% OI',pc(m.netPctOI)],['PERCENTIL 52S',pc(m.percentile52)],['Z · 52S',Number.isFinite(Number(m.z52??m.zScore))?Number(m.z52??m.zScore).toFixed(2)+'σ':'—']].map(x=>'<div class="metric p-3"><span class="text-[10px] text-gray-400">'+x[0]+'</span><b class="block text-lg text-white mt-1">'+x[1]+'</b></div>').join('')+'</div><div class="metric rounded-xl p-5"><div class="flex flex-wrap items-center justify-between gap-3"><div><b class="text-sm text-white">'+esc(m.name||'')+' · NET POSITIONING</b><div class="text-[10px] text-gray-400 mt-1">Informe '+esc(m.reportDate||'—')+' · '+esc(m.traderGroup||'')+' · '+esc(m.reportFamily||'')+'</div></div><div class="flex flex-wrap gap-1">'+ranges+'</div></div>'+chart+'<div class="text-[10px] text-gray-400">Amarillo = neto semanal. Pasa el cursor por cada punto para ver fecha, largos, cortos y neto.</div></div><div class="metric rounded-xl p-5 overflow-x-auto"><div class="flex items-center justify-between gap-3 mb-3"><b class="text-sm text-white">HISTÓRICO VISIBLE</b><span class="mini-pill">'+range+' observaciones máximas</span></div><table class="w-full min-w-[520px]"><thead><tr class="border-b border-gray-700 text-[10px] text-gray-400 uppercase"><th class="text-left py-2 px-2">Semana</th><th class="text-right py-2 px-2">Largos</th><th class="text-right py-2 px-2">Cortos</th><th class="text-right py-2 px-2">Neto</th></tr></thead><tbody>'+table+'</tbody></table></div></section>';
        }'''
    dark = r'''function renderDarkPoolSection(){
 const t=macroDatabase.__darkPoolPrints||{assets:{},prints:[]},assets=t.assets||{},keys=Object.keys(assets); const selected=(window.__darkPoolTicker&&assets[window.__darkPoolTicker])?window.__darkPoolTicker:(keys[0]||'SPY'); window.__darkPoolTicker=selected;
 const a=assets[selected]||{ticker:selected,lastPrice:null,priceSeries:[],prints:[],venueClusters:[],dailyOffExchange:{}},ps=a.priceSeries||[]; const W=1000,H=420,L=68,R=28,T=28,B=62;
 const lo=ps.length?Math.min(...ps.map(x=>+x.price)):0,hi=ps.length?Math.max(...ps.map(x=>+x.price)):1,pad=(hi-lo||1)*.12,y0=lo-pad,y1=hi+pad; const minTs=ps.length?Math.min(...ps.map(p=>+p.ts)):0,maxTs=ps.length?Math.max(...ps.map(p=>+p.ts)):1,span=Math.max(maxTs-minTs,1);
 const x=t=>L+(t-minTs)*(W-L-R)/span; const y=v=>H-B-(v-y0)/(y1-y0)*(H-T-B); const path=ps.map((p,i)=>(i?'L':'M')+x(+p.ts).toFixed(1)+' '+y(+p.price).toFixed(1)).join(' ');
 const grid=[0,.25,.5,.75,1].map(t=>{const yy=T+t*(H-T-B),v=y1-t*(y1-y0);return '<line x1="'+L+'" x2="'+(W-R)+'" y1="'+yy+'" y2="'+yy+'" stroke="#263244" stroke-dasharray="3 5"/><text x="'+(L-10)+'" y="'+(yy+4)+'" text-anchor="end" fill="#cbd5e1" font-size="11">'+fmtNum(v,2)+'</text>';}).join('');
 const xlabels=ps.filter((p,i)=>i===0||i===ps.length-1||i%Math.max(1,Math.floor(ps.length/6))===0).map(p=>'<text x="'+x(+p.ts)+'" y="'+(H-24)+'" text-anchor="middle" fill="#cbd5e1" font-size="10">'+esc(new Date(+p.ts*1000).toLocaleDateString('es-ES',{day:'2-digit',month:'2-digit'}))+'</text>').join('');
 const dots=(a.prints||[]).map((p,i)=>{const q=Number.isFinite(+p.price)?+p.price:+p.priceApprox;const xx=Number.isFinite(+p.approxTs)?x(+p.approxTs):L+(i%Math.max(ps.length,1))*(W-L-R)/Math.max(ps.length-1,1);const yy=Number.isFinite(q)?y(q):(H+T)/2;const c=p.side==='BUY'?'#34d399':p.side==='SELL'?'#f87171':'#facc15';const r=Math.max(5,Math.min(18,Math.sqrt(Math.max(+p.size||1000,1))/8));return '<circle cx="'+xx.toFixed(1)+'" cy="'+yy.toFixed(1)+'" r="'+r.toFixed(1)+'" fill="'+c+'" stroke="#ffffff" stroke-opacity=".75"><title>'+esc(p.timestamp||'')+' · '+esc(p.side||'PRINT')+' · '+fmtNum(q,2)+' · '+(+p.size||0).toLocaleString('es-ES')+' acciones</title></circle>';}).join('');
 const svg=ps.length?'<svg viewBox="0 0 '+W+' '+H+'" class="w-full h-[420px]">'+grid+'<path d="'+path+'" fill="none" stroke="#60a5fa" stroke-width="2.5"/>'+dots+xlabels+'</svg>':'<div class="h-[420px] flex items-center justify-center text-gray-400">Sin serie de precio publicada.</div>';
 const sel=keys.map(k=>'<option value="'+esc(k)+'" '+(k===selected?'selected':'')+'>'+esc(k)+' · '+esc(instrumentName(k))+'</option>').join(''); const dpx=a.dailyOffExchange||{};
 const rows=(a.prints||[]).slice(0,100).map(p=>'<tr class="border-b border-gray-800"><td class="py-2 px-2 text-xs '+(p.side==='BUY'?'text-emerald-300':p.side==='SELL'?'text-red-300':'text-yellow-300')+'">'+esc(p.side||'PRINT')+'</td><td class="py-2 px-2 text-xs text-gray-300">'+esc(p.timestamp||'—')+'</td><td class="py-2 px-2 text-xs text-right text-white">'+(+p.size||0).toLocaleString('es-ES')+'</td><td class="py-2 px-2 text-xs text-right text-white">'+fmtNum(p.price||p.priceApprox,2)+'</td><td class="py-2 px-2 text-xs text-right text-gray-300">'+fmtCompactMoney(p.notional||((p.price||p.priceApprox||0)*(p.size||0)))+'</td></tr>').join('');
 return '<section id="sec-darkpool" class="space-y-4"><div class="glass rounded-2xl p-5"><div class="flex justify-between items-center gap-3"><div><div class="text-[10px] uppercase tracking-wider text-gray-400">INSTITUTIONAL FLOW DESK</div><h2 class="text-xl font-black text-white mt-1">DARK POOLS · '+esc(selected)+'</h2><p class="text-sm text-gray-300 mt-1">Precio, tiempo y prints visibles. El color identifica BUY, SELL o print sin lado confirmado.</p></div><select onchange="window.__darkPoolTicker=this.value;renderContent()" class="bg-gray-900 border border-gray-600 text-white rounded-lg px-3 py-2">'+sel+'</select></div><div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">'+[['PRECIO',fmtNum(a.lastPrice,2)],['PRINTS',a.printCount||0],['SHARES',(+a.shareCount||0).toLocaleString('es-ES')],['NOTIONAL',fmtCompactMoney(a.notional)],['OFF-EXCHANGE',Number.isFinite(+dpx.offExchangePct)?(+dpx.offExchangePct).toFixed(1)+'%':'No disponible'].map(x=>'<div class="metric p-3"><span class="text-[10px] text-gray-400">'+x[0]+'</span><b class="block text-lg text-white mt-1">'+x[1]+'</b></div>').join('')+'</div></div><div class="metric rounded-xl p-4"><b class="text-sm text-white">PRECIO / PRINTS · EJE TEMPORAL Y PRECIO</b>'+svg+'<div class="flex flex-wrap gap-4 text-[10px] mt-2"><span class="text-emerald-300">● BUY</span><span class="text-red-300">● SELL</span><span class="text-yellow-300">● SIN LADO CONFIRMADO</span></div><p class="text-[10px] text-gray-400 mt-2">Un print fuera de mercado no demuestra por sí solo acumulación institucional ni identifica al comprador final.</p></div><div class="metric rounded-xl p-4 overflow-x-auto"><b class="text-sm text-white">PRINTS VISIBLES · TABLA</b><table class="w-full min-w-[650px] mt-3"><thead><tr class="border-b border-gray-700 text-[10px] text-gray-400 uppercase"><th class="text-left py-2 px-2">Lado</th><th class="text-left py-2 px-2">Fecha / hora</th><th class="text-right py-2 px-2">Acciones</th><th class="text-right py-2 px-2">Precio</th><th class="text-right py-2 px-2">Notional</th></tr></thead><tbody>'+(rows||'<tr><td colspan="5" class="py-3 text-xs text-gray-400">No hay prints individuales publicados.</td></tr>')+'</tbody></table></div></section>';
}'''
    s = replace_function(s, 'renderCotSection', cot, 'renderOptionsSection')
    s = replace_function(s, 'renderOptionsSection', options, 'renderDarkPoolSection')
    s = replace_function(s, 'renderDarkPoolSection', dark, 'renderRotationSection')
    p.write_text(s, encoding="utf-8")


if __name__ == '__main__':
    repair_python()
    repair_html()
    print('dashboard repair complete')
