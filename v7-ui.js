/* Claude V7 extensions: retain existing interaction and layout. */
function v7Fresh(value,days){const t=Date.parse(String(value||''));return Number.isFinite(t)&&t<=Date.now()+86400000&&t>=Date.now()-days*86400000;}
function v7PrintAllowed(p){const day=String(p.timestamp||'').slice(0,10);return (!window.__darkFrom||day>=window.__darkFrom)&&(!window.__darkTo||day<=window.__darkTo);}
function v7LabelLayout(annotations,trace,layout,el){
 const xs=(trace.x||[]).map(Number),ys=(trace.high||trace.y||[]).concat(trace.low||[]).filter(Number.isFinite);
 if(!xs.length||!ys.length)return annotations;
 const width=Math.max(280,(el.clientWidth||900)-110),height=Math.max(220,(layout.height||520)-120);
 const xmin=Math.min(...xs),xspan=Math.max(1,Math.max(...xs)-xmin),ymin=Math.min(...ys),yspan=Math.max(.01,Math.max(...ys)-ymin);
 const px=x=>(Number(x)-xmin)/xspan*width,py=y=>height-(y-ymin)/yspan*height;
 const placed=[],boxes=xs.map((x,i)=>({x:px(x)-2,y:py((trace.high||trace.y)[i]),w:4,h:Math.max(3,(trace.high&&trace.low)?((trace.high[i]-trace.low[i])/yspan*height):3)}));
 const overlap=(a,b)=>Math.max(0,Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x))*Math.max(0,Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y));
 return annotations.map((a,i)=>{
  const w=Math.min(230,Math.max(100,String(a.text).length*6)),h=24,x=px(a.x),y=py(a.y);
  const candidates=[[-100,-65],[100,65],[-100,65],[100,-65],[0,-100],[0,100],[-150,0],[150,0]].map(([dx,dy])=>{
   const cx=Math.max(w/2,Math.min(width-w/2,x+dx)),cy=Math.max(h/2,Math.min(height-h/2,y+dy)),box={x:cx-w/2,y:cy-h/2,w,h};
   const cost=placed.reduce((s,b)=>s+overlap(box,b)*100,0)+boxes.reduce((s,b)=>s+overlap(box,b)*5,0)+Math.hypot(cx-x,cy-y);
   return {box,cost,dx:cx-x,dy:cy-y};
  }).sort((a,b)=>a.cost-b.cost);
  const best=candidates[0];placed.push(best.box);
  return {...a,showarrow:true,ax:best.dx,ay:best.dy,arrowhead:0,arrowwidth:1,xanchor:'center',yanchor:'middle',bgcolor:'rgba(0,0,0,0)',font:{size:window.__darkLabelSize||11,color:v7Palette().ink}};
 });
}
const v7Catalog=optionsDisplayCatalog;
optionsDisplayCatalog=function(o){
 const entries=v7Catalog(o).filter(x=>!['SXXP','EXSA'].includes(x.code));
 entries.push({code:'SXXP',family:'EURO STOXX',label:'STOXX Europe 600 · índice · cadena OXXP no conectada',kind:'index'},
              {code:'EXSA',family:'EURO STOXX',label:'iShares STOXX Europe 600 UCITS ETF · cadena no conectada',kind:'etf'});
 return entries.map(x=>['SX5E','FEZ','SXXP','EXSA'].includes(x.code)?{...x,family:'EURO STOXX'}:x)
  .filter(x=>!['SX5E','FEZ','SXXP','EXSA'].includes(x.code)||((window.__stoxxSegment||'50')==='600'?['SXXP','EXSA']:['SX5E','FEZ']).includes(x.code));
};
function v7Palette(){
 const warm=document.body.classList.contains('theme-warm'),carbon=document.body.classList.contains('theme-carbon');
 return {panel:warm?'#201b15':carbon?'#101d1b':'#101a2a',ink:warm?'#f2e8d8':'#e2e8f0',grid:warm?'#514332':carbon?'#29433d':'#334155',accent:warm?'#d8a64a':carbon?'#58c7b4':'#60a5fa'};
}
const v7OldTheme=setTheme;
setTheme=function(theme){v7OldTheme(theme);if(window.Plotly){const p=v7Palette();document.querySelectorAll('.js-plotly-plot').forEach(el=>Plotly.relayout(el,{'font.color':p.ink,'xaxis.gridcolor':p.grid,'yaxis.gridcolor':p.grid,'paper_bgcolor':'transparent','plot_bgcolor':'transparent'}));}};

