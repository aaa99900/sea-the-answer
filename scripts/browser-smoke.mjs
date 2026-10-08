// Optional real-browser integration check. Uses Chrome's DevTools protocol and an isolated PostgreSQL test server.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { readFile, mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createServer } from 'node:net';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import { openDatabase, importDocuments } from '../backend/db.mjs';
import { lanInterfaces } from '../backend/network.mjs';
import { socketDatabase } from '../tests/support/postgres.mjs';

const workspace = fileURLToPath(new URL('../', import.meta.url));
const lan = process.argv.includes('--lan');
const lanAddress = lan ? lanInterfaces()[0]?.address : null;
if (lan && !lanAddress) throw new Error('LAN browser check needs a connected IPv4 interface.');
await mkdir(join(workspace, '.verification'), { recursive: true });
const run = await mkdtemp(join(workspace, '.verification', 'backend-browser-'));
const probe = createServer(); probe.listen(0, '127.0.0.1'); await once(probe, 'listening');
const port = probe.address().port; await new Promise(r => probe.close(r));
const postgres = await socketDatabase();
const server = spawn(process.execPath, ['server.mjs', ...(lan ? ['--lan'] : [])], { cwd: workspace, windowsHide: true, stdio: 'ignore',
  env: { ...process.env, PORT: String(port), DATABASE_URL: postgres.url, HAEDAP_DB_POOL_SIZE: '1', OPENAI_API_KEY: '', OPENAI_MODEL: '' } });
