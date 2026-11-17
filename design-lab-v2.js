'use strict';

// Fixtures for the visual lab only. The page never requests the market feeds.
const demoDate = '2026-11-13';
const date = days => new Date(Date.UTC(2026, 10, 13 + days)).toISOString().slice(0, 10);
const points = (size, make) => Array.from({length:size}, (_, i) => make(i));
const wave = i => Math.sin(i * .53) * .64 + Math.cos(i * 1.71) * .36;
const round = n => Math.round(n * 100) / 100;
const num = (n, digits = 2) => n == null ? '—' : n.toLocaleString('es-ES', {maximumFractionDigits:digits, minimumFractionDigits:digits});
const signed = (n, digits = 2) => (n > 0 ? '+' : '') + num(n, digits);
const fmt = (n, unit, digits = 2) => num(n, digits) + ' ' + unit;
const tickDates = points(60, i => date(i - 59));
const sessions = points(118, i => date(i - 117)).filter(d => {
  const day = new Date(d + 'T12:00:00Z').getUTCDay();
  return day > 0 && day < 6;
});
const flowDates = sessions.slice(-20);
const weeklyDates = flowDates.filter((_, i) => i % 5 === 4);
const widths = ['3M','1A','2A','5A','10A','20A','30A'];
const assets = {
  SPX:{name:'S&P 500 Index', price:5897.4, step:25, flip:5855, call:6000, put:5800, scale:250},
  SPY:{name:'SPDR S&P 500 ETF', price:589.73, step:2.5, flip:585.5, call:600, put:580, scale:150},
  GLD:{name:'SPDR Gold Shares', price:248.15, step:2.5, flip:247.5, call:255, put:242.5, scale:64},
  USO:{name:'United States Oil Fund · WTI', price:71.7, step:1, flip:71, call:75, put:69, scale:42},
  BNO:{name:'United States Brent Oil Fund', price:30.31, step:.5, flip:30, call:32, put:29, scale:18}
};
const etfs = {BTC:points(20, i => round(125 + 400 * wave(i))), ETH:points(20, i => round(55 + 150 * wave(i + 3)))};
const regimes = ['Liquidez','Renta variable','Volatilidad','Crédito','Divisas','Materias primas'];
const regimesValues = [7,12,-5,4,-2,3];
const cotGroups = {
  'Gestores de activos':{base:342000,swing:81000,color:'accent'},
  'Fondos apalancados':{base:-240000,swing:93000,color:'accent2'},
  'Intermediarios':{base:-124000,swing:46000,color:'amber'}
};
const fxRows = [
  ['USD','Fed','4,00 %','4,18 %','+0,62 %','Mixto'], ['EUR','BCE','2,25 %','2,19 %','−0,45 %','Mixto'],
  ['JPY','BoJ','0,75 %','1,02 %','+0,18 %','Defensivo'], ['CAD','BoC','2,50 %','2,69 %','−0,48 %','Mixto'],
  ['AUD','RBA','3,60 %','3,80 %','+0,33 %','Expansivo'], ['NZD','RBNZ','3,00 %','3,12 %','−0,41 %','Mixto'],
  ['CHF','SNB','0,25 %','0,45 %','+0,11 %','Defensivo'], ['GBP','BoE','4,25 %','4,30 %','+0,20 %','Mixto']
];

const $ = id => document.getElementById(id);
const html = (tag, props, ...children) => {
  const node = document.createElement(tag);
  Object.entries(props ?? {}).forEach(([key,val]) => node.setAttribute(key, val));
  node.append(...children.flat());
  return node;
};
const select = (label, options, initial, changed) => {
  const node = html('select', {'aria-label':label}, options.map(([value, text]) => html('option', {value}, text)));
  node.value = initial;
  node.addEventListener('change', () => changed(node.value));
  return html('label', null, label, node);
};
const button = (label, click) => {
  const node = html('button', {type:'button'}, label);
  node.addEventListener('click', click);
  return node;
};
const controls = (...items) => html('div', {class:'controls'}, items);
function table(headers, rows, caption = 'Datos de demostración') {
  return html('div', {class:'table-scroll'},
    html('table', {'aria-label':caption},
      html('thead', null, html('tr', null, headers.map(h => html('th', {scope:'col'}, h)))),
      html('tbody', null, rows.map(row => html('tr', null, row.map(v => html('td', null, String(v ?? '—'))))))));
}
const card = (title, desc, ...body) => html('article', {class:'card'},
  html('div', {class:'panel-head'}, html('div', null, html('h2', null, title), html('p', null, desc))), body);
const details = (label, ...contents) => html('details', null, html('summary', null, label), contents);
const colorClass = tone => tone === 'up' ? 'up' : tone === 'down' ? 'down' : '';
function metric([name,value,note,tone,copyValue]) {
  const node = html('article', {class:'card metric','data-tone':tone ?? 'neutral'},
    html('span', {class:'label'}, name), html('strong', {class:'value ' + colorClass(tone)}, value), html('small', null, note));
  if (copyValue != null) {
    const copy = button('Copiar', async () => {
      try {
        await navigator.clipboard.writeText(copyValue);
        $('announcement').textContent = name + ' copiado';
        copy.textContent = 'Copiado';
        setTimeout(() => { copy.textContent = 'Copiar'; }, 1400);
      } catch {
        const range = document.createRange();
        range.selectNodeContents(node.querySelector('.value'));
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        $('announcement').textContent = name + ' seleccionado para copiar';
      }
    });
    copy.className = 'copy';
    copy.setAttribute('aria-label', 'Copiar ' + name);
    node.append(copy);
  }
  return node;
}
const metrics = (...items) => html('div', {class:'metric-grid'}, items.map(metric));
const columns = (...items) => html('div', {class:'grid-two'}, items);

