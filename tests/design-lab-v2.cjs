'use strict';

// Run with Node and Playwright. Optional BROWSER_EXE points to an installed Chromium browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const bundled = path.resolve(path.dirname(process.execPath), '../node_modules/playwright');
const {chromium} = require(fs.existsSync(bundled) ? bundled : 'playwright');
const url = pathToFileURL(path.join(__dirname, '../design-lab-v2.html')).href;
const engine = 'https://cdn.plot.ly/plotly-2.35.2.min.js';
const themes = ['graphite','carbon','institutional','gold','mystic'];
const modes = ['essential','advanced','ultra'];

async function waitCharts(page, count) {
  await page.waitForFunction(count =>
    document.querySelectorAll('.panel-content:not([hidden]) .chart[data-ready]').length === count &&
    document.querySelectorAll('.panel-content:not([hidden]) .chart .main-svg').length >= count,
  count, {timeout:22000});
}
async function open(page, route, count = 0) {
  await page.evaluate(hash => { location.hash = hash; }, route);
  await page.locator('#panel-'+route.replace('/','-')+':visible').waitFor();
  if (count) await waitCharts(page,count);
}

(async () => {
  const browser = await chromium.launch({
    executablePath:process.env.BROWSER_EXE || undefined,
    args:['--disable-background-networking']
  });
  try {
    const desktop = await browser.newContext({viewport:{width:1440,height:1000}, permissions:['clipboard-read','clipboard-write']});
    const page = await desktop.newPage();
    const requests = [], errors = [];
    page.on('request',r => requests.push(r.url()));
    page.on('pageerror',err => errors.push(err.message));
    if (process.env.PLOTLY_TEST_BUNDLE) await desktop.route(engine, route => route.fulfill({
      path:process.env.PLOTLY_TEST_BUNDLE, contentType:'application/javascript'
    }));
    await page.goto(url,{waitUntil:'domcontentloaded'});
    assert.equal(await page.locator('html').getAttribute('data-mode'),'advanced');
    await waitCharts(page,2);
    const initialCharts = await page.locator('.chart').count();
    assert.equal(initialCharts,2,'Hidden modules must be mounted lazily');
    const metrics = await page.locator('.metric .value').allTextContents();
    for (const theme of themes) {
      await page.locator('#theme').selectOption(theme);
      for (const mode of modes) {
        await page.locator('input[value='+mode+']').check();
        assert.equal(await page.locator('html').getAttribute('data-mode'),mode);
        assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
        assert.deepEqual(await page.locator('.metric .value').allTextContents(),metrics);
      }
    }
    await page.locator('#theme').selectOption('carbon');
    await page.reload({waitUntil:'domcontentloaded'});
    assert.equal(await page.locator('html').getAttribute('data-mode'),'ultra');
    assert.equal(await page.locator('html').getAttribute('data-theme'),'carbon');
    await waitCharts(page,2);
    await page.locator('#subtabs [aria-selected=true]').press('ArrowRight');
    await page.getByRole('tab',{name:'Divisas y tipos',selected:true}).waitFor();

    await open(page,'opciones/cadena',3);
    const options = page.locator('#panel-opciones-cadena');
    await options.getByLabel('Activo',{exact:true}).selectOption('BNO');
    await options.getByLabel('Vencimiento',{exact:true}).selectOption('2');
    await page.waitForFunction(() => {
      const strikes = document.querySelector('#panel-opciones-cadena .chart')?.data?.[0]?.x;
      return strikes?.length === 17 && strikes[8] === 30.5;
    });
    const [gamma,oi,iv] = await options.locator('.chart').evaluateAll(charts => charts.map(c => c.data.map(t => Array.from(t.y))));
    assert(gamma[0].some(x => x < 0) && gamma[0].some(x => x > 0));
    assert(oi.flat().every(x => x >= 0));
    assert.equal(iv[0].length,3);
    await options.getByRole('button',{name:'Copiar Gamma Flip'}).click();
    const copyStatus = page.locator('#announcement');
    await page.waitForFunction(() => document.querySelector('#announcement').textContent.includes('Gamma Flip'));
    assert.match(await copyStatus.textContent(),/copiado|seleccionado/);
    await open(page,'sentimiento/indicadores',1);
    const sentiment = page.locator('#panel-sentimiento-indicadores .chart');
    const fg = await sentiment.evaluate(c => ({
      range:c.layout.yaxis.range, sameDates:JSON.stringify(c.data[0].x) === JSON.stringify(c.data[1].x),
      second:c.data[1].yaxis
    }));
    assert.deepEqual(fg,{range:[0,100],sameDates:true,second:'y2'});
    await open(page,'sentimiento/flujos',1);
    await page.locator('#panel-sentimiento-flujos').getByLabel('Período').selectOption('weekly');
    await page.waitForFunction(() => document.querySelector('#panel-sentimiento-flujos .chart').data?.[0]?.x?.length === 4);
    await open(page,'posicionamiento/cot',1);
    const cot = page.locator('#panel-posicionamiento-cot');
    await cot.getByLabel('Histórico').selectOption('13');
    await page.waitForFunction(() => document.querySelector('#panel-posicionamiento-cot .chart').data?.every(t => t.mode === 'lines+markers' && t.x.length === 13));

    await open(page,'liquidez/dark',1);
    const dark = page.locator('#panel-liquidez-dark');
    const plot = dark.locator('.chart');
    assert.equal(await plot.evaluate(c => c.data[0].type),'candlestick');
    await dark.getByLabel('Intervalo').selectOption('1h');
    await page.waitForFunction(() => document.querySelector('#panel-liquidez-dark .chart').data?.[0]?.x?.length === 42);
    const resetRange = () => plot.evaluate(c => [...c._fullLayout.xaxis.range]);
    let before = await resetRange();
    const area = await plot.locator('.nsewdrag').first().boundingBox();
    assert(area && area.width > 200);
    const y = area.y + area.height * .48;
    await page.mouse.move(area.x+area.width*.62,y);
    await page.mouse.down();
    await page.mouse.move(area.x+area.width*.39,y,{steps:9});
    await page.mouse.up();
    await page.waitForFunction(before => JSON.stringify(document.querySelector('#panel-liquidez-dark .chart')._fullLayout.xaxis.range)!==JSON.stringify(before),before);
    await dark.getByRole('button',{name:'Restablecer'}).click();
    await page.waitForFunction(() => document.querySelector('#panel-liquidez-dark .chart').layout.xaxis.autorange === true);
    before = await resetRange();
    await dark.getByRole('button',{name:'Ampliar región'}).click();
    await page.mouse.move(area.x+area.width*.24,y-25);
    await page.mouse.down();
    await page.mouse.move(area.x+area.width*.67,y+20,{steps:8});
    await page.mouse.up();
    await page.waitForFunction(before => JSON.stringify(document.querySelector('#panel-liquidez-dark .chart')._fullLayout.xaxis.range)!==JSON.stringify(before),before);
    const zoomed = await resetRange();
    await page.locator('input[value=essential]').check();
    await open(page,'liquidez/bonos',1);
    await open(page,'liquidez/credito',1);
    await open(page,'mercado/amplitud',1);
    await open(page,'liquidez/dark',1);
    assert.deepEqual(await resetRange(),zoomed);
    assert.equal(await dark.getByLabel('Intervalo').inputValue(),'1h');
    assert.equal(await plot.evaluate(c => c._fullLayout.dragmode),'zoom');
    await dark.getByRole('button',{name:'Operaciones'}).click();
    await page.waitForFunction(() => document.querySelector('#panel-liquidez-dark .chart').data?.length === 2);
    assert.deepEqual(await resetRange(),zoomed);
    await dark.getByRole('button',{name:'Operaciones'}).click();
    await page.waitForFunction(() => document.querySelector('#panel-liquidez-dark .chart').data?.length === 4);
    await page.locator('#theme').selectOption('gold');
    await page.waitForFunction(() => document.querySelector('#panel-liquidez-dark .chart').layout?.font?.color === '#f9f1e0');
    assert.deepEqual(await resetRange(),zoomed);
    assert.equal(await plot.evaluate(c => c._fullLayout.dragmode),'zoom');
    await dark.getByRole('button',{name:'Restablecer'}).click();
    await page.mouse.move(area.x+area.width*.5,y);
    await plot.locator('.hoverlayer text').first().waitFor();
    await open(page,'opciones/cadena',3);
    assert.equal(await options.getByLabel('Activo',{exact:true}).inputValue(),'BNO');
    assert.equal(await options.getByLabel('Vencimiento',{exact:true}).inputValue(),'2');
    assert.equal(requests.filter(r => r === engine).length,2,'One Plotly load per page load');
    assert(!requests.some(r => /macro-feed|stats-feed|v7-ui/.test(r)));
    assert.deepEqual(errors,[]);
    if (process.env.LAB_SCREENSHOT) await page.screenshot({path:process.env.LAB_SCREENSHOT});

    // JS/UI latency for already mounted tabs. This is not a sustained FPS or GPU benchmark.
    const timings = {};
    for (const mode of modes) {
      await page.locator('input[value='+mode+']').check();
      timings[mode] = await page.evaluate(async () => {
        const elapsed = [];
        const routes = ['mercado/divisas','mercado/resumen','liquidez/bonos','liquidez/dark'];
        for (let i=0;i<12;i++) {
          const start = performance.now();
          location.hash = routes[i%routes.length];
          await new Promise(resolve => window.addEventListener('hashchange',resolve,{once:true}));
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
          elapsed.push(performance.now()-start);
        }
        elapsed.sort((a,b) => a-b);
        return {medianMs:Math.round((elapsed[5]+elapsed[6])/2),maxMs:Math.round(elapsed.at(-1))};
      });
    }
    console.log('Cached tabs to second animation frame, headless Chrome, 12 switches/mode:',JSON.stringify(timings));

    const mobile = await browser.newContext({viewport:{width:390,height:844}, isMobile:true,hasTouch:true,reducedMotion:'reduce',
      deviceScaleFactor:1});
    if (process.env.PLOTLY_TEST_BUNDLE) await mobile.route(engine, route => route.fulfill({
      path:process.env.PLOTLY_TEST_BUNDLE, contentType:'application/javascript'
    }));
    const mobilePage = await mobile.newPage();
    await mobilePage.goto(url,{waitUntil:'domcontentloaded'});
    await waitCharts(mobilePage,2);
    await mobilePage.locator('input[value=ultra]').check();
    for (const hash of ['mercado/resumen','sentimiento/indicadores','opciones/cadena','liquidez/dark']) {
      const count = {'mercado/resumen':2,'opciones/cadena':3}[hash] ?? 1;
      await open(mobilePage,hash,count);
      assert.equal(await mobilePage.locator('.panel-content:not([hidden])').evaluate(n => getComputedStyle(n).animationName),'none');
      assert(await mobilePage.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    if (process.env.LAB_MOBILE_SCREENSHOT) await mobilePage.screenshot({path:process.env.LAB_MOBILE_SCREENSHOT});
    const fallback = await browser.newContext();
    await fallback.route(engine,route => route.abort());
    const offlinePage = await fallback.newPage();
    await offlinePage.goto(url,{waitUntil:'domcontentloaded'});
    await offlinePage.getByRole('button',{name:'Reintentar gráfico'}).first().waitFor();
    await offlinePage.locator('summary').first().click();
    await offlinePage.getByRole('table',{name:'Régimen de mercado'}).waitFor();
    console.log('OK · 5 themes × 3 modes, preserved data/state, keyboard tabs, all chart views, Plotly candles/drag/zoom/reset/hover, exact option values, mobile width and reduced motion.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode=1; });