renderCurveChart=function(data){
 const bonds=data.bonds||{},pts=(bonds.tenors||[]).map(t=>({term:t.term,y:parseRate(t.yield)})).filter(t=>Number.isFinite(t.y));
 if(pts.length<2)return '<div class="curve-wrap text-sm">Curva sin suficientes vencimientos observados.</div>';
 const id='v7-curve-'+data.id;
 setTimeout(()=>__loadPlotly().then(P=>{
  const el=document.getElementById(id);if(!el)return;
  const p=v7Palette(),hist=bonds.history||[],traces=[];
  for(const [offset,label,color] of [[21,'21 sesiones antes','#64748b'],[5,'5 sesiones antes','#a78bfa']]){
   const row=hist[hist.length-1-offset];if(!row)continue;
   const values=pts.map(t=>row.values?.[t.term]??null);
   if(values.filter(x=>x!==null).length>1)traces.push({x:pts.map(t=>t.term),y:values,name:label+' · '+row.date,mode:'lines+markers',line:{color,dash:'dot',width:1.5},connectgaps:false});
  }
  traces.push({x:pts.map(t=>t.term),y:pts.map(t=>t.y),mode:'lines+markers',name:'Curva · '+(bonds.date||'sin fecha'),line:{color:p.accent,width:3},marker:{size:8},hovertemplate:'%{x}: %{y:.3f}%<extra></extra>'});
  P.newPlot(el,traces,{height:480,paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{color:p.ink,size:13},margin:{l:68,r:25,t:55,b:65},xaxis:{title:'Vencimiento',type:'category',gridcolor:p.grid},yaxis:{title:'Rendimiento (%)',gridcolor:p.grid,automargin:true},legend:{orientation:'h',y:1.15},hovermode:'x unified'},{responsive:true,scrollZoom:true,displaylogo:false,modeBarButtonsToRemove:['select2d','lasso2d']});
 }),70);
 return '<div class="curve-wrap"><div id="'+id+'" style="height:480px"></div><div class="text-xs text-gray-400">'+esc(bonds.source||'Fuente sin identificar')+' · '+esc(bonds.date||'sin fecha')+' · '+esc(bonds.status==='estimated'?'Curva oficial estimada':'Rendimientos observados')+' · '+esc(bonds.methodology||'Sin interpolación propia')+'</div></div>';
};

const v7Options=renderOptionsSection;
renderOptionsSection=function(){
 const html=v7Options(),o=macroDatabase.__options||{},m=(o.markets||[]).find(x=>x.ticker===window.__optTicker)||{},p=optionsSelectedProfile(m)||{};
 const roots=(p.gammaFlipRoots||[]).map(x=>fmtNum(x,2)).join(' · '),model=p.gammaFlipModel;
 const history=(o.dailySnapshots?.[(m.ticker||'')+':'+(p.expiration||'')]||[]).slice(-5);
 const details='<details class="metric p-4 mt-4"><summary class="cursor-pointer text-sm font-bold">Datos, modelo y evolución · '+esc(p.expiration||'sin vencimiento')+'</summary><div class="grid md:grid-cols-2 gap-4 mt-4 text-sm"><div><b>Gamma Flip</b><p>'+esc(p.gammaFlipStatus||'No calculable con este snapshot')+'</p><p>Cobertura OI con IV: '+fmtNum(p.gammaFlipCoveragePct,1)+'%. Cruces: '+esc(roots||'ninguno calculable')+'.</p><p>'+esc(model?.method||'Sin modelo revalorado disponible')+'</p><p>Supuestos: r='+fmtNum(model?.rate,3)+'; q='+fmtNum(model?.dividendYield,3)+'. OI fijo, IV por strike constante; exposición estimada.</p><p>Sensibilidad: '+esc(p.gammaFlipSensitivity?JSON.stringify(p.gammaFlipSensitivity):'no disponible')+'</p></div><div><b>Put/Call y Max Pain</b><p>OI: '+fmtNum(p.putCallOi,2)+' · Volumen: '+fmtNum(p.putCallVolume,2)+'. Mismo vencimiento; no son señales automáticas de compra/venta.</p><p>Max Pain minimiza el pago intrínseco agregado del OI observado. Walls OI son concentraciones de contratos; GEX aplica gamma y un supuesto de signo.</p><p>IV ATM es la volatilidad del activo y vencimiento seleccionados, no el VIX. Datos: '+esc(m.asOf||'sin fecha')+' · '+esc(m.source||'sin fuente')+'</p></div></div><div class="mt-4 text-xs">Últimas '+history.length+' fechas de snapshot capturadas · sin reconstrucción retrospectiva</div><div class="overflow-x-auto"><table class="w-full text-xs"><tr><th>Fecha</th><th>Call OI</th><th>Put OI</th><th>GEX</th><th>Flip</th></tr>'+history.map(r=>'<tr><td>'+esc(r.date)+'</td><td>'+fmtNum(r.callOi,0)+'</td><td>'+fmtNum(r.putOi,0)+'</td><td>'+fmtCompactMoney(r.gammaNet)+'</td><td>'+fmtNum(r.gammaFlip,2)+'</td></tr>').join('')+'</table></div></details>';
 const tabs=window.__optFamily==='EURO STOXX'?'<div class="flex gap-3 p-3"><button class="mini-pill" onclick="window.__stoxxSegment=\'50\';window.__optTicker=\'SX5E\';renderContent()">EURO STOXX 50 · SX5E / FEZ</button><button class="mini-pill" onclick="window.__stoxxSegment=\'600\';window.__optTicker=\'SXXP\';renderContent()">STOXX Europe 600 · SXXP / EXSA</button></div>':'';
 const djx=(o.markets||[]).find(x=>x.ticker==='DJX'),rawDow=djx?.referenceIndex?.price;
 const dowValue=rawDow??(Number.isFinite(djx?.spot)?djx.spot*100:null);
 const dow=['DJX','DIA'].includes(window.__optTicker)?'<div class="metric p-4"><div class="flex flex-wrap gap-3 justify-between"><b>Dow Jones · DJIA / DJI</b><span>'+fmtNum(dowValue,2)+' puntos</span></div><p class="text-sm text-gray-400 mt-2">'+(rawDow!=null?'Precio del índice de referencia · '+esc(djx.referenceIndex.source):'Equivalente del índice calculado como DJX × 100')+' · '+esc(djx?.asOf||'sin fecha')+'</p><p class="text-xs text-gray-400 mt-2">DJX / DJXW: opciones sobre 1/100 del DJIA; multiplicador 100 USD por punto. DIA: ETF con precio y cadena propios. Los strikes y el OI se interpretan en la escala del instrumento seleccionado.</p></div>':'';
 return html.replace('<section id="sec-options" class="space-y-4">','<section id="sec-options" class="space-y-4">'+tabs+dow).replace('</div></section>',details+'</div></section>');
};