const chartStates = new WeakMap();
let plotlyPromise;
function getPlotly() {
  if (!plotlyPromise) {
    plotlyPromise = new Promise((resolve, reject) => {
      const script = html('script', {src:'https://cdn.plot.ly/plotly-2.35.2.min.js', async:''});
      const timeout = setTimeout(() => reject(Error('Tiempo de carga agotado')), 15000);
      script.onload = () => { clearTimeout(timeout); window.Plotly ? resolve(window.Plotly) : reject(Error('Motor no disponible')); };
      script.onerror = () => { clearTimeout(timeout); reject(Error('Motor no disponible')); };
      document.head.append(script);
    }).catch(error => { plotlyPromise = null; throw error; });
  }
  return plotlyPromise;
}

function palette() {
  const style = getComputedStyle(document.documentElement);
  const read = name => style.getPropertyValue('--' + name).trim();
  return {accent:read('accent'), accent2:read('accent-2'), positive:read('positive'),
    negative:read('negative'), line:read('line'), panel:read('panel'), muted:read('muted'),
    ink:read('ink'), amber:read('amber')};
}

function layout(p, spec, revision, narrow) {
  const interactive = spec.interactive ?? false;
  const axis = {gridcolor:p.line, linecolor:p.line, tickfont:{size:narrow ? 10 : 11, color:p.muted},
    zerolinecolor:p.muted, automargin:true, fixedrange:true};
  const xaxis = {...axis, fixedrange:!interactive, ...spec.xaxis};
  if (interactive) Object.assign(xaxis, {showspikes:true, spikemode:'across', spikesnap:'cursor', spikedash:'dot', spikethickness:1, spikecolor:p.muted});
  return {
    paper_bgcolor:'transparent', plot_bgcolor:'transparent', font:{family:'Inter, system-ui',color:p.ink,size:12},
    margin:{l:narrow ? 40 : 54,r:spec.yaxis2 ? (narrow ? 46 : 67) : 18,t:spec.legend ? 50 : 27,b:48},
    xaxis, yaxis:{...axis, ...spec.yaxis},
    ...(spec.yaxis2 ? {yaxis2:{...axis, showgrid:false, zeroline:false, ...spec.yaxis2}} : {}),
    hovermode:interactive ? 'x unified' : 'closest', hoverlabel:{bgcolor:p.panel,bordercolor:p.line,font:{color:p.ink}},
    showlegend:!!spec.legend, legend:{orientation:'h', y:1.04, x:0, font:{size:11}, tracegroupgap:3},
    shapes:spec.shapes, annotations:spec.annotations, barmode:spec.barmode,
    dragmode:interactive ? 'pan' : false, uirevision:revision,
    separators:',.'
  };
}

async function drawChart(host) {
  const state = chartStates.get(host);
  if (!host.offsetWidth || host.closest('[hidden]')) return;
  if (state.busy) { state.queued = true; return; }
  if (state.rendered === state.revision && state.generation === state.drawnGeneration && state.theme === document.documentElement.dataset.theme) {
    window.Plotly.Plots.resize(host);
    return;
  }
  state.busy = true;
  try {
    const P = await getPlotly();
    if (!host.offsetWidth || host.closest('[hidden]')) return;
    const revision = state.revision;
    const generation = state.generation;
    const theme = document.documentElement.dataset.theme;
    const p = palette();
    const spec = state.make(p);
    const config = {responsive:true, displaylogo:false, displayModeBar:false, showTips:false,
      scrollZoom:!!spec.interactive, doubleClick:spec.interactive ? 'reset' : false};
    const l = layout(p,spec,revision,host.offsetWidth < 520);
    if (state.dragMode) l.dragmode = state.dragMode;
    await P.react(host,spec.traces,l,config);
    state.rendered = revision;
    state.drawnGeneration = generation;
    state.theme = theme;
    state.notice.hidden = true;
    state.retry.hidden = true;
    host.dataset.ready = 'true';
  } catch {
    state.notice.textContent = 'El gráfico no pudo cargar. La tabla de valores sigue disponible.';
    state.notice.hidden = false;
    state.retry.hidden = false;
  } finally {
    state.busy = false;
    if (state.queued) { state.queued = false; drawChart(host); }
  }
}

function chart({title,desc,make,extra,toolbar,tall=false}) {
  const host = html('div', {class:'chart' + (tall ? ' tall' : ''), 'aria-label':title});
  const notice = html('p', {class:'chart-status', role:'status'}, 'Cargando gráfico…');
  const retry = button('Reintentar gráfico', () => drawChart(host));
  retry.hidden = true;
  const state = {make,notice,retry,revision:0,generation:0};
  chartStates.set(host,state);
  const tools = toolbar?.(host);
  const values = details('Consultar valores');
  const fillValues = () => {
    const spec = make(palette());
    values.replaceChildren(values.firstElementChild, table(spec.headers,spec.rows,title), ...(spec.extraValues?.() ?? []));
  };
  values.addEventListener('toggle', () => { if (values.open) fillValues(); });
  host.addEventListener('renew', event => {
    ++state.generation;
    if (!event.detail?.keepView) ++state.revision;
    if (values.open) fillValues();
    drawChart(host);
  });
  return html('article', {class:'card'},
    html('div', {class:'panel-head'}, html('div', null, html('h2', null, title), html('p', null, desc)), tools ? [tools] : []),
    notice, retry, host, values, extra ?? []);
}

