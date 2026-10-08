import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { PGlite } from '@electric-sql/pglite';
import { PGLiteSocketServer } from '@electric-sql/pglite-socket';
import { createServer } from 'node:net';
import { once } from 'node:events';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, sep, basename } from 'node:path';
import { openDatabase, importDocuments, listDocuments, retrieve, saveReport, getReport, countDocuments } from '../backend/db.mjs';
import { answerQuestion } from '../backend/rag.mjs';
import { runTool } from '../backend/tools.mjs';

const seed = JSON.parse(readFileSync(new URL('../knowledge/seed.json', import.meta.url), 'utf8'));
const execFileAsync = promisify(execFile);

async function fixture(t) {
  // In-process PostgreSQL engine; production uses the pg network driver.
  const engine = await PGlite.create();
  const pool = {
    query: (...args) => engine.query(...args),
    connect: async () => ({ query: (...args) => engine.query(...args), release() {} }),
    end: () => engine.close(),
  };
  const db = await openDatabase('postgresql://test/test', { pool });
  t.after(async () => db.close());
  return db;
}

test('PostgreSQL initializes and searches JSON and paged PDF chunks', async t => {
  const db = await fixture(t);
  assert.equal(db.kind, 'postgres');
  assert.equal((await db.pool.query("SELECT indexname FROM pg_indexes WHERE indexname='chunks_search_vector_idx'")).rows.length, 1);
  assert.equal((await importDocuments(db, seed)).length, 4);
  assert.equal(await countDocuments(db), 4);
  assert.ok((await importDocuments(db, seed)).every(item => item.status === 'unchanged'));
  for (const query of ['황 함유량 기준', 'fuel sulphur ECA limit', 'CII corrective action']) {
    const hits = await retrieve(db, query);
    assert.ok(hits.length, query);
    assert.ok(hits.every(hit => hit.document_id && hit.title && hit.heading && hit.text && typeof hit.rank === 'number'));
  }
  assert.deepEqual(await retrieve(db, '초콜릿 케이크 레시피'), []);
  assert.deepEqual(await retrieve(db, '" OR * - ()'), []);
  assert.ok((await retrieve(db, '황 함유량', { kind: 'imo' })).every(hit => hit.kind === 'official-summary'));
  const pdf = { id: 'pdf-test', title: 'Engine Manual.pdf', kind: 'pdf', reference: 'data/pdfs/ABS/Engine Manual.pdf',
    version: '1', reviewedAt: '2026-10-08', language: 'en', sections: [
      { page: 1, heading: 'Ballast inspection', text: 'Ballast inspection records are required.' },
      { page: 3, heading: 'Propulsion procedure', text: 'Propulsion machinery inspection requirements.' },
    ] };
  await importDocuments(db, [pdf]);
  const hits = await retrieve(db, 'Propulsion', { kind: 'manual' });
  assert.equal(hits[0].title, pdf.title);
  assert.equal(hits[0].page, 3);
  assert.ok((await listDocuments(db)).find(doc => doc.logical_id === pdf.id).sections.some(section => section.page === 3));
  const revision = { ...pdf, version: '2', sections: [{ page: 1, heading: 'Changed', text: 'Revised machinery guidance.' }] };
  await importDocuments(db, [revision]);
  assert.deepEqual(await retrieve(db, 'Propulsion'), []);
  assert.equal((await listDocuments(db)).filter(doc => doc.logical_id === pdf.id).length, 2);
});

test('PostgreSQL preserves report versions, tool and question records', async t => {
  const db = await fixture(t);
  await importDocuments(db, seed);
  const source = (await retrieve(db, '황 함유량'))[0];
  const draft = { title: '검토 초안', type: '규정 검토', text: '담당자 검토 필요', sources: [source.document_id], version: 0 };
  const saved = await saveReport(db, draft);
  assert.equal(saved.version, 1);
  assert.deepEqual((await getReport(db)).sources, draft.sources);
  await assert.rejects(saveReport(db, draft), error => error.status === 409);
  await assert.rejects(saveReport(db, { ...draft, sources: ['missing'], version: 1 }));
  const tool = await runTool(db, 'calculate_emissions', { fuel: 10, factor: 3, dwt: 100, distance: 10 });
  assert.equal(tool.emission, 30);
  const answer = await answerQuestion(db, { question: '황 함유량 기준' });
  assert.equal(answer.evidence[0].document_id, source.document_id);
  assert.equal(Number((await db.pool.query('SELECT count(*) AS n FROM tool_runs')).rows[0].n), 1);
  assert.equal(Number((await db.pool.query('SELECT count(*) AS n FROM queries')).rows[0].n), 1);
});

test('pg network driver connects to a PostgreSQL wire-protocol test server', { timeout: 30000 }, async t => {
  const probe = createServer(); probe.listen(0, '127.0.0.1'); await once(probe, 'listening');
  const port = probe.address().port; await new Promise(resolve => probe.close(resolve));
  const engine = await PGlite.create();
  const socket = new PGLiteSocketServer({ db: engine, port, host: '127.0.0.1' });
  await socket.start();
  t.after(async () => { await socket.stop(); await engine.close(); });
  const db = await openDatabase(`postgresql://postgres@127.0.0.1:${port}/postgres`);
  try {
    assert.equal(db.kind, 'postgres');
    await importDocuments(db, seed);
    assert.equal(await countDocuments(db), 4);
    assert.ok((await retrieve(db, 'fuel sulphur ECA limit')).length > 0);
  } finally { await db.close(); }
});