const v7Dark=renderDarkPoolSection;
renderDarkPoolSection=function(){
 const html=v7Dark(),a=macroDatabase.__darkPoolPrints?.assets?.[window.__darkPoolTicker]||{};
 const frames=a.ohlcTimeframes||{},chosen=window.__darkTimeframe||'1d';
 const timeframe='<div class="metric p-4 flex flex-wrap gap-3 items-center"><label>Velas <select aria-label="Temporalidad dark pools" onchange="window.__darkTimeframe=this.value;renderContent()">'+['1d','4h','1h'].map(k=>'<option value="'+k+'" '+(chosen===k?'selected ':'')+((frames[k]?.candles?.length|| (k==='1d'&&a.ohlc?.length))?'':'disabled')+'>'+({'1d':'Diario','4h':'4 horas · agregado','1h':'1 hora'})[k]+'</option>').join('')+'</select></label><span class="text-xs text-gray-400">'+esc(frames[chosen]?.observedAt||a.ohlcObservedAt||'sin fecha')+' · '+esc(frames[chosen]?.timezone||'UTC')+' · retrasado'+(chosen==='4h'?' · agrupado por sesión; última vela puede ser inferior a 4 h':'')+'</span></div>';
 const controls='<details class="metric p-4"><summary class="cursor-pointer text-sm">Dark pools · fechas y presentación</summary><div class="flex flex-wrap gap-4 mt-4 text-sm"><label>Desde <input type="date" value="'+esc(window.__darkFrom||'')+'" onchange="window.__darkFrom=this.value;renderContent()"></label><label>Hasta <input type="date" value="'+esc(window.__darkTo||'')+'" onchange="window.__darkTo=this.value;renderContent()"></label><label>Línea <input type="range" min="1" max="2" step="0.25" value="'+(window.__darkLineWidth||1)+'" onchange="window.__darkLineWidth=Number(this.value);renderContent()"></label><label>Opacidad <input type="range" min="0.2" max="1" step="0.05" value="'+(window.__darkOpacity??.65)+'" onchange="window.__darkOpacity=Number(this.value);renderContent()"></label><label>Texto <input type="range" min="10" max="15" value="'+(window.__darkLabelSize||11)+'" onchange="window.__darkLabelSize=Number(this.value);renderContent()"></label><label><input type="checkbox" '+(window.__darkHideLabels?'':'checked')+' onchange="window.__darkHideLabels=!this.checked;renderContent()"> Etiquetas</label></div></details><p class="text-xs text-gray-400">Precio: '+esc(a.ohlcObservedAt||'sin fecha OHLC')+' · '+esc(a.ohlcSource||'serie puntual')+' · Prints verificables: '+(a.prints||[]).filter(p=>p.realPrint&&p.price!=null&&p.timestamp).length+'. Los agregados ATS no identifican compras o ventas individuales.</p>';
 return html.replace(/(<section id="sec-darkpool"[^>]*>)/,'$1'+timeframe+controls);
};

const v7Sentiment=renderCryptoBondSection;
renderCryptoBondSection=function(){
 const html=v7Sentiment(),h=macroDatabase.__cryptoSentiment?.fearGreed?.history||[];
 const history='<div class="metric p-4"><div class="text-xs text-gray-400 mb-3">Últimas 7 observaciones · Fear & Greed</div><div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">'+h.slice(-7).map(r=>'<div class="text-center"><div class="text-xs text-gray-400">'+esc(r.date)+'</div><div class="text-xl font-bold mt-1" style="color:'+fearVisualTone(r.value).color+'">'+fmtNum(r.value,0)+'</div><div class="text-xs text-gray-400">'+esc(r.classification||'')+'</div></div>').join('')+'</div></div>';
 return html.replace('<div id="crypto-etf-flows"',history+'<div id="crypto-etf-flows"');
};
