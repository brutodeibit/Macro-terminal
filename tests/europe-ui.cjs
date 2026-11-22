'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(path.resolve(path.dirname(process.execPath),'../node_modules/playwright'));
const feed=JSON.parse(fs.readFileSync('macro-feed-v7.json','utf8'));
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.BROWSER_EXE});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8766/#global/opciones/cadena');
  await page.waitForFunction(()=>typeof macroDatabase!=='undefined'&&macroDatabase.__feedMeta);
  const market=feed.options.markets.find(m=>m.ticker==='SX5E'),profile=market.profiles.find(p=>p.contractCode==='OESX'&&p.settlementModel?.status==='derived');
  assert(profile,'Real validated OESX profile required for this integration check');
  await page.evaluate(p=>{window.__optTicker='SX5E';window.__optFamily='EURO STOXX';window.__optExpiration=p.contractCode+':'+p.expiration;renderContent();},profile);
  await page.getByText('Europa · OESX · modelo diario de liquidación',{exact:true}).waitFor();
  await page.waitForFunction(()=>document.getElementById('opt-gex-chart')?.data?.length);
  const state=await page.locator('#opt-gex-chart').evaluate(el=>({bars:el.data[0].type,unit:el.layout.yaxis.title.text,values:el.data[0].y}));
  assert.equal(state.bars,'bar');assert(state.unit.includes('EUR'));assert(state.values.some(v=>v!==null));
  await page.waitForFunction(()=>document.getElementById('opt-term-chart')?.data?.length);
  assert(await page.locator('#opt-term-chart').evaluate(el=>el.data[0].customdata.every(row=>row[2]==='Eurex · OESX')));
  await page.locator('#opt-gex-chart').screenshot({path:'.test-tmp/europe-gex-real.png'});
  await page.evaluate(()=>{location.hash='economia/eu/indicadores';});
  const table=page.locator('#v2-active-view #sec-indicadores');await table.waitFor();
  assert((await table.textContent()).includes('Periodo: 2026-10'));
  assert((await table.textContent()).includes('Eurostat · EA21'));
  assert((await table.textContent()).includes('Publicación sin fecha verificada'));
  assert(await table.locator('tbody tr').filter({hasText:'IPC Subyacente Eurozona'}).locator('td').nth(3).textContent().then(t=>t==='—'));
  await page.evaluate(()=>{location.hash='global/darkpools/dark';});
  await page.getByText('Fuentes, precisión y cobertura de operaciones',{exact:true}).waitFor();
  await page.evaluate(()=>{window.__darkPoolTicker='AAPL';window.__darkTimeframe='1h';renderContent();});
  assert((await page.locator('#v2-active-view #sec-darkpool').textContent()).includes('PROVIDER REPORTED'));
  assert(await page.locator('#v2-active-view #sec-darkpool tbody tr').count()>0,'Date-only records remain in the table during intraday mode');
  await page.evaluate(()=>{macroDatabase.__darkPoolPrints.assets.AAPL.dailyOffExchange.offExchangePct=null;renderContent();});
  assert((await page.getByText('OFF-EXCH',{exact:true}).locator('..').textContent()).includes('—'));
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'.test-tmp/europe-real-ui.png',fullPage:false});
  console.log('Europe UI: real OESX GEX, EUR units, separate contract curves, official macro and retained date-only rows OK');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