let browser, socket;
const checks = [], exceptions = [];
const pause = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, message) { for (let i = 0; i < 100; i++) { try { if (await fn()) return; } catch {} await pause(100); } throw new Error(message); }
try {
  await until(async () => (await fetch(`http://127.0.0.1:${port}/api/health`)).ok, 'Server startup');
  browser = spawn(process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${join(run, 'chrome')}`, '--no-first-run', '--no-default-browser-check', '--disable-gpu', 'about:blank'],
    { windowsHide: true, stdio: 'ignore' });
  let debugPort;
  await until(async () => { debugPort = (await readFile(join(run, 'chrome', 'DevToolsActivePort'), 'utf8')).split('\n')[0]; return debugPort; }, 'Chrome startup');
  const pages = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json();
  socket = new WebSocket(pages.find(p => p.type === 'page').webSocketDebuggerUrl);
  await new Promise((r, reject) => { socket.onopen = r; socket.onerror = reject; });
  let sequence = 0; const pending = new Map();
  function command(method, params = {}) {
    const id = ++sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 15000);
      pending.set(id, { resolve, reject, timer }); socket.send(JSON.stringify({ id, method, params }));
    });
  }
  socket.onmessage = e => {
    const data = JSON.parse(e.data);
    if (data.method === 'Runtime.exceptionThrown') exceptions.push(data.params.exceptionDetails.text + ': ' + (data.params.exceptionDetails.exception?.description || ''));
    if (data.method === 'Page.javascriptDialogOpening') command('Page.handleJavaScriptDialog', { accept: true }).catch(() => {});
    const item = pending.get(data.id);
    if (item) { clearTimeout(item.timer); pending.delete(data.id); data.error ? item.reject(new Error(data.error.message)) : item.resolve(data.result); }
  };
  async function evaluate(expression) {
    const data = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (data.exceptionDetails) throw new Error(data.exceptionDetails.exception?.description || data.exceptionDetails.text);
    return data.result.value;
  }
  const waitJs = (expression, name) => until(() => evaluate(expression), name);
  await command('Runtime.enable'); await command('Page.enable');
  await command('Page.navigate', { url: `http://${lanAddress || '127.0.0.1'}:${port}/` });
  await waitJs('typeof backend!=="undefined" && backend.ready', 'Backend hydration'); checks.push('Backend connected');
  await evaluate(`navigate('regulation'); document.getElementById('query').value='배출규제해역 연료 황 함유량'; document.getElementById('search-form').requestSubmit()`);
  await waitJs('state.result==="backend" && !state.loading', 'Search');
  assert.ok(await evaluate('document.getElementById("search-response").textContent.includes("0.50%")')); checks.push('Actual document search and decimal values');
  await evaluate('document.querySelector(".citation").click()');
  assert.ok(await evaluate('document.getElementById("document-dialog").open')); checks.push('Evidence dialog');
  await evaluate(`document.getElementById('document-dialog').close(); document.querySelector('[data-action="add-backend-result"]').click(); document.getElementById('report-title').value='브라우저 검증 초안'; document.querySelector('[data-action="save-report"]').click()`);
  await waitJs('backend.version===1 && !backend.saving', 'Report DB save'); checks.push('Report DB save');
  await command('Page.reload'); await waitJs('typeof backend!=="undefined" && backend.ready', 'Reload');
  assert.ok(await evaluate('state.report.text.includes("0.50%") && state.report.sources.every(id=>DOCS[id])')); checks.push('Reload with stable citations');
  await evaluate(`document.querySelector('[data-action="load-db-report"]').click()`);
  await waitJs('backend.version===1', 'DB report reload'); checks.push('DB draft load');
  await evaluate(`navigate('carbon'); document.getElementById('fuel').value='100'; document.getElementById('factor').value='3'; document.getElementById('carbon-form').requestSubmit()`);
  await waitJs('state.calc?.version==="HAEDAP-EMISSIONS-1"', 'Server calculation');
  assert.equal(await evaluate('state.calc.emission'), 300); checks.push('Server calculation');
  await evaluate(`navigate('ask'); document.getElementById('query').value='초콜릿 케이크 레시피'; document.getElementById('search-form').requestSubmit()`);
  await waitJs('state.result==="backend" && !state.loading', 'Unknown question');
  assert.equal(await evaluate('backend.result.status'), 'insufficient_evidence'); checks.push('No-evidence response');
  // PGlite's test socket accepts one network client; inject through its in-process pool.
  const db = await openDatabase(postgres.url, { pool: postgres.directPool });
  try { await importDocuments(db, [{ id: 'new-manual', title: '<img src=x onerror="window.injected=true">', kind: 'onboard', reference: 'TEST-MANUAL', version: '1', reviewedAt: '2026-09-28',
    sections: [{ heading: '신규문서', text: '신규문서유입검증용 본문입니다. 브라우저 접속 후에 수집한 문서도 근거로 열 수 있어야 합니다.' }] }]); } finally { await db.close(); }
  await evaluate(`document.getElementById('query').value='신규문서유입검증용'; document.getElementById('search-form').requestSubmit()`);
  await waitJs('state.result==="backend" && !state.loading', 'New document search');
  await evaluate('document.querySelector(".citation").click()');
  assert.ok(await evaluate('document.getElementById("document-dialog").open'));
  assert.equal(await evaluate('window.injected===true'), false);
  await evaluate('document.getElementById("document-dialog").close()');
  checks.push('Newly ingested evidence hydrates and imported markup is escaped');
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await evaluate("navigate('report')");
  assert.ok(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1')); checks.push('Mobile report layout');
  const screenshot = await command('Page.captureScreenshot', { format: 'png' });
  await writeFile(join(run, 'report-mobile.png'), Buffer.from(screenshot.data, 'base64'));
  assert.deepEqual(exceptions, []); checks.push('No JavaScript exceptions');
  await writeFile(join(run, 'results.json'), JSON.stringify({ checkedAt: new Date().toISOString(), mode: lan ? 'lan' : 'local', address: lanAddress || '127.0.0.1', checks, exceptions }, null, 2));
  console.log(JSON.stringify({ mode: lan ? 'lan' : 'local', address: lanAddress || '127.0.0.1', checks, artifactDirectory: run }, null, 2));
} finally {
  socket?.close();
  for (const child of [browser, server].filter(Boolean)) {
    if (child.exitCode === null && child.signalCode === null) { const done = once(child, 'exit'); child.kill(); await done; }
  }
  await postgres.close();
}