function zoomTools(host) {
  const mode = (value, label) => {
    const node = button(label, async () => {
      chartStates.get(host).dragMode = value;
      controlsNode.querySelectorAll('[aria-pressed]').forEach(x => x.setAttribute('aria-pressed', String(x === node)));
      if (host.dataset.ready) await window.Plotly.relayout(host, {dragmode:value});
    });
    node.setAttribute('aria-pressed', String(value === 'pan'));
    return node;
  };
  const reset = button('Restablecer', () => {
    if (host.dataset.ready) window.Plotly.relayout(host, {'xaxis.autorange':true});
  });
  const controlsNode = controls(mode('pan','Desplazar'),mode('zoom','Ampliar región'),reset);
  host.addEventListener('renew', event => {
    if (event.detail?.keepView) return;
    chartStates.get(host).dragMode = 'pan';
    controlsNode.querySelectorAll('[aria-pressed]').forEach((node,i) => node.setAttribute('aria-pressed', String(i === 0)));
  });
  return controlsNode;
}

const line = (name,x,y,color,unit,extra = {}) => ({
  type:'scatter', mode:'lines', name,x,y,line:{color,width:2.4},
  hovertemplate:'%{y:,.2f} ' + unit + '<extra>' + name + '</extra>', ...extra
});
const bars = (name,x,y,color,unit) => ({
  type:'bar', name,x,y,marker:{color}, hovertemplate:'%{x}<br>%{y:,.2f} ' + unit + '<extra>' + name + '</extra>'
});
const timeAxis = {type:'date', tickformat:'%d/%m', hoverformat:'%d/%m/%Y'};
const staticChart = (title,desc,make) => chart({title,desc,make});

function overview() {
  const values = points(60, i => round(50 + i * .23 + 10 * wave(i / 2.2)));
  return [
    metrics(['Régimen intermercado','63 / 100','Sesgo favorable · sesión de muestra','up'],
      ['S&P 500','5.897,40','+0,72 % · cierre a cierre','up'],
      ['VIX','17,85','−0,46 pt · cierre a cierre','down'],
      ['Crédito HY','338 pb','+5 pb · diferencial OAS','down']),
    columns(staticChart('Régimen de mercado','Histórico de muestra · escala 0–100',p => ({
      xaxis:timeAxis, yaxis:{range:[0,100],title:{text:'Puntuación'}},
      traces:[line('Régimen',tickDates,values,p.accent,'/ 100',{fill:'tozeroy',fillcolor:p.accent + '22'})],
      headers:['Fecha','Puntuación / 100'],rows:tickDates.map((d,i) => [d,num(values[i],1)])
    })), staticChart('Señales intermercado','Contribuciones demostrativas, en puntos',p => ({
      traces:[bars('Contribución',regimes,regimesValues,regimesValues.map(v => v >= 0 ? p.positive : p.negative),'pt')],
      xaxis:{tickangle:-25},yaxis:{title:{text:'Puntos'}},
      headers:['Factor','Contribución'],rows:regimes.map((name,i) => [name,signed(regimesValues[i],0)])
    }))),
    card('Agenda de la semana','Fechas, períodos y estado de publicación de muestra',table(
      ['Fecha','Divisa','Evento','Último','Consenso','Estado'],
      [['16 nov · 14:30','USD','Ventas minoristas','+0,4 %','+0,3 %','Programado'],
      ['17 nov · 11:00','EUR','IPC final','2,2 %','2,2 %','Programado'],
      ['19 nov · 00:30','JPY','IPC nacional','2,9 %','2,8 %','Programado']]))
  ];
}

function fx() {
  return [card('Divisas y política monetaria','Panorama comparativo · fuente de demostración',table(
    ['Divisa','Banco central','Tipo oficial','Bono 2A','Variación 5 sesiones','Sesgo'],fxRows)),
    card('Tres últimas reuniones','Muestra de ficha de banco central · Reserva Federal',
      table(['Fecha','Decisión','Cambio','Estado'],[
        ['2026-10-28','4,00 %','0 pb','Comunicado'],['2026-09-16','4,00 %','−25 pb','Comunicado'],['2026-07-29','4,25 %','0 pb','Comunicado']
      ]),details('Catalizadores e invalidación',html('p',null,'IPC y empleo de la próxima semana. Revisar el sesgo si el diferencial 2A y la divisa dejan de confirmar la misma dirección.')))];
}

function breadth() {
  return [
    metrics(['Avances','312','S&P 500 · 500 observados','up'],['Descensos','176','12 sin cambios','down'],
      ['Máximos / mínimos','34 / 12','Extremos de 52 semanas'],['Sobre SMA 200','61,4 %','307 de 500']),
    staticChart('Amplitud por horizonte','Porcentaje de componentes por encima de cada media',p => ({
      traces:[bars('S&P 500',['SMA 50','SMA 100','SMA 200'],[67.4,64.2,61.4],p.accent,'%'),
        bars('Nasdaq-100',['SMA 50','SMA 100','SMA 200'],[62,59,57],p.accent2,'%')],
      legend:true,barmode:'group',yaxis:{range:[0,100],ticksuffix:' %'},
      headers:['Media','S&P 500','Nasdaq-100'],rows:[['SMA 50','67,4 %','62 %'],['SMA 100','64,2 %','59 %'],['SMA 200','61,4 %','57 %']]
    })),
    card('Balance de mercado','Variaciones por sesión y cobertura de muestra',table(['Universo','1 sesión','5 sesiones','21 sesiones','Cobertura'],[
      ['S&P 500','+136','+274','+594','500 / 500'],['Nasdaq-100','+21','+49','+107','100 / 100']
    ]))
  ];
}

