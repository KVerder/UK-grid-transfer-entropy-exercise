const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE});
 try{
  const context=await browser.newContext();await context.setOffline(true);
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(root,'household-network.html')).href);
  const data=await page.locator('#network-data').evaluate(el=>JSON.parse(el.textContent));
  const compare=async(a,b)=>{
   await page.locator('#pair-a').fill(a);await page.locator('#pair-b').fill(b);
   await page.locator('#pair-form').evaluate(f=>f.requestSubmit());
  };
  const candidate=data.edges.find(e=>e.mi>0&&Number.isFinite(e.r));
  await compare(data.nodes[candidate.s].id,data.nodes[candidate.t].id);
  assert(await page.locator('#pair-results').isVisible());
  assert(Math.abs(parseFloat(await page.locator('#pair-r').innerText())-candidate.r)<0.00000051);
  assert(Math.abs(parseFloat(await page.locator('#pair-mi').innerText())-candidate.mi)<0.00000051);
  const present=new Set(data.edges.map(e=>`${e.s}:${e.t}`));
  let t=1;while(present.has(`0:${t}`))t++;
  await compare(data.nodes[0].id,data.nodes[t].id);
  assert.match(await page.locator('#pair-status').innerText(),/outside the sparse graph/);
  await page.locator('#pair-file').setInputFiles(path.join(root,'analysis/household-pairs.gspairs'));
  await page.waitForFunction(()=>!document.querySelector('#pair-results').hidden);
  const file=await fs.open(path.join(root,'analysis/household-pairs.gspairs'),'r');
  const prefix=Buffer.alloc(12);await file.read(prefix,0,12,0);const base=12+prefix.readUInt32LE(8);
  const record=Buffer.alloc(10);await file.read(record,0,10,base+(t-1)*10);await file.close();
  assert(Math.abs(parseFloat(await page.locator('#pair-r').innerText())-record.readFloatLE(0))<0.00000051);
  assert(Math.abs(parseFloat(await page.locator('#pair-mi').innerText())-record.readFloatLE(4))<0.00000051);
  assert.equal(Number((await page.locator('#pair-n').innerText()).replaceAll(',','')),record.readUInt16LE(8));
  const previous=await page.locator('#pair-results').innerText();
  await compare(data.nodes[t].id,data.nodes[0].id);
  await page.waitForFunction(()=>!document.querySelector('#pair-results').hidden);
  assert.equal(await page.locator('#pair-results').innerText(),previous);
  await compare(data.nodes[0].id,data.nodes[0].id);assert.match(await page.locator('#pair-status').innerText(),/different/);
  await compare('INVALID',data.nodes[0].id);assert.match(await page.locator('#pair-status').innerText(),/valid/);
  await page.locator('#pair-file').setInputFiles({name:'wrong.gspairs',mimeType:'application/octet-stream',buffer:Buffer.from('not a GSclone file')});
  await page.waitForFunction(()=>document.querySelector('#pair-file-status').textContent.includes('Choose a GSclone'));
  assert.deepEqual(errors,[]);
  console.log('PASS: embedded pair, arbitrary full-file pair, exact values, reversed IDs, same/invalid ID feedback, wrong-file rejection, offline.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
