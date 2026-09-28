const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'), fixture=path.join(root,'test-results/scaling-fixture.html');
 await fs.mkdir(path.dirname(fixture),{recursive:true});
 const html=await fs.readFile(path.join(root,'household-network.html'),'utf8');
 // Test-only observation of the production mapping; never bundled in delivery.
 assert(html.includes('new ResizeObserver(resize)'));
 await fs.writeFile(fixture,html.replace('new ResizeObserver(resize)','window.scaleProbe = {style: scaledEdgeStyle, anchors: scaleAnchors}; new ResizeObserver(resize)'));
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE});
 try{
  const context=await browser.newContext({viewport:{width:1500,height:1100}});await context.setOffline(true);
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(fixture).href);
  const set=async(id,value)=>page.locator('#'+id).evaluate((el,value)=>{el.value=String(value);el.dispatchEvent(new Event('input',{bubbles:true}));},value);
  for(const metric of ['mi','r']){
   await page.locator(`input[name=metric][value=${metric}]`).check();
   const before=await page.evaluate(m=>{const p=window.scaleProbe,a=p.anchors[m];return {anchor:a,median:p.style(a.median,m),below:p.style(a.median/2,m)};},metric);
   await set('width-scale',3);
   const xmax=Number(await page.locator('#opacity-scale').getAttribute('max'));
   await set('opacity-scale',xmax);
   const result=await page.evaluate(m=>{const p=window.scaleProbe,a=p.anchors[m];return {median:p.style(a.median,m),below:p.style(a.median/2,m),max:p.style(a.max,m)};},metric);
   assert.deepEqual(result.median,before.median);
   assert.deepEqual(result.below,before.below);
   assert(Math.abs(result.max.width-9*before.anchor.width)<1e-9);
   assert(Math.abs(result.max.opacity-1)<1e-9);
   await set('opacity-scale',1);await set('width-scale',1);
   const flat=await page.evaluate(m=>{const p=window.scaleProbe,a=p.anchors[m];return p.style(a.max,m);},metric);
   assert.deepEqual(flat,before.median);
   await set('width-scale',metric==='mi'?2:3);
   await page.screenshot({path:path.join(root,`test-results/scaling-${metric}.png`),fullPage:true});
  }
  await page.locator('input[name=metric][value=mi]').check();assert.equal(Number(await page.locator('#width-scale').inputValue()),2);
  const anchor=await page.locator('#edge-scale-anchor').innerText();
  await set('threshold',0);await page.locator('#grouping').selectOption('mi');
  assert.equal(await page.locator('#edge-scale-anchor').innerText(),anchor);
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
  assert.deepEqual(errors,[]);
  console.log('PASS: fixed medians and lower scores; exact x²/y² maximum endpoints; opacity bounds; independent metric settings; filter/grouping stability; mobile/offline.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