function sentiment() {
  const btc = points(60,i => round(94600 + 218*i + wave(i / 1.5)*4800));
  const scores = points(60,i => Math.round(30 + i*.52 + wave(i / 1.5 + 2)*19));
  return [
    metrics(['Crypto Fear & Greed',num(scores.at(-1),0) + ' / 100',demoDate],['BTC / USD',fmt(btc.at(-1),'USD',0),demoDate],
      ['Miedo y codicia · bolsa','57 / 100','Lectura bursátil de muestra'],['AAII · alcistas','38,4 %','Encuesta semanal de muestra']),
    chart({title:'BTC y Crypto Fear & Greed',desc:'Fechas compartidas · índice a la izquierda y precio BTC a la derecha', tall:true,toolbar:zoomTools, make:p => ({
      interactive:true, legend:true, xaxis:timeAxis, yaxis:{range:[0,100],title:{text:'Índice / 100'}},
      yaxis2:{overlaying:'y',side:'right',title:{text:'BTC · USD'},tickformat:'~s'},
      shapes:[[0,25,'#e88189'],[25,45,'#e9b271'],[45,55,'#a1a9ba'],[55,75,'#a6ce88'],[75,100,'#78d7b7']].map(([y0,y1,c]) => ({
        type:'rect',xref:'paper',x0:0,x1:1,y0,y1,fillcolor:c,opacity:.085,line:{width:0},layer:'below'
      })),
      traces:[line('Fear & Greed',tickDates,scores,p.amber,'/ 100',{mode:'lines+markers',marker:{size:4}}),
        line('BTC (USD)',tickDates,btc,p.accent,'USD',{yaxis:'y2'})],
      headers:['Fecha','Índice / 100','BTC · USD'],rows:tickDates.map((d,i) => [d,scores[i],num(btc[i])])
    })}),
    card('Sentimiento tradicional','Encuesta semanal de muestra',table(['Fecha','Alcistas','Neutrales','Bajistas'],
      [['12 nov','38,4 %','27,1 %','34,5 %'],['05 nov','35,1 %','26,2 %','38,7 %'],['29 oct','36,2 %','28,5 %','35,3 %']]))
  ];
}

function flows() {
  let period = 'daily';
  const weekly = arr => weeklyDates.map((_,i) => round(arr.slice(i*5,i*5+5).reduce((a,b) => a+b,0)));
  return [
    metrics(['BTC · última sesión',fmt(etfs.BTC.at(-1),'M USD',1),demoDate],['ETH · última sesión',fmt(etfs.ETH.at(-1),'M USD',1),demoDate],
      ['BTC · 4 semanas',fmt(weekly(etfs.BTC).reduce((a,b) => a+b,0),'M USD',1),'20 sesiones de muestra'],
      ['ETH · 4 semanas',fmt(weekly(etfs.ETH).reduce((a,b) => a+b,0),'M USD',1),'20 sesiones de muestra']),
    chart({title:'Flujos netos de ETF spot',desc:'Entradas y salidas en millones de USD · BTC y ETH por fecha',
      toolbar:host => controls(select('Período',[['daily','20 sesiones'],['weekly','4 semanas']],period,value => {
        period = value; host.dispatchEvent(new Event('renew'));
      })),
      make:p => {
        const x = period === 'weekly' ? weeklyDates : flowDates;
        const btc = period === 'weekly' ? weekly(etfs.BTC) : etfs.BTC;
        const eth = period === 'weekly' ? weekly(etfs.ETH) : etfs.ETH;
        return {xaxis:{type:'category',tickangle:-25,nticks:10},yaxis:{title:{text:'M USD'},zerolinewidth:2},barmode:'group',legend:true,
          traces:[bars('BTC',x,btc,btc.map(y => y >= 0 ? p.positive : p.negative),'M USD'),
            {...bars('ETH',x,eth,eth.map(y => y >= 0 ? p.positive : p.negative),'M USD'),marker:{color:eth.map(y => y >= 0 ? p.positive : p.negative),pattern:{shape:'/'}}}],
          headers:['Fecha','BTC · M USD','ETH · M USD'],rows:x.map((d,i) => [d,signed(btc[i]),signed(eth[i])])};
      }})
  ];
}

function cot() {
  let weeks = 26;
  const data = points(52,i => [date((i-51)*7), ...Object.values(cotGroups).map((v,j) => Math.round(v.base + v.swing * wave(i/4+j) + i*690))]);
  return [
    metrics(...Object.entries(cotGroups).map(([name],i) => [name,signed(data.at(-1)[i+1],0),'Posición neta · contratos'])),
    chart({title:'Posicionamiento COT · S&P 500 E-mini',desc:'Neto semanal por categoría · los puntos identifican cada informe',
      toolbar:host => controls(select('Histórico',[[13,'13 semanas'],[26,'26 semanas'],[52,'52 semanas']],weeks,value => {
        weeks = Number(value); host.dispatchEvent(new Event('renew'));
      }),zoomTools(host)),
      make:p => {
        const rows = data.slice(-weeks);
        return {interactive:true,legend:true,xaxis:timeAxis,yaxis:{title:{text:'Contratos netos'},tickformat:'~s'},
          traces:Object.entries(cotGroups).map(([name,v],i) => line(name,rows.map(r => r[0]),rows.map(r => r[i+1]),p[v.color],'contratos',{mode:'lines+markers',marker:{size:5}})),
          headers:['Fecha',...Object.keys(cotGroups)],rows:rows.map(r => [r[0],...r.slice(1).map(v => signed(v,0))])};
      }})
  ];
}

