(() => {
  'use strict';
  if (new URLSearchParams(location.search).get('design') !== 'v2') return;

  const themes = [
    ['institutional','Institutional Blue'], ['graphite','Graphite Pro'],
    ['carbon','Carbon Turquoise'], ['gold','Obsidian Gold'], ['mystic','Mystic Carbon']
  ];
  const modes = [['essential','Esencial'],['advanced','Avanzado'],['ultra','Ultra']];
  const globalGroups = [
    ['mercado','Panel de mercado',[
      ['resumen','Resumen','sec-resumen'],['regimen','Régimen','sec-risk'],
      ['divisas','Divisas y carry','sec-fx'],['regiones','Mercados regionales','sec-global-markets'],
      ['rotacion','Rotación','sec-rotation']
    ]],
    ['sentimiento','Sentimiento',[
      ['bolsa','Bolsa y amplitud','sec-sentiment'],['cripto','Crypto Fear & Greed','sec-sentiment'],
      ['etf','Flujos ETF spot','sec-sentiment']
    ]],
    ['posicionamiento','Posicionamiento',[['cot','COT','sec-cot']]],
    ['opciones','Opciones',[['cadena','Cadena y niveles','sec-options']]],
    ['liquidez','Liquidez y crédito',[
      ['dark','Dark pools / OTC','sec-darkpool'],['bonos','Bonos y crédito','sec-sentiment']
    ]]
  ];
  const economyTabs = [
    ['semana','Sesgo semanal','sec-fx-weekly'],['tipos','Tipos y expectativas','sec-tipos'],
    ['central','Banco central','sec-conferencia'],['lectura','Lectura macro','v2-macro-reading'],
    ['curva','Curva soberana','sec-bonos'],['indicadores','Indicadores','sec-indicadores']
  ];

  const $ = id => document.getElementById(id);
  const root = document.documentElement;
  const dashboard = $('mainDashboard');
  const sidebar = $('countryNav');
  const classicRender = renderContent;
  const classicSidebar = renderSidebar;
  const classicScroll = scrollToSection;
  const classicFeedStatus = setFeedStatus;
  const plots = new WeakMap();
  const globalPanels = new Map();
  const lastEconomyTab = new Map();
  const lastGlobalTab = new Map();
  let countryRendered, feedRevision, groupKey = 'mercado', tabKey = 'resumen', active, chrome;

  function make(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [key,value] of Object.entries(attrs ?? {})) el.setAttribute(key,value);
    el.append(...children.flat());
    return el;
  }
  function button(text, action, attrs = {}) {
    const el = make('button',{type:'button',...attrs},text);
    el.addEventListener('click',action);
    return el;
  }
  function readPreference(key,choices,fallback) {
    try {
      const value = localStorage.getItem('macroPreviewV2.'+key);
      if (choices.some(([candidate]) => candidate === value)) return value;
    } catch {}
    return fallback;
  }
  function savePreference(key,value) {
    root.dataset[key] = value;
    try { localStorage.setItem('macroPreviewV2.'+key,value); } catch {}
  }
  savePreference('theme',readPreference('theme',themes,'institutional'));
  savePreference('mode',readPreference('mode',modes,'advanced'));
  root.classList.add('macro-v2');
  document.body.classList.remove('theme-warm','theme-carbon');
  document.title = 'Macro Monitor · Vista de prueba V2';
  document.head.append(make('link',{rel:'stylesheet',href:'design-preview-v2.css'}));

  const classicPalette = v7Palette;
  v7Palette = function () {
    const style = getComputedStyle(document.body);
    const token = (name,fallback) => style.getPropertyValue('--v2-'+name).trim() || fallback;
    const p = classicPalette();
    return {panel:token('panel',p.panel),ink:token('ink',p.ink),grid:token('line',p.grid),accent:token('accent',p.accent)};
  };

  function drawVisible() {
    if (!active) return;
    const panel = active;
    requestAnimationFrame(() => {
      if (active !== panel) return;
      for (const el of panel.querySelectorAll('.v2-plot-host, .js-plotly-plot')) {
        if (el.closest('[hidden]')) continue;
        const plot = plots.get(el);
        if (plot?.pending) plot.pending();
        else if (el._fullLayout) {
          updatePlotColors(el);
          window.Plotly?.Plots.resize(el);
        }
      }
    });
  }
  function updatePlotColors(el) {
    const p = v7Palette(), layout = el._fullLayout;
    if (!layout) return;
    const colors = {'font.color':p.ink,'hoverlabel.bgcolor':p.panel,'hoverlabel.font.color':p.ink};
    for (const key of Object.keys(layout).filter(key => /^(x|y)axis\d*$/.test(key))) {
      colors[key+'.gridcolor'] = p.grid;
      colors[key+'.tickfont.color'] = p.ink;
    }
    if (el.id === 'opt-oi-chart') {
      const secondary = getComputedStyle(document.body).getPropertyValue('--v2-accent2').trim();
      window.Plotly.restyle(el,{'marker.color':[p.accent,secondary]},[0,1]);
    }
    window.Plotly.relayout(el,colors);
  }
  function darkTools(el,P) {
    if (!el.matches('#sec-darkpool .dp-chart-wrap') || el.previousElementSibling?.classList.contains('v2-chart-tools')) return;
    const bar = make('div',{class:'v2-chart-tools','aria-label':'Interacción con el gráfico de velas'});
    for (const [value,label] of [['pan','Desplazar'],['zoom','Ampliar región']]) {
      const control = button(label,() => {
        for (const child of bar.children) child.setAttribute('aria-pressed',String(child === control));
        P.relayout(el,{dragmode:value});
      },{'aria-pressed':String(value === 'pan')});
      bar.append(control);
    }
    el.before(bar);
  }
  function configurePlotly() {
    const load = __loadPlotly;
    __loadPlotly = function () {
      return load().then(P => {
        if (P.__macroPreviewV2) return P;
        P.__macroPreviewV2 = true;
        const originalPlot = P.newPlot;
        P.newPlot = function (element,traces,layout,config) {
          const el = typeof element === 'string' ? $(element) : element;
          if (!el || !el.isConnected) return Promise.resolve(el);
          el.classList.add('v2-plot-host');
          const p = v7Palette();
          const axis = layout.yaxis ?? {};
          layout = {...layout, yaxis:{...axis}, font:{...layout.font,color:p.ink}};
          config = {...config,showTips:false};
          if (el.id === 'opt-oi-chart') {
            const colors = [p.accent,getComputedStyle(document.body).getPropertyValue('--v2-accent2').trim()];
            traces = traces.map((trace,i) => ({type:'bar',x:trace.x,y:trace.y,name:trace.name,
              marker:{color:colors[i]},hovertemplate:trace.hovertemplate}));
            layout.barmode = 'group';
            layout.yaxis.rangemode = 'tozero';
          }
          if (el.id === 'opt-gex-chart') {
            layout.yaxis.zerolinewidth = 2;
            layout.yaxis.zerolinecolor = p.ink;
            layout.margin = {...layout.margin,r:28};
          }
          if (el.id === 'opt-oi-chart' || el.id === 'opt-gex-chart') {
            layout.xaxis = {...layout.xaxis,fixedrange:true};
            layout.yaxis.fixedrange = true;
            config.scrollZoom = false;
          }
          if (el.matches('#sec-darkpool .dp-chart-wrap')) {
            layout.hoverdistance = 30;
            layout.xaxis = {...layout.xaxis,showspikes:true,spikemode:'across',spikesnap:'cursor'};
          }
          const draw = () => {
            plots.delete(el);
            if (!el.isConnected) return Promise.resolve(el);
            return Promise.resolve(originalPlot.call(P,el,traces,layout,config)).then(() => {
              if (el.isConnected) { darkTools(el,P); updatePlotColors(el); }
              return el;
            }).catch(error => {
              if (el.isConnected) {
                el.append(make('p',{class:'v2-message',role:'status'},'Este gráfico no pudo dibujarse. Sus datos y avisos siguen en el panel.'));
                console.warn('Macro Monitor · Plotly',error);
              }
              return el;
            });
          };
          if (el.closest('[hidden]')) {
            plots.set(el,{pending:draw});
            return Promise.resolve(el);
          }
          return draw();
        };
        return P;
      });
    };
  }

  function copyLevels(panel) {
    const market = macroDatabase.__options?.markets?.find(m => m.ticker === window.__optTicker);
    const profile = market && optionsSelectedProfile(market);
    if (!profile) return;
    const levels = [
      ['Gamma Flip','GAMMA FLIP',profile.gammaFlip ?? profile.zeroGamma],
      ['Call Wall','CALL WALL · OI',profile.callWallOi ?? profile.callWall],
      ['Put Wall','PUT WALL · OI',profile.putWallOi ?? profile.putWall]
    ].map(([name,label,value]) => [name,label,__optNum(value)]).filter(([, ,value]) => value > 0);
    if (!levels.length) return;
    const status = make('span',{class:'v2-message',role:'status'});
    let grid;
    for (const [name,label,value] of levels) {
      const card = [...panel.querySelectorAll('.metric')].find(el => el.firstElementChild?.textContent === label);
      const displayed = card?.querySelector('b,strong');
      if (!displayed) continue;
      grid = card.parentElement;
      const copy = button('Copiar',async () => {
        try {
          await navigator.clipboard.writeText(String(value));
          status.textContent = name+' copiado';
        } catch {
          const range = document.createRange();
          range.selectNodeContents(displayed);
          getSelection().removeAllRanges();
          getSelection().addRange(range);
          status.textContent = name+' seleccionado para copiar';
        }
      },{'aria-label':'Copiar '+name,title:'Copiar valor del dato: '+value});
      card.classList.add('v2-level');
      card.append(copy);
    }
    if (!grid) return;
    const detail = [market.ticker,profile.contractCode,profile.expiration,
      market.asOf || market.sourceDate || market.quote?.asOf,market.source].filter(Boolean).join(' · ');
    grid.after(make('div',{class:'v2-level-meta'},make('p',null,detail),status));
  }

  function emptyPanels() {
    for (const chart of dashboard.querySelectorAll('.js-plotly-plot')) window.Plotly?.purge(chart);
    dashboard.replaceChildren();
    globalPanels.clear();
    countryRendered = undefined;
    active = null;
  }
  function setupSentiment(container) {
    const section = container.querySelector('#sec-sentiment');
    const flow = section?.querySelector('#crypto-etf-flows');
    const children = [...(section?.children ?? [])];
    const index = children.indexOf(flow);
    if (index < 2 || index === children.length-1) return;
    children.forEach((node,i) => {
      node.dataset.sentimentView = i === 0 ? 'bolsa' : i === index ? 'etf' : i > index ? 'bonos' : 'cripto';
    });
  }
  function mountGlobal(id,replace) {
    if (!globalPanels.has(id) || replace) {
      const old = globalPanels.get(id);
      if (old) {
        for (const chart of old.querySelectorAll('.js-plotly-plot')) window.Plotly?.purge(chart);
        old.remove();
      }
      const panel = make('section',{class:'v2-view',hidden:'',role:'tabpanel'});
      try { panel.innerHTML = renderGlobalView(id); }
      catch (error) {
        console.error('Macro Monitor · panel',error);
        panel.append(make('p',{class:'v2-message',role:'status'},'El panel no pudo mostrarse en esta actualización.'));
      }
      if (id === 'sec-sentiment') setupSentiment(panel);
      if (id === 'sec-options') copyLevels(panel.querySelector('#sec-options') || panel);
      globalPanels.set(id,panel);
      dashboard.append(panel);
    }
    const panel = globalPanels.get(id);
    if (id === 'sec-sentiment') for (const child of panel.querySelectorAll('[data-sentiment-view]')) {
      child.hidden = child.dataset.sentimentView !== tabKey;
    }
    return panel;
  }

  function mountEconomy() {
    const kept = [...globalPanels.values()];
    for (const node of [...dashboard.children]) {
      if (!kept.includes(node)) {
        for (const chart of node.querySelectorAll('.js-plotly-plot')) window.Plotly?.purge(chart);
      }
      node.remove();
    }
    kept.forEach(panel => { panel.hidden = true; });
    classicRender();
    const sections = new Map(economyTabs.filter(([, ,id])=>id!=='v2-macro-reading').map(([, ,id])=>[id,id]));
    let id = 'sec-fx-weekly';
    const items = [...dashboard.children];
    const panels = new Map();
    for (const node of items) {
      if (sections.has(node.id)) id = node.id;
      else if (id === 'sec-conferencia') id = 'v2-macro-reading';
      if (!panels.has(id)) panels.set(id,make('section',{class:'v2-view',hidden:'',role:'tabpanel','data-economy-panel':id}));
      panels.get(id).append(node);
    }
    dashboard.replaceChildren(...kept,...panels.values());
    countryRendered = currentCountryKey;
  }
  function selectCountry(key) {
    const tab = key === '__global' ? groupKey+'/'+(lastGlobalTab.get(groupKey)||'') : key+'/'+(lastEconomyTab.get(key)||'');
    navigate((key === '__global' ? 'global/' : 'economia/')+tab);
  }
  function navigate(route) {
    if (location.hash === '#'+route) return;
    history.pushState(null,'','#'+route);
    renderRoute();
  }
  function buildTabs(tabs) {
    const list = $('topTabs');
    const focus = list.contains(document.activeElement);
    list.setAttribute('role','tablist');
    list.setAttribute('aria-label','Apartados');
    list.replaceChildren(...tabs.map(([key,label]) => button(label,() => {
      navigate(currentCountryKey === '__global' ? 'global/'+groupKey+'/'+key : 'economia/'+currentCountryKey+'/'+key);
    },{id:'v2-tab-'+key,role:'tab','aria-selected':String(tabKey===key),
      'aria-controls':'v2-active-view',tabindex:tabKey===key?'0':'-1'})));
    if (focus) list.querySelector('[aria-selected=true]')?.focus();
  }
  function refreshNavigation(tabs) {
    const global = currentCountryKey === '__global';
    chrome.groups.hidden = !global;
    for (const item of chrome.groups.children) item.setAttribute('aria-pressed',String(item.dataset.group===groupKey));
    chrome.context.textContent = global ? 'Panel global' : 'Economías / '+(macroDatabase[currentCountryKey]?.name || currentCountryKey);
    buildTabs(tabs);
  }
  function show(panel) {
    for (const view of dashboard.children) {
      view.hidden = view !== panel;
      if (view === panel) {
        view.id = 'v2-active-view';
        view.setAttribute('aria-labelledby','v2-tab-'+tabKey);
      } else view.removeAttribute('id');
    }
    if (active !== panel && panel) {
      panel.classList.remove('v2-enter');
      requestAnimationFrame(() => { if (active === panel) panel.classList.add('v2-enter'); });
    }
    active = panel;
    drawVisible();
  }
  function renderActive({replace=false} = {}) {
    if (feedRevision !== macroDatabase.__feedMeta) {
      feedRevision = macroDatabase.__feedMeta;
      emptyPanels();
    }
    const global = currentCountryKey === '__global';
    const group = globalGroups.find(([key]) => groupKey === key);
    const tabs = global ? group[2] : economyTabs;
    const [key,,sectionId] = tabs.find(([id]) => id === tabKey) ?? tabs[0];
    tabKey = key;
    refreshNavigation(tabs);
    if (global) {
      $('countryTitle').textContent = group[1];
      $('countrySubtitle').textContent = 'Monitor Macro Global';
      show(mountGlobal(sectionId,replace));
    } else {
      if (countryRendered !== currentCountryKey || replace) mountEconomy();
      show(dashboard.querySelector('[data-economy-panel="'+sectionId+'"]') ?? dashboard.firstElementChild);
    }
  }
  function renderRoute() {
    const [scope,id,tab] = location.hash.slice(1).split('/');
    if (scope === 'economia' && Object.hasOwn(macroDatabase,id) && macroDatabase[id]?.id) {
      currentCountryKey = id;
      tabKey = economyTabs.some(([key]) => tab === key) ? tab : lastEconomyTab.get(id) || 'semana';
      lastEconomyTab.set(id,tabKey);
    } else {
      currentCountryKey = '__global';
      if (globalGroups.some(([key])=>key===id)) groupKey = id;
      const group = globalGroups.find(([key]) => groupKey === key);
      tabKey = group[2].some(([key]) => tab === key) ? tab : lastGlobalTab.get(groupKey)||group[2][0][0];
      lastGlobalTab.set(groupKey,tabKey);
    }
    renderSidebar();
    renderActive();
    document.querySelector('main').scrollTo({top:0,behavior:'instant'});
  }

  function buildChrome() {
    const originalHeader = $('countryTitle').closest('header');
    originalHeader.classList.add('v2-header');
    originalHeader.querySelector('[aria-label="Apariencia"]')?.setAttribute('hidden','');
    const context = make('span',{class:'v2-context'},'Panel global');
    const select = make('select',{'aria-label':'Tema visual'},themes.map(([key,name])=>make('option',{value:key},name)));
    select.value = root.dataset.theme;
    select.addEventListener('change',() => { savePreference('theme',select.value); drawVisible(); });
    const segmented = make('fieldset',{class:'v2-modes'},make('legend',{class:'sr-only'},'Modo de presentación'));
    for (const [key,name] of modes) {
      const input = make('input',{type:'radio',name:'v2-mode',value:key});
      input.checked = root.dataset.mode === key;
      input.addEventListener('change',() => savePreference('mode',key));
      segmented.append(make('label',null,input,make('span',null,name)));
    }
    const toolbar = make('div',{class:'v2-topbar'},context,
      make('div',{class:'v2-preferences'},make('label',null,'Tema ',select),segmented));
    originalHeader.before(toolbar);
    $('countryTitle').before(make('div',{class:'v2-kicker'},'MACRO MONITOR ',make('span',null,'VISTA DE PRUEBA V2')));
    const groups = make('nav',{class:'v2-groups','aria-label':'Módulos globales'},globalGroups.map(([id,name]) =>
      button(name,()=>navigate('global/'+id+'/'+(lastGlobalTab.get(id)||'')),{'data-group':id})));
    $('topTabs').before(groups);
    $('topTabs').addEventListener('keydown',event => {
      const list = [...$('topTabs').children];
      const i = list.indexOf(document.activeElement), n = list.length;
      if (i<0 || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      const next = {ArrowLeft:(i+n-1)%n,ArrowRight:(i+1)%n,Home:0,End:n-1}[event.key];
      event.preventDefault(); list[next].click();
    });
    return {context,groups};
  }

  chrome = buildChrome();
  renderTopTabs = () => {};
  renderSidebar = function () {
    classicSidebar();
    sidebar.querySelector('.nav-item.active')?.setAttribute('aria-current','page');
  };
  renderContent = () => renderActive({replace:true});
  setFeedStatus = function (message,ok) {
    const local = ['127.0.0.1','localhost'].includes(location.hostname);
    classicFeedStatus(local ? message.replace('GitHub Pages','copia local del feed') : message,ok);
  };
  switchCountry = selectCountry;
  scrollToSection = function (id) {
    const global = currentCountryKey === '__global';
    const globalTab = global && globalGroups.flatMap(([key,,tabs])=>tabs.map(t=>[key,...t])).find(([, , , section])=>section===id);
    const economy = !global && economyTabs.find(([, ,section])=>section===id);
    if (globalTab) navigate('global/'+globalTab[0]+'/'+globalTab[1]);
    else if (economy) navigate('economia/'+currentCountryKey+'/'+economy[0]);
    else classicScroll(id);
  };
  window.addEventListener('DOMContentLoaded',() => {
    configurePlotly();
    renderRoute();
  });
  window.addEventListener('hashchange',renderRoute);
})();
