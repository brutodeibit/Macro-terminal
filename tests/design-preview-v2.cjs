'use strict';

// Run against the local preview server with real, unchanged repository feeds.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const bundled = path.resolve(path.dirname(process.execPath),'../node_modules/playwright');
const {chromium} = require(fs.existsSync(bundled) ? bundled : 'playwright');
const url = process.env.MACRO_PREVIEW_URL || 'http://127.0.0.1:8765';
const feed = JSON.parse(fs.readFileSync(path.join(__dirname,'../macro-feed-v7.json'),'utf8'));

async function ready(page) {
  await page.waitForFunction(() => typeof macroDatabase !== 'undefined' && macroDatabase.__feedMeta);
}
async function route(page,hash) {
  await page.evaluate(hash => { location.hash = hash; },hash);
  await page.locator('#v2-active-view').waitFor();
  await page.waitForFunction(() => !document.querySelector('#v2-active-view')?.hidden);
}
async function chart(page,selector) {
  await page.locator('#v2-active-view '+selector+'.js-plotly-plot').waitFor({timeout:30000});
}

(async () => {
  const browser = await chromium.launch({executablePath:process.env.BROWSER_EXE || undefined});
  try {
    const ctx = await browser.newContext({viewport:{width:1440,height:1000}});
    const old = await ctx.newPage();
    const page = await ctx.newPage();
    const errors = [], requests = [];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',req=>requests.push(req.url()));
    await Promise.all([page.goto(url+'/index.html'),old.goto(url+'/index.html?layout=classic')]);
    await Promise.all([ready(page),ready(old)]);
    assert.equal(await page.evaluate(()=>macroDatabase.__feedMeta.updated),feed.updated);
    assert.equal(await old.locator('html').evaluate(el=>el.classList.contains('macro-v2')),false);
    assert.deepEqual(await page.getByRole('navigation',{name:'Módulos globales'}).getByRole('button').allTextContents(),
      ['Panel de mercado','Sentimiento','Posicionamiento','Opciones','Dark Pools']);
    assert(!await page.locator('body').textContent().then(t=>t.includes('VISTA DE PRUEBA')));
    const capture = () => Object.entries(macroDatabase).filter(([key])=>key!=='__feedMeta');
    const digest = entries => Object.fromEntries(entries.map(([key,value])=>[
      key,createHash('sha256').update(JSON.stringify(value)).digest('hex')
    ]));
    const [a,b] = (await Promise.all([page.evaluate(capture),old.evaluate(capture)])).map(digest);
    assert.deepEqual(Object.keys({...a,...b}).filter(key=>a[key]!==b[key]),[],'Different macro database keys');
    assert.equal(await page.locator('#mainDashboard>[hidden]').count(),0);
    assert.equal(await page.locator('#sec-options').count(),0,'Hidden global modules render on demand');

    const sections = [
      ['global/mercado/regimen','#sec-risk'],['global/mercado/divisas','#sec-fx'],
      ['global/mercado/regiones','#sec-global-markets'],['global/mercado/rotacion','#sec-rotation'],
      ['global/sentimiento/bolsa','[data-sentiment-view=bolsa]'],['global/sentimiento/cripto','[data-sentiment-view=cripto]'],
      ['global/sentimiento/etf','#crypto-etf-flows'],['global/posicionamiento/cot','#sec-cot'],
      ['global/opciones/cadena','#sec-options'],['global/darkpools/dark','#sec-darkpool'],
      ['global/mercado/bonos','[data-sentiment-view=bonos]']
    ];
    for (const [hash,selector] of sections) {
      await route(page,hash);
      await page.locator('#v2-active-view '+selector+':visible').first().waitFor();
    }
    await route(page,'global/sentimiento/cripto');
    await chart(page,'#fg-v2-chart');
    assert.deepEqual(await page.locator('#fg-v2-chart').evaluate(el=>el.layout.yaxis.range),[0,100]);
    await route(page,'global/sentimiento/etf');
    await chart(page,'#crypto-etf-flow-chart');
    await route(page,'global/posicionamiento/cot');
    await chart(page,'#cot-interactive-chart');
    await route(page,'global/darkpools/dark');
    await chart(page,'.dp-chart-wrap');
    assert.equal(await page.locator('#v2-active-view .dp-chart-wrap').evaluate(el=>el.data[0].type),'candlestick');
    const dark = page.locator('#v2-active-view #sec-darkpool');
    await dark.getByRole('button',{name:'Ampliar región'}).click();
    await page.waitForFunction(()=>document.querySelector('#sec-darkpool .dp-chart-wrap')._fullLayout.dragmode==='zoom');

    const keys = ['us','eu','de','uk','jp','au','nz','ca','ch'];
    for (const key of keys) {
      await route(page,'economia/'+key+'/indicadores');
      await page.locator('#v2-active-view #sec-indicadores table').waitFor();
      assert.equal(await page.locator('#v2-active-view #sec-indicadores tbody tr').count(),feed.economies[key].indicators.length);
      assert.equal(await page.locator('#mainDashboard [data-economy-panel]').count(),6);
    }
    await route(page,'economia/us/curva');
    await chart(page,'#v7-curve-us');
    await route(page,'global/darkpools/dark');
    assert.equal(await dark.locator('.dp-chart-wrap').evaluate(el=>el._fullLayout.dragmode),'zoom');

    await route(page,'global/opciones/cadena');
    const active = page.locator('#v2-active-view');
    const compareOptions = await page.evaluate(() => {
      const market = macroDatabase.__options.markets.find(x=>x.ticker===window.__optTicker);
      return {ticker:market?.ticker,expiry:market && optionsSelectedProfile(market)?.expiration};
    });
    assert(compareOptions.ticker);
    if (compareOptions.expiry) {
      await chart(page,'#opt-oi-chart');
      assert(await active.locator('#opt-oi-chart').evaluate(el=>el.data.every(trace=>trace.type==='bar' && trace.y.every(y=>y>=0))));
      const putWall = active.getByRole('button',{name:'Copiar Put Wall'});
      if (await putWall.count()) {
        await putWall.click();
        await active.getByRole('status').filter({hasText:/Put Wall (copiado|seleccionado)/}).waitFor();
      }
    }
    const text = await active.locator('#sec-options').textContent();
    for (const theme of ['institutional','graphite','carbon','gold','mystic']) {
      await page.getByLabel('Tema visual').selectOption(theme);
      assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
      for (const mode of ['essential','advanced','ultra']) {
        await page.locator('input[name=v2-mode][value='+mode+']').check();
        assert.equal(await page.locator('html').getAttribute('data-mode'),mode);
      }
    }
    assert((await active.locator('#sec-options').textContent()).includes(text.trim().slice(0,80)));
    assert.equal(requests.filter(url=>url.endsWith('/macro-feed-v7.json')).length,1,'Navigation reuses the feed');
    assert.deepEqual(errors,[]);
    if (process.env.MACRO_PREVIEW_SCREEN) await page.screenshot({path:process.env.MACRO_PREVIEW_SCREEN});

    const mobile = await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,reducedMotion:'reduce'});
    const phone = await mobile.newPage();
    await phone.goto(url+'/index.html');
    await ready(phone);
    await phone.locator('#mobileCountrySelect').selectOption('jp');
    await phone.locator('#v2-active-view #sec-fx-weekly').waitFor();
    await phone.getByRole('tab',{name:'Indicadores'}).press('Enter');
    await phone.locator('#v2-active-view #sec-indicadores').waitFor();
    assert.equal(await phone.locator('#v2-active-view').evaluate(el=>getComputedStyle(el).animationName),'none');
    assert(await phone.evaluate(()=>document.documentElement.scrollWidth <= innerWidth));
    console.log('OK · same real feed, 11 global sections, 9 economies, 15 theme-mode combinations, financial charts and mobile navigation');
  } finally {
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