const aggregate = group => ({
  x:group[0].x, open:group[0].open, close:group.at(-1).close,
  high:Math.max(...group.map(r => r.high)), low:Math.min(...group.map(r => r.low)),
  volume:group.reduce((total,row) => total + row.volume,0)
});
function darkSample(ticker) {
  const base = assets[ticker].price;
  return sessions.slice(-45).map((day,d) => points(26,i => {
    const mid = base * (.963 + .0008*d + .005*wave(d/2) + .0015*i/26 + .0015*wave(i/2+d));
    const open = round(mid * (1 + .0012*wave(i+1)));
    const close = round(mid * (1 + .0013*wave(i+2)));
    const minutes = 30 + i*15;
    const hour = String(9+Math.floor(minutes/60)).padStart(2,'0');
    return {x:day+'T'+hour+':'+String(minutes%60).padStart(2,'0')+':00',
      open, close, high:round(Math.max(open,close)*1.0018), low:round(Math.min(open,close)*.9985),
      volume:Math.round(300000 + 180000 * (1+wave(i+d)))};
  }));
}
function darkPools() {
  let ticker = 'SPY', interval = '15m', printsVisible = true, sample = darkSample(ticker);
  return [
    chart({title:'Dark pools · precio y operaciones',desc:'Hora Nueva York de muestra. Velas OHLC, volumen y operaciones sintéticas superpuestas.',
      tall:true, toolbar:host => {
        const renew = keepView => host.dispatchEvent(new CustomEvent('renew',{detail:{keepView}}));
        const toggle = button('Operaciones', () => {
          printsVisible = !printsVisible;
          toggle.setAttribute('aria-pressed',String(printsVisible));
          renew(true);
        });
        toggle.setAttribute('aria-pressed','true');
        return controls(
          select('Activo',['SPY','GLD','USO','BNO'].map(t => [t,t]),ticker,value => {
            ticker = value; sample = darkSample(ticker); renew();
          }),
          select('Intervalo',[['15m','15 min'],['1h','1 hora'],['1d','1 día']],interval,value => { interval = value; renew(); }),
          toggle,zoomTools(host));
      },
      make:p => {
        const candles = interval === '1d' ? sample.map(day => ({...aggregate(day),x:day[0].x.slice(0,10)})) :
          interval === '1h' ? sample.slice(-6).flatMap(day => points(Math.ceil(day.length/4), i => aggregate(day.slice(i*4,i*4+4)))) :
            sample.slice(-2).flat();
        const x = candles.map(r => r.x);
        const range = [Math.min(...candles.map(r => r.low)) * .997, Math.max(...candles.map(r => r.high)) * 1.003];
        const ohlc = {type:'candlestick',name:ticker,x,
          ...Object.fromEntries(['open','high','low','close'].map(key => [key,candles.map(r => r[key])])),
          increasing:{line:{color:p.positive,width:1},fillcolor:p.positive},
          decreasing:{line:{color:p.negative,width:1},fillcolor:p.negative},
          text:candles.map(r => 'Apertura: '+num(r.open)+' USD<br>Máximo: '+num(r.high)+' USD<br>Mínimo: '+num(r.low)+' USD<br>Cierre: '+num(r.close)+' USD'),
          hoverinfo:'x+text+name',showlegend:false};
        const volume = bars('Volumen',x,candles.map(r => r.volume),candles.map(r => (r.close>=r.open?p.positive:p.negative)+'66'),'acciones');
        Object.assign(volume,{yaxis:'y2',showlegend:false});
        const operations = [false,true].map(estimated => {
          const name = estimated ? 'Precio aproximado' : 'Precio de ejecución';
          return {name,estimated,rows:sample.slice(-2).map((day,i) => {
            const candle = day[estimated ? 14+i*3 : 5+i*5];
            return {time:candle.x,price:estimated ? candle.close : round((candle.open+candle.close)/2),size:145000+i*47000};
          })};
        });
        const markers = operations.map(({name,estimated,rows}) => ({
          type:'scatter',mode:'markers',name,
            x:rows.map(r => interval === '1d' ? r.time.slice(0,10) : r.time),
            y:rows.map(r => r.price),
            customdata:rows.map(r => [r.size,r.time.replace('T',' ')]),marker:{size:11,color:estimated?p.amber:p.accent,symbol:estimated?'diamond-open':'circle',
              line:{width:2,color:p.panel}},
            hovertemplate:'%{customdata[1]}<br>%{y:,.2f} USD<br>%{customdata[0]:,d} acciones<extra>'+name+' · demo</extra>'
        }));
        return {interactive:true,legend:printsVisible,
          xaxis:{...timeAxis, tickformat:interval === '1d' ? '%d/%m' : '%d/%m %H:%M', hoverformat:'%d/%m/%Y %H:%M',
            rangeslider:{visible:false},
            rangebreaks:interval === '1d' ? [{bounds:['sat','mon']}] :
              [{bounds:['sat','mon']},{pattern:'hour',bounds:[16,9.5]}]},
          yaxis:{domain:[.27,1],range,title:{text:'USD'}},
          yaxis2:{domain:[0,.18],title:{text:'Volumen'},tickformat:'~s',rangemode:'tozero'},
          traces:[ohlc,volume,...(printsVisible ? markers : [])],
          headers:['Fecha/hora NY','Apertura · USD','Máximo · USD','Mínimo · USD','Cierre · USD','Volumen'],
          rows:candles.map(r => [r.x.replace('T',' '), ...['open','high','low','close'].map(k => num(r[k])),num(r.volume,0)]),
          extraValues:printsVisible ? () => [html('h3',null,'Operaciones de muestra'),table(
            ['Fecha/hora NY','Precio · USD','Acciones','Base del precio'],
            operations.flatMap(({name,rows}) => rows.map(r => [r.time.replace('T',' '),num(r.price),num(r.size,0),name]))
          )] : undefined};
      }}),
    columns(card('Off-exchange diario','Porcentaje del volumen por sesión · agregado de muestra',
      table(['Fecha','SPY','GLD','USO','BNO'],[[demoDate,'42,8 %','36,4 %','31,7 %','29,3 %'],['2026-11-12','40,2 %','39,0 %','34,1 %','30,0 %']])),
      card('ATS / OTC semanal','Ejemplo de resumen con retraso · recuentos agregados',
        table(['Semana','Activo','Acciones ATS','Acciones no ATS'],[['2026-10-26','SPY','53.400.000','25.200.000'],['2026-10-26','GLD','8.500.000','4.200.000']])) )
  ];
}

