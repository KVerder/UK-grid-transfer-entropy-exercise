const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE});
 try{
  const context=await browser.newContext({viewport:{width:1500,height:1050}});await context.setOffline(true);
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.resolve(__dirname,'../household-network.html')).href);
  const frame=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  const bitmap=()=>page.locator('#network').evaluate(el=>el.toDataURL());
  await frame();const original=await bitmap();
  const nodes=await page.locator('#network-data').evaluate(el=>JSON.parse(el.textContent).nodes.length);
  for(const mode of ['mi','r']){
   await page.locator('#grouping').selectOption(mode);await frame();
   assert.notEqual(await bitmap(),original);
   assert.match(await page.locator('#layout-status').innerText(),/groups/);
   const positions=await page.locator('#network-data').evaluate((el,m)=>JSON.parse(el.textContent).layouts[m].positions,mode);
   assert.equal(positions.length,nodes);assert(positions.flat().every(Number.isFinite));
   await page.screenshot({path:path.resolve(__dirname,`../test-results/grouping-${mode}.png`),fullPage:true});
  }
  await page.locator('#reset-layout').click();await frame();
  assert((await bitmap())===original,'Reset must restore exactly the original fitted graph');
  await page.locator('#example-household').click();
  const selected=await page.locator('#selected-id').innerText();
  const threshold=await page.locator('#threshold').inputValue();
  await page.locator('#grouping').selectOption('mi');
  assert.equal(await page.locator('#selected-id').innerText(),selected);
  assert.equal(await page.locator('#threshold').inputValue(),threshold);
  await page.locator('input[value=mi]').check();
  assert.equal(await page.locator('#grouping').inputValue(),'mi');
  await page.locator('#reset-layout').click();assert.equal(await page.locator('#selected-id').innerText(),selected);
  await page.setViewportSize({width:390,height:844});
  await page.locator('#grouping').selectOption('r');await frame();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
  await page.screenshot({path:path.resolve(__dirname,'../test-results/grouping-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);console.log('PASS: both metric layouts, exact reset, preserved selection/filters, independent edge metric, mobile/offline.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
