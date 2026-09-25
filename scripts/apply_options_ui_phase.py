from pathlib import Path
p=Path(__file__).resolve().parents[1]/"index.html"
s=p.read_text(encoding="utf-8")
s=s.replace("EXPECTED MOVE · MODEL","EXPECTED MOVE · IV → RANGO")
s=s.replace("ATM IV · OBSERVED","ATM IV · VOLATILIDAD IMPLÍCITA")
s=s.replace("?'±'+fmtNum(p.expectedMove,2):'N/D'","?'±'+fmtNum(p.expectedMove,2):'—'")
advanced=r'''<div class="metric rounded-xl p-5"><div class="flex justify-between gap-3"><div><b class="text-sm text-white">OPCIONES · MÉTRICAS PROFESIONALES</b><p class="text-[10px] text-gray-500 mt-1">Concentración de OI, walls, skew y régimen de gamma.</p></div><span class="mini-pill">PUBLIC CHAIN</span></div><div class="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3 mt-4">
<div class="p-3 rounded-lg bg-gray-900"><span class="text-[9px] text-gray-500">CALL WALL</span><b class="block text-sm text-white mt-1">'+fmtNum(p.callWall??m.topCallStrike,2)+'</b><small>'+fmtNum(p.callWallOi,0)+' OI</small></div>
<div class="p-3 rounded-lg bg-gray-900"><span class="text-[9px] text-gray-500">PUT WALL</span><b class="block text-sm text-white mt-1">'+fmtNum(p.putWall??m.topPutStrike,2)+'</b><small>'+fmtNum(p.putWallOi,0)+' OI</small></div>
<div class="p-3 rounded-lg bg-gray-900"><span class="text-[9px] text-gray-500">CALL WALL VOL</span><b class="block text-sm text-white mt-1">'+fmtNum(p.callWallVolume,0)+'</b></div>
<div class="p-3 rounded-lg bg-gray-900"><span class="text-[9px] text-gray-500">PUT WALL VOL</span><b class="block text-sm text-white mt-1">'+fmtNum(p.putWallVolume,0)+'</b></div>
<div class="p-3 rounded-lg bg-gray-900"><span class="text-[9px] text-gray-500">25D SKEW</span><b class="block text-sm text-white mt-1">'+(Number.isFinite(Number(p.skew25d))?fmtNum(p.skew25d,2)+' vol pts':'—')+'</b></div>
<div class="p-3 rounded-lg bg-gray-900"><span class="text-[9px] text-gray-500">OI > SPOT</span><b class="block text-sm text-white mt-1">'+(Number.isFinite(Number(p.oiAbovePct))?fmtNum(p.oiAbovePct,1)+'%':'—')+'</b></div>
<div class="p-3 rounded-lg bg-gray-900"><span class="text-[9px] text-gray-500">OI < SPOT</span><b class="block text-sm text-white mt-1">'+(Number.isFinite(Number(p.oiBelowPct))?fmtNum(p.oiBelowPct,1)+'%':'—')+'</b></div>
<div class="p-3 rounded-lg bg-gray-900"><span class="text-[9px] text-gray-500">GAMMA NET</span><b class="block text-sm '+(Number(p.gammaNet)<0?'text-red-300':'text-emerald-300')+' mt-1">'+(Number(p.gammaNet)<0?'NEGATIVO':'POSITIVO')+'</b></div></div>
<div class="mt-4 text-xs text-gray-400">Gamma negativo puede asociarse, bajo el modelo, con mayor amplificación de movimientos; gamma positivo con mayor amortiguación. No es una garantía ni una observación directa del posicionamiento de dealers. Max Pain y walls son concentraciones de OI, no soportes/resistencias garantizados.</div></div>'''
needle='<div class="metric rounded-xl p-4"><b class="text-sm text-white">Cómo leerlo</b>'
if "OPCIONES · MÉTRICAS PROFESIONALES" not in s and needle in s:s=s.replace(needle,advanced+needle,1)
if "function renderOrderFlowSection()" not in s:
 fn=r'''function renderOrderFlowSection(){
 const o=macroDatabase.__orderFlow||{markets:[]},ms=o.markets||[],n=v=>Number.isFinite(Number(v))?Number(v).toLocaleString("es-ES",{maximumFractionDigits:2}):"—";
 const cards=ms.map(m=>'<div class="metric rounded-xl p-4"><div class="flex justify-between"><b class="text-sm text-white">'+esc(m.display||m.symbol)+'</b><span class="mini-pill">Spread '+n(m.spread)+'</span></div><div class="text-[10px] text-gray-400 mt-1">'+esc(m.dataStatus||"")+'</div><div class="grid grid-cols-4 gap-2 mt-4 text-[10px]"><div>Bid<br><b>'+n(m.bestBid)+'</b></div><div>Ask<br><b>'+n(m.bestAsk)+'</b></div><div>Bid depth<br><b class="text-emerald-300">'+n(m.bidDepth??m.bidSize)+'</b></div><div>Ask depth<br><b class="text-red-300">'+n(m.askDepth??m.askSize)+'</b></div></div><div class="mt-3 text-[10px] text-gray-400">Imbalance <b class="'+(Number(m.imbalance)>=0?"text-emerald-300":"text-red-300")+'">'+n(m.imbalance)+'%</b> · '+esc(m.source||"")+'</div></div>').join("");
 return '<section id="sec-orderflow" class="space-y-4"><div class="glass rounded-2xl p-5"><div class="text-[10px] uppercase tracking-wider text-gray-400">MICROESTRUCTURA</div><h2 class="text-xl font-black text-white mt-1">ORDER FLOW · MARKET DEPTH</h2><p class="text-sm text-gray-300 mt-1">BTC/ETH: profundidad pública Deribit. Acciones/ETF: top-of-book; no se presenta como Level 2.</p></div><div class="grid grid-cols-1 xl:grid-cols-2 gap-4">'+(cards||'<div class="metric p-5 text-gray-400">Sin profundidad pública.</div>')+'</div></section>';
}'''
 s=s.replace("function renderGlobalView()",fn+"\n\n        function renderGlobalView()",1)
if "if(feed.orderFlow) macroDatabase.__orderFlow" not in s:s=s.replace("if(feed.squawkFlow) macroDatabase.__squawkFlow = feed.squawkFlow;","if(feed.squawkFlow) macroDatabase.__squawkFlow = feed.squawkFlow;\n                    if(feed.orderFlow) macroDatabase.__orderFlow = feed.orderFlow;",1)
if "macroDatabase.__orderFlow = macroDatabase.__orderFlow ||" not in s:s=s.replace("macroDatabase.__squawkFlow = macroDatabase.__squawkFlow || {};","macroDatabase.__squawkFlow = macroDatabase.__squawkFlow || {};\n        macroDatabase.__orderFlow = macroDatabase.__orderFlow || {updated:'—',markets:[]};",1)
if "$"+"{renderOrderFlowSection()}" not in s:s=s.replace("$"+"{renderCotSection()}$"+"{renderOptionsSection()}","$"+"{renderCotSection()}$"+"{renderOrderFlowSection()}$"+"{renderOptionsSection()}",1)
p.write_text(s,encoding="utf-8")
print("OPTIONS UI + ORDER FLOW UI PHASE OK")