function options() {
  let ticker = 'SPX', expiry = 0;
  const expiries = ['2026-11-20','2026-12-18','2027-01-15'];
  const levels = html('div');
  const configured = () => {
    const a = assets[ticker];
    return {...a,flip:a.flip+a.step*expiry,call:a.call+a.step*expiry,put:a.put-a.step*expiry};
  };
  const refreshLevels = () => {
    const a = configured();
    const obs = ticker+' · exp. '+expiries[expiry]+' · '+demoDate;
    levels.replaceChildren(metrics(
      ['Spot',fmt(a.price,'USD'),ticker+' · '+demoDate],
      ['Gamma Flip',fmt(a.flip,'USD'),obs,null,String(a.flip)],
      ['Call Wall',fmt(a.call,'USD'),obs,'up',String(a.call)],
      ['Put Wall',fmt(a.put,'USD'),obs,'down',String(a.put)]));
  };
  const rows = () => {
    const a = configured(),center = Math.round(a.price/a.step)*a.step;
    return points(17,i => {
      const strike = round(center+(i-8)*a.step);
      const callDistance = ((strike-a.call)/a.step)**2;
      const putDistance = ((strike-a.put)/a.step)**2;
      const call = Math.round(4500+20000*Math.exp(-callDistance/4)+1800*(1+wave(i)));
      const put = Math.round(3200+24000*Math.exp(-putDistance/5)+2000*(1+wave(i+4)));
      return {strike,call,put,gex:round(a.scale*(call-put)/13000)};
    });
  };
  const charts = columns(
    staticChart('GEX por strike','Exposición gamma modelada · M USD por movimiento del 1 % · muestra',p => {
      const data = rows(), a = configured();
      const annotations = [[a.put,'Put Wall',p.negative],[a.flip,'Flip',p.amber],[a.call,'Call Wall',p.positive]];
      return {xaxis:{tickformat:'.2f',nticks:8,title:{text:'Strike · USD'}}, yaxis:{zerolinewidth:2,ticksuffix:' M'},
        traces:[bars('GEX',data.map(r => r.strike),data.map(r => r.gex),data.map(r => r.gex >= 0 ? p.positive : p.negative),'M USD / 1 %')],
        shapes:annotations.map(([x,,color]) => ({type:'line',x0:x,x1:x,yref:'paper',y0:0,y1:1,line:{color,width:1,dash:'dot'}})),
        annotations:annotations.map(([x,text,color],i) => ({x,text,yref:'paper',y:.97-i*.105,showarrow:false,bgcolor:p.panel,font:{color,size:10}})),
        headers:['Strike · USD','GEX · M USD / 1 %'],rows:data.map(r => [num(r.strike),signed(r.gex)])};
    }),
    staticChart('Open interest por strike','Contratos abiertos de calls y puts · escala desde cero',p => {
      const data = rows(),x = data.map(r => r.strike);
      return {legend:true,barmode:'group',xaxis:{tickformat:'.2f',nticks:8,title:{text:'Strike · USD'}},
        yaxis:{rangemode:'tozero',tickformat:'~s',title:{text:'Contratos'}},
        traces:[bars('Calls',x,data.map(r => r.call),p.accent,'contratos'),bars('Puts',x,data.map(r => r.put),p.accent2,'contratos')],
        headers:['Strike · USD','Calls · contratos','Puts · contratos'], rows:data.map(r => [num(r.strike),num(r.call,0),num(r.put,0)])};
    })
  );
  const term = staticChart('Estructura temporal de IV','IV ATM por vencimiento · porcentaje anualizado',p => {
    const offset = Object.keys(assets).indexOf(ticker)*2.3;
    const iv = [17.2,19.4,20.1].map(v => round(v+offset));
    return {xaxis:{type:'date',tickformat:'%d/%m/%Y'},yaxis:{ticksuffix:' %',title:{text:'IV ATM'}},
      traces:[line('IV ATM',expiries,iv,p.accent,'%',{mode:'lines+markers',marker:{size:8}})],
      headers:['Vencimiento','IV ATM'],rows:expiries.map((x,i) => [x,fmt(iv[i],'%')])};
  });
  const update = () => {
    refreshLevels();
    [...charts.querySelectorAll('.chart'),term.querySelector('.chart')].forEach(host => host.dispatchEvent(new Event('renew')));
  };
  refreshLevels();
  return [card('Cadena de opciones','Instrumentos y niveles sintéticos · las cifras sirven para evaluar la presentación.',
    controls(select('Activo',Object.entries(assets).map(([key,v]) => [key,key+' · '+v.name]),ticker,value => { ticker = value; update(); }),
      select('Vencimiento',expiries.map((d,i) => [i,d]),expiry,value => { expiry = Number(value); update(); }))),
    levels,charts,term,details('Lectura de niveles',html('p',{class:'hint'},'Gamma Flip, Call Wall y Put Wall se muestran como niveles de modelo. Comprueba activo, vencimiento y fecha antes de trasladar un nivel a TradingView.'))];
}

