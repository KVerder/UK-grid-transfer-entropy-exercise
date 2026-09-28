/* Real browser integration checks against the computed, standalone HTML. */
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs/promises');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');
let launchedBrowser;
function csvLine(line) {
  const fields = [];
  let value = '', quoted = false;
  for (let i = 0; i < line.length; i++) {
    if (line[i] === '"') {
      if (quoted && line[i + 1] === '"') { value += '"'; i++; }
      else quoted = !quoted;
    } else if (line[i] === ',' && !quoted) { fields.push(value); value = ''; }
    else value += line[i];
  }
  fields.push(value);
  return fields;
}

(async () => {
  const root = path.resolve(__dirname, '..');
  const out = path.join(root, 'test-results');
  await fs.mkdir(out, {recursive: true});
  const browser = await chromium.launch({headless: true,
    ...(process.env.BROWSER_EXECUTABLE ? {executablePath: process.env.BROWSER_EXECUTABLE} : {})});
  launchedBrowser = browser;
  const context = await browser.newContext({viewport: {width: 1500, height: 1050}, acceptDownloads: true});
  await context.setOffline(true);
  const page = await context.newPage();
  const errors = [];
  const remoteRequests = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (/^https?:/.test(r.url())) remoteRequests.push(r.url()); });
  const url = pathToFileURL(process.env.HTML_PATH || path.join(root, 'household-network.html')).href;
  await page.goto(url);
  await page.waitForFunction(() => !document.querySelector('#visible-count').textContent.includes('Loading'));
  const data = await page.locator('#network-data').evaluate(el => JSON.parse(el.textContent));
  assert(data.nodes.length > 1, 'Real nodes must be embedded');
  assert(data.edges.length > 0, 'Computed edges must be embedded');
  assert.equal(await page.locator('#household-list option').count(), data.nodes.length);
  assert((await page.locator('#household-count').innerText()).replace(/,/g, '').includes(String(data.nodes.length)));
  assert(await page.locator('input[name=metric][value=r]').isChecked());
  await page.screenshot({path: path.join(out, 'review-overview.png'), fullPage: true});

  await page.locator('input[name=metric][value=mi]').check();
  assert.match(await page.locator('#threshold-label').innerText(), /MI|nats/i);
  assert.match(await page.locator('#graph-legend').innerText(), /MI|mutual|nats/i);
  const candidate = data.edges.find(e => e.mi > 0);
  const selectedId = data.nodes[candidate.s].id;
  await page.locator('#household-search').fill(selectedId);
  await page.locator('#search-form').evaluate(form => form.requestSubmit());
  await page.waitForFunction(id => document.querySelector('#selected-id').textContent === id, selectedId);
  assert(await page.locator('#selection-detail').isVisible());
  assert((await page.locator('#neighbor-table').innerText()).length > 0);
  await page.screenshot({path: path.join(out, 'review-mi-selection.png'), fullPage: true});

  const downloadPromise = page.waitForEvent('download');
  await page.locator('#export-edges').click();
  const download = await downloadPromise;
  const csvPath = path.join(out, 'visible-edges.csv');
  await download.saveAs(csvPath);
  const csv = await fs.readFile(csvPath, 'utf8');
  assert(csv.split(/\r?\n/).length > 1, 'Export must include header and edge rows');
  const exported = csv.trim().split(/\r?\n/).map(csvLine);
  assert.equal(exported[0][0], 'household_a');
  const idIndex = new Map(data.nodes.map((node, index) => [node.id, index]));
  const edgeIndex = new Map(data.edges.map(edge => [`${edge.s}:${edge.t}`, edge]));
  for (const row of exported.slice(1)) {
    const edge = edgeIndex.get(`${idIndex.get(row[0])}:${idIndex.get(row[1])}`);
    assert(edge, 'Exported pair must be a computed candidate');
    assert.equal(Number(row[3]), edge.mi, 'Exported MI must match computed data');
    assert.equal(Number(row[4]), edge.n, 'Exported overlap must match computed data');
    assert.equal(row[5], 'mutual_information_nats');
  }

  const constant = data.nodes.find(node => node.correlationEligible === false && node.miEligible === true);
  if (constant) {
    await page.locator('input[name=metric][value=r]').check();
    await page.locator('#household-search').fill(constant.id);
    await page.locator('#search-form').evaluate(form => form.requestSubmit());
    assert.match(await page.locator('#selected-status').innerText(), /undefined|constant/i);
    await page.locator('input[name=metric][value=mi]').check();
    assert.match(await page.locator('#selected-status').innerText(), /zero|MI\s*=\s*0|MI\s+is\s+0/i);
  }
  const insufficient = data.nodes.find(node => node.miEligible === false);
  if (insufficient) {
    await page.locator('#household-search').fill(insufficient.id);
    await page.locator('#search-form').evaluate(form => form.requestSubmit());
    assert.match(await page.locator('#selected-status').innerText(), /insufficient|below|fewer|unavailable/i);
  }

  await page.locator('#clear-selection').click();
  assert(await page.locator('#selection-empty').isVisible());
  await page.locator('input[name=metric][value=r]').check();
  for (const [selector, value] of [['#threshold', '1'], ['#edge-budget', '100']]) {
    await page.locator(selector).evaluate((el, value) => {
      el.value = value;
      el.dispatchEvent(new Event('input', {bubbles: true}));
    }, value);
  }
  const expectedCount = Math.min(100, data.edges.filter(e => typeof e.r === 'number' && Math.abs(e.r) >= 1).length);
  assert((await page.locator('#visible-count').innerText()).includes(`${expectedCount.toLocaleString('en-US')} filtered edges`));
  if (expectedCount === 0) assert(await page.locator('#graph-empty').isVisible());
  await page.locator('#threshold').evaluate(el => { el.value = '0.60'; el.dispatchEvent(new Event('input', {bubbles: true})); });
  await page.locator('#edge-budget').evaluate(el => { el.value = '2000'; el.dispatchEvent(new Event('input', {bubbles: true})); });
  await page.locator('#household-search').fill('HOUSEHOLD_DOES_NOT_EXIST');
  await page.locator('#search-form').evaluate(form => form.requestSubmit());
  assert((await page.locator('#search-message').innerText()).length > 0, 'Invalid IDs need a message');

  await page.locator('#zoom-in').click();
  await page.locator('#zoom-out').click();
  await page.locator('#fit').click();
  await page.locator('#network').focus();
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('0');
  await page.locator('#methods summary').click();
  assert(await page.locator('#method-metrics').isVisible());

  await page.setViewportSize({width: 390, height: 844});
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const resizedCanvas = await page.locator('#network').evaluate(canvas => canvas.toDataURL('image/png'));
  await page.locator('#fit').click();
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const refittedCanvas = await page.locator('#network').evaluate(canvas => canvas.toDataURL('image/png'));
  assert.equal(resizedCanvas, refittedCanvas, 'A fitted graph must stay fitted after desktop-to-mobile resize');
  await page.screenshot({path: path.join(out, 'review-mobile.png'), fullPage: true});
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  assert.equal(overflow, false, 'Mobile layout must not overflow horizontally');
  assert.deepEqual(errors, [], 'No runtime errors');
  assert.deepEqual(remoteRequests, [], 'Standalone HTML must not request network resources');
  console.log(JSON.stringify({nodes: data.nodes.length, candidateEdges: data.edges.length,
    offline: true, browserErrors: errors.length, mobileOverflow: overflow,
    checks: ['all-household search', 'metric toggle', 'selection', 'exact edge CSV values',
      'constant and low-coverage states', 'threshold and budget effects', 'invalid ID feedback',
      'zoom/fit/keyboard', 'methods', 'mobile fit preservation', 'offline']}, null, 2));
  await browser.close();
})().catch(async error => {
  console.error(error);
  if (launchedBrowser) await launchedBrowser.close();
  process.exitCode = 1;
});