test('HTTP server uses PostgreSQL for search, reports and tools', { timeout: 30000 }, async t => {
  const probe = createServer(); probe.listen(0, '127.0.0.1'); await once(probe, 'listening');
  const pgPort = probe.address().port; await new Promise(resolve => probe.close(resolve));
  const engine = await PGlite.create();
  const socket = new PGLiteSocketServer({ db: engine, port: pgPort, host: '127.0.0.1' });
  await socket.start();
  t.after(async () => { await socket.stop(); await engine.close(); });
  const httpProbe = createServer(); httpProbe.listen(0, '127.0.0.1'); await once(httpProbe, 'listening');
  const port = httpProbe.address().port; await new Promise(resolve => httpProbe.close(resolve));
  const root = new URL('../', import.meta.url);
  const child = spawn(process.execPath, ['server.mjs'], { cwd: root, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, DATABASE_URL: `postgresql://postgres@127.0.0.1:${pgPort}/postgres`, HAEDAP_DB_BACKEND: '', PORT: String(port), OPENAI_API_KEY: '', OPENAI_MODEL: '' } });
  let logs = ''; child.stdout.on('data', data => { logs += data; }); child.stderr.on('data', data => { logs += data; });
  try {
    const base = `http://127.0.0.1:${port}`;
    let health;
    for (let i = 0; i < 150; i++) {
      try { health = await (await fetch(base + '/api/health')).json(); break; } catch { await new Promise(resolve => setTimeout(resolve, 50)); }
    }
    assert.equal(health?.storage, 'postgresql', logs);
    assert.equal(health.documents, 4);
    const post = (path, body) => fetch(base + path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Haedap-Token': health.csrfToken }, body: JSON.stringify(body) });
    const answer = await (await post('/api/ask', { question: '황 함유량 기준' })).json();
    assert.ok(answer.evidence[0].text.includes('0.50%'));
    const report = { title: 'PG 검토', type: '규정 검토', text: '저장됨', sources: [answer.evidence[0].document_id], version: 0 };
    assert.equal((await post('/api/reports/current', report)).status, 200);
    assert.equal((await post('/api/reports/current', report)).status, 409);
    assert.equal((await (await fetch(base + '/api/reports/current')).json()).report.title, report.title);
    const calc = await (await post('/api/tools/calculate_emissions', { fuel: 10, factor: 3, dwt: 100, distance: 10 })).json();
    assert.equal(calc.result.emission, 30);
    assert.equal((await fetch(base + '/data/haedap.sqlite')).status, 404);
  } finally {
    if (child.exitCode === null && child.signalCode === null) {
      const done = once(child, 'exit'); child.kill(); await done;
    }
  }
});

test('SQLite migration copies documents, citations and logs without changing the source', { timeout: 30000 }, async t => {
  const dir = mkdtempSync(join(tmpdir(), 'haedap-pg-migrate-'));
  t.after(() => {
    assert.ok(resolve(dir).startsWith(resolve(tmpdir()) + sep) && basename(dir).startsWith('haedap-pg-migrate-'));
    rmSync(dir, { recursive: true, force: true });
  });
  const path = join(dir, 'original.sqlite');
  const source = openDatabase(path);
  importDocuments(source, seed);
  const citation = retrieve(source, '황 함유량')[0].document_id;
  saveReport(source, { title: '기존', type: '규정 검토', text: '보존할 초안', sources: [citation], version: 0 });
  await runTool(source, 'calculate_emissions', { fuel: 10, factor: 3, dwt: 100, distance: 10 });
  await answerQuestion(source, { question: '황 함유량 기준' });
  source.close();
  const probe = createServer(); probe.listen(0, '127.0.0.1'); await once(probe, 'listening');
  const port = probe.address().port; await new Promise(resolve => probe.close(resolve));
  const engine = await PGlite.create();
  const socket = new PGLiteSocketServer({ db: engine, port, host: '127.0.0.1' });
  await socket.start();
  t.after(async () => { await socket.stop(); await engine.close(); });
  const url = `postgresql://postgres@127.0.0.1:${port}/postgres`;
  const { stdout } = await execFileAsync(process.execPath, ['scripts/migrate-sqlite-to-postgres.mjs', path], {
    cwd: new URL('../', import.meta.url), env: { ...process.env, DATABASE_URL: url }, windowsHide: true, timeout: 20000,
  });
  const summary = JSON.parse(stdout);
  assert.equal(summary.copied.documents, 4);
  assert.equal(summary.copied.reports, 1);
  const pgdb = await openDatabase(url);
  try {
    assert.equal((await retrieve(pgdb, '황 함유량'))[0].document_id, citation);
    assert.deepEqual((await getReport(pgdb)).sources, [citation]);
    assert.equal(Number((await pgdb.pool.query('SELECT count(*) AS n FROM tool_runs')).rows[0].n), 1);
    assert.equal(Number((await pgdb.pool.query('SELECT count(*) AS n FROM queries')).rows[0].n), 1);
    await assert.rejects(execFileAsync(process.execPath, ['scripts/migrate-sqlite-to-postgres.mjs', path], {
      cwd: new URL('../', import.meta.url), env: { ...process.env, DATABASE_URL: url }, windowsHide: true, timeout: 20000,
    }));
  } finally { await pgdb.close(); }
  const again = openDatabase(path);
  assert.equal(getReport(again).text, '보존할 초안');
  again.close();
});