function curves() {
  let selected = 'Estados Unidos';
  const curves = {'Estados Unidos':[3.87,3.91,4.18,4.29,4.48,4.82,4.89],
    'Zona euro':[2.11,2.16,2.19,2.46,2.73,3.01,3.04],
    'Canadá':[2.48,2.54,2.69,2.93,3.16,3.4,3.49]};
  return [chart({title:'Curva de tipos soberana',desc:'Vencimientos observados en la muestra · rendimientos en porcentaje',
    toolbar:host => controls(select('Economía',Object.keys(curves).map(v => [v,v]),selected,value => {
      selected = value; host.dispatchEvent(new Event('renew'));
    })),
    make:p => {
      const y = curves[selected], prev = y.map((v,i) => round(v - .03 + i*.004));
      return {legend:true,yaxis:{ticksuffix:' %',title:{text:'Rendimiento'}},traces:[
        line(demoDate,widths,y,p.accent,'%',{mode:'lines+markers',marker:{size:7}}),
        line('Hace 5 sesiones',widths,prev,p.accent2,'%',{line:{color:p.accent2,dash:'dot',width:2}})],
      headers:['Vencimiento',demoDate,'Hace 5 sesiones'],rows:widths.map((x,i) => [x,fmt(y[i],'%'),fmt(prev[i],'%')])};
    }})];
}

function credit() {
  const hy = points(60,i => Math.round(337 + 27*wave(i/3) - (i-29)*.34));
  const ig = points(60,i => Math.round(102 + 11*wave(i/3+1) - (i-29)*.1));
  return [
    metrics(['HY OAS',fmt(hy.at(-1),'pb',0),demoDate],['IG OAS',fmt(ig.at(-1),'pb',0),demoDate],
      ['Liquidez · SOFR','4,02 %','Tipo overnight de muestra'],['Duración · TLT','−0,63 %','Rentabilidad de 5 sesiones']),
    staticChart('Diferenciales de crédito','Series HY e IG en puntos básicos · escala común',p => ({
      legend:true,xaxis:timeAxis,yaxis:{title:{text:'Puntos básicos'}},traces:[
        line('High yield',tickDates,hy,p.accent2,'pb'), line('Investment grade',tickDates,ig,p.accent,'pb')],
      headers:['Fecha','HY OAS · pb','IG OAS · pb'],rows:tickDates.map((d,i) => [d,hy[i],ig[i]])
    }))
  ];
}

const modules = {
  mercado:{title:'Panel de mercado',icon:'◈',desc:'Régimen, divisas y participación del mercado.',tabs:{
    resumen:['Resumen',overview],divisas:['Divisas y tipos',fx],amplitud:['Amplitud',breadth]}},
  sentimiento:{title:'Sentimiento',icon:'◐',desc:'Lecturas de riesgo en bolsa y cripto, con flujos de ETF spot.',tabs:{
    indicadores:['Fear & Greed',sentiment],flujos:['Flujos ETF',flows]}},
  posicionamiento:{title:'Posicionamiento',icon:'⇅',desc:'Distribución y evolución del posicionamiento por categoría.',tabs:{
    cot:['COT',cot]}},
  opciones:{title:'Opciones',icon:'Γ',desc:'Exposición gamma, open interest y volatilidad por vencimiento.',tabs:{
    cadena:['Cadena y niveles',options]}},
  liquidez:{title:'Liquidez y crédito',icon:'≈',desc:'Operaciones, volumen fuera de bolsa, curvas y diferenciales.',tabs:{
    dark:['Dark pools',darkPools],bonos:['Bonos y curvas',curves],credito:['Crédito',credit]}}
};

