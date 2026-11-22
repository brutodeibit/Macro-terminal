'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(path.resolve(path.dirname(process.execPath),'../node_modules/playwright'));
(async () => {
  const browser = await chromium.launch({executablePath:process.env.BROWSER_EXE});
  try {
    const page = await browser.newPage({viewport:{width:1365,height:900}});
    let posts=0, polls=0, hasJob=false;
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/api/refresh',async route => {
      let body;
      if (route.request().method()==='POST') {
        posts++; hasJob=true;
        assert.equal(route.request().postDataJSON().group,'options');
        body={id:'test-job',state:'running',group:'options',progress:[]};
      } else {
        if(hasJob)polls++;
        body={service:'macro-source-refresh-v1',job:hasJob?{
          id:'test-job',state:polls>1?'completed':'running',group:'options',
          progress:[{source:'OPTIONS',status:'unchanged_or_unavailable'}]
        }:null};
      }
      await route.fulfill({json:body});
    });
    await page.goto('http://127.0.0.1:8766/');
    await page.waitForFunction(()=>typeof macroDatabase!=='undefined'&&macroDatabase.__feedMeta);
    await page.locator('#sourceRefreshButton').click();
    await page.getByText('Servicio conectado.',{exact:false}).waitFor();
    await page.locator('#sourceRefreshStart').click();
    await page.waitForFunction(()=>document.getElementById('sourceRefreshStart').disabled);
    assert.equal(await page.locator('#sourceRefreshGroup').isDisabled(),true);
    await page.getByText('Consulta terminada y copia cargada.',{exact:false}).waitFor();
    assert.equal(posts,1);
    assert.equal(await page.locator('#sourceRefreshStart').isEnabled(),true);
    assert((await page.locator('#sourceRefreshProgress').textContent()).includes('Sin cambios o sin datos nuevos'));
    assert(!await page.locator('a[href*="actions/workflows/update-preview"]').count());
    assert.equal(browser.contexts()[0].pages().length,1);
    assert.equal(await page.evaluate(()=>macroDatabase.__feedMeta.source),'Consulta manual de fuentes');
    await page.getByLabel('Cerrar',{exact:true}).click();
    await page.setViewportSize({width:390,height:844});
    await page.route('**/api/refresh',route=>route.abort());
    await page.locator('#sourceRefreshButton').click();
    await page.getByText('El servicio de actualización no está conectado.',{exact:false}).waitFor();
    assert.equal(await page.locator('dialog').evaluate(el=>el.getBoundingClientRect().width<=innerWidth),true);
    assert.deepEqual(errors,[]);
    console.log('Source refresh UI: progress, single request, feed load, unavailable service, mobile and no GitHub navigation OK');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