const root = document.documentElement;
const preference = (name,value) => {
  try {
    if (value === undefined) return localStorage.getItem('macroDesignLabV2.'+name);
    localStorage.setItem('macroDesignLabV2.'+name,value);
  } catch { /* File previews can disable storage. */ }
  return null;
};
function setMode(mode) {
  if (!['essential','advanced','ultra'].includes(mode)) return;
  root.dataset.mode = mode;
  document.querySelector('input[name=mode][value='+mode+']').checked = true;
  preference('mode',mode);
}
function setTheme(theme) {
  if (![...$('theme').options].some(x => x.value === theme)) return;
  root.dataset.theme = theme;
  $('theme').value = theme;
  preference('theme',theme);
  drawVisible();
}
const lastTab = new Map();
const views = new Map();
let selectedModule, selectedTab, activePanel;
let exitAnimation;
function hidePanel(panel) {
  exitAnimation?.cancel();
  panel.hidden = true;
  panel.inert = true;
  if (root.dataset.mode === 'essential' || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  panel.classList.remove('enter');
  panel.classList.add('exiting');
  exitAnimation = panel.animate([{opacity:.45},{opacity:0}],{duration:135,easing:'ease-out'});
  const cleanup = () => panel.classList.remove('exiting');
  exitAnimation.onfinish = cleanup;
  exitAnimation.oncancel = cleanup;
}
function drawVisible() {
  if (!activePanel) return;
  requestAnimationFrame(() => activePanel.querySelectorAll('.chart').forEach(host => drawChart(host)));
}
function openView(moduleKey,tabKey) {
  if (!Object.hasOwn(modules,moduleKey)) moduleKey = 'mercado';
  const {tabs,title,desc} = modules[moduleKey];
  if (!Object.hasOwn(tabs,tabKey)) tabKey = lastTab.get(moduleKey) ?? Object.keys(tabs)[0];
  if (selectedModule === moduleKey && selectedTab === tabKey) return;
  selectedModule = moduleKey; selectedTab = tabKey;
  lastTab.set(moduleKey,tabKey);
  $('section-label').textContent = 'PANEL GLOBAL / '+title.toUpperCase();
  $('section-title').textContent = title;
  $('section-description').textContent = desc;
  const key = moduleKey+'-'+tabKey;
  for (const link of $('modules').children) {
    if (link.dataset.module === moduleKey) link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  }
  const nav = $('modules');
  if (nav.scrollWidth > nav.clientWidth) {
    const selected = nav.querySelector('[aria-current]');
    const navBox = nav.getBoundingClientRect(), selectedBox = selected.getBoundingClientRect();
    if (selectedBox.left < navBox.left || selectedBox.right > navBox.right) {
      nav.scrollLeft += selectedBox.left - navBox.left;
    }
  }
  const buttons = Object.entries(tabs).map(([id,[name]]) => {
    const tab = html('button',{role:'tab',type:'button',id:'tab-'+moduleKey+'-'+id,
      'aria-controls':'panel-'+moduleKey+'-'+id,'aria-selected':String(id===tabKey),tabindex:id===tabKey?'0':'-1'},name);
    tab.addEventListener('click',() => { location.hash = moduleKey+'/'+id; });
    return tab;
  });
  const focusOnTabs = $('subtabs').contains(document.activeElement);
  $('subtabs').replaceChildren(...buttons);
  if (focusOnTabs) $('tab-'+key).focus();
  if (activePanel) hidePanel(activePanel);
  if (!views.has(key)) {
    const panel = html('section',{class:'panel-content',role:'tabpanel',tabindex:'0',id:'panel-'+key,'aria-labelledby':'tab-'+key},tabs[tabKey][1]());
    views.set(key,panel);
    $('panels').append(panel);
  }
  activePanel = views.get(key);
  activePanel.hidden = false;
  activePanel.inert = false;
  activePanel.classList.remove('exiting');
  activePanel.classList.remove('enter');
  const panel = activePanel;
  requestAnimationFrame(() => {
    if (panel !== activePanel) return;
    panel.classList.add('enter');
    drawVisible();
  });
}

for (const [id,{title,icon}] of Object.entries(modules)) {
  $('modules').append(html('a',{href:'#'+id,class:'module','data-module':id},
    html('span',{class:'module-icon','aria-hidden':'true'},icon),title));
}
$('subtabs').addEventListener('keydown',event => {
  const keys = ['ArrowLeft','ArrowRight','Home','End'];
  if (!keys.includes(event.key)) return;
  const tabKeys = Object.keys(modules[selectedModule].tabs);
  const last = tabKeys.length-1;
  const current = tabKeys.indexOf(selectedTab);
  const index = {Home:0,End:last,ArrowLeft:(current+last)%(last+1),ArrowRight:(current+1)%(last+1)}[event.key];
  event.preventDefault();
  location.hash = selectedModule+'/'+tabKeys[index];
});
$('theme').addEventListener('change',event => setTheme(event.target.value));
$('modes').addEventListener('change',event => setMode(event.target.value));
let lightFrame;
$('panels').addEventListener('pointermove',event => {
  if (root.dataset.mode !== 'ultra' || event.pointerType !== 'mouse' || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const tile = event.target.closest('.metric');
  if (!tile || lightFrame) return;
  const {clientX,clientY} = event;
  lightFrame = requestAnimationFrame(() => {
    const box = tile.getBoundingClientRect();
    tile.style.setProperty('--px',(clientX-box.left)+'px');
    tile.style.setProperty('--py',(clientY-box.top)+'px');
    lightFrame = null;
  });
});
const route = () => {
  if (location.hash === '#main') return;
  openView(...location.hash.slice(1).split('/'));
};
window.addEventListener('hashchange', route);
setMode(preference('mode') ?? 'advanced');
setTheme(preference('theme') ?? 'institutional');
if (location.hash === '#main') openView('mercado','resumen');
else route();
