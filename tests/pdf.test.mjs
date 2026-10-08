import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, sep, basename } from 'node:path';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';
import { importDocuments, retrieve, listDocuments } from '../backend/db.mjs';
import { openDatabase as openLegacyDatabase, importDocuments as importLegacyDocuments,
  retrieve as retrieveLegacy, saveReport as saveLegacyReport, getReport as getLegacyReport } from './support/sqlite.mjs';
import { database } from './support/postgres.mjs';
import { prepareDocument } from '../backend/knowledge.mjs';
import { pdfDocument, extractPdfDocument } from '../backend/pdf.mjs';
import { answerQuestion } from '../backend/rag.mjs';

const seed = JSON.parse(readFileSync(new URL('../knowledge/seed.json', import.meta.url), 'utf8'));
const metadata = { id: 'pdf-test', title: 'Engine handbook.pdf', reference: 'data/pdfs/ABS/Engine handbook.pdf', version: 'test-1', reviewedAt: '2026-10-01' };
const pages = [{ page: 1, text: 'Ballast inspection\n' + 'Ballast inspection records must be retained. '.repeat(35) },
  { page: 2, text: ' ' }, { page: 3, text: 'Propulsion procedure\nPropulsion machinery inspection requirements.' }];

function temporary(t) {
  const dir = mkdtempSync(join(tmpdir(), 'haedap-pdf-'));
  t.after(() => {
    assert.ok(resolve(dir).startsWith(resolve(tmpdir()) + sep) && basename(dir).startsWith('haedap-pdf-'));
    rmSync(dir, { recursive: true, force: true });
  });
  return dir;
}

test('PDF page metadata survives chunking, PostgreSQL search, answers and document listing', async t => {
  const db = await database(t);
  const input = pdfDocument(pages, metadata);
  assert.deepEqual(input.summary.emptyPages, [2]);
  assert.equal(input.summary.pages, 3);
  const prepared = prepareDocument(input.document);
  assert.ok(prepared.chunks.length > 2);
  for (const chunk of prepared.chunks) {
    assert.equal(chunk.document_id, prepared.revisionId);
    assert.equal(chunk.title, metadata.title);
    assert.ok([1, 3].includes(chunk.page));
    assert.ok(chunk.text.length <= 900);
  }
  await importDocuments(db, [input.document]);
  const hits = await retrieve(db, 'Propulsion', { kind: 'manual' });
  assert.equal(hits.length, 1);
  for (const key of ['document_id', 'title', 'page', 'heading', 'text']) assert.ok(hits[0][key]);
  assert.equal(hits[0].page, 3);
  assert.equal(hits[0].title, metadata.title);
  assert.equal(typeof hits[0].rank, 'number');
  assert.deepEqual(await retrieve(db, 'Propulsion', { kind: 'imo' }), []);
  assert.equal((await answerQuestion(db, { question: 'Propulsion' })).evidence[0].page, 3);
  assert.ok((await listDocuments(db))[0].sections.every(c => c.page && c.title && c.document_id));
  assert.equal((await importDocuments(db, [input.document]))[0].status, 'unchanged');
  const updated = pdfDocument([{ page: 1, text: 'Replacement inspection.' }], { ...metadata, version: 'test-2' });
  await importDocuments(db, [updated.document]);
  assert.deepEqual(await retrieve(db, 'Propulsion'), []);
  assert.ok((await listDocuments(db)).find(d => !d.active).sections.some(c => c.page === 3));
});

test('PDF validation rejects invalid pages and textless files; JSON keeps its old hash and limits', () => {
  assert.throws(() => pdfDocument([{ page: 1, text: '' }], metadata), /OCR/);
  assert.throws(() => pdfDocument([{ page: 2, text: 'text' }], metadata), /페이지/);
  for (const page of [undefined, 0, -1, 1.5, '1', 5001]) {
    assert.throws(() => prepareDocument({ ...metadata, kind: 'pdf', sections: [{ heading: 'h', text: 'text', page }] }));
  }
  const legacyHash = createHash('sha256').update('haedap-chunk-v1\n').update(JSON.stringify(seed[0])).digest('hex');
  assert.equal(prepareDocument(seed[0]).hash, legacyHash);
  assert.ok(prepareDocument(seed[0]).chunks.every(c => c.page === null));
  assert.throws(() => prepareDocument({ ...seed[0], sections: Array(101).fill(seed[0].sections[0]) }));
  const large = pdfDocument(Array.from({ length: 101 }, (_, i) => ({ page: i + 1, text: 'Ballast inspection. '.repeat(80) })), metadata);
  assert.equal(prepareDocument(large.document).sections.length, 101);
});

test('legacy SQLite fixture preserves source data for one-time PostgreSQL migration', t => {
  const file = join(temporary(t), 'legacy.sqlite');
  let db = openLegacyDatabase(file);
  try {
    importLegacyDocuments(db, seed);
    const old = retrieveLegacy(db, '황 함유량')[0];
    saveLegacyReport(db, { title: '기존 보고서', type: '규정 검토', text: '유지할 내용', sources: [old.document_id], version: 0 });
    db.exec('ALTER TABLE chunks DROP COLUMN page; PRAGMA user_version=1;');
    db.close(); db = openLegacyDatabase(file);
    assert.equal(db.prepare('PRAGMA user_version').get().user_version, 2);
    assert.equal(retrieveLegacy(db, '황 함유량')[0].id, old.id);
    assert.equal(retrieveLegacy(db, '황 함유량')[0].page, null);
    assert.equal(getLegacyReport(db).sources[0], old.document_id);
    assert.ok(importLegacyDocuments(db, seed).every(r => r.status === 'unchanged'));
    importLegacyDocuments(db, [pdfDocument(pages, metadata).document]);
    db.close(); db = openLegacyDatabase(file);
    assert.equal(retrieveLegacy(db, 'Propulsion')[0].page, 3);
  } finally { db.close(); }
});

test('UI shows escaped document title and PDF page and carries both into a report', () => {
  let report;
  const context = vm.createContext({ document: { addEventListener() {} },
    esc: value => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
    ico: () => '', chip: () => '', btn: () => '', sourceCards: () => '', DOCS: { document: {} },
    addReport: (...args) => { report = args; } });
  vm.runInContext(readFileSync(new URL('../backend-ui.js', import.meta.url), 'utf8'), context);
  vm.runInContext(`backend.result = { question: 'inspection', status: 'evidence_found', generation: 'extractive',
    warnings: [], notice: '', toolRuns: [], statements: [{ text: 'inspection', quote: 'inspection', chunkId: 'chunk' }],
    evidence: [{ id: 'chunk', document_id: 'document', title: '<manual>.pdf', page: 7, heading: 'Inspection', version: '1', kind: 'pdf' }] };`, context);
  const html = vm.runInContext('backendResultView()', context);
  assert.match(html, /&lt;manual&gt;\.pdf · PDF p\.7/);
  vm.runInContext('addBackendResult()', context);
  assert.match(report[0], /<manual>\.pdf \/ PDF p\.7/);
});

// One tiny three-page PDF fixture (including a blank second page), assembled for extraction testing.
function fixturePdf() {
  const texts = ['Ballast inspection records.', '', 'Propulsion machinery requirements.'];
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R 5 0 R 7 0 R] /Count 3 >>'];
  for (const [i, text] of texts.entries()) {
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 9 0 R >> >> /Contents ${4 + i * 2} 0 R >>`);
    const content = text ? `BT /F1 12 Tf 72 720 Td (${text}) Tj ET` : '';
    objects.push(`<< /Length ${content.length} >>\nstream\n${content}\nendstream`);
  }
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');
  let data = '%PDF-1.4\n'; const offsets = [0];
  for (const [i, object] of objects.entries()) { offsets.push(data.length); data += `${i + 1} 0 obj\n${object}\nendobj\n`; }
  const xref = data.length;
  data += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets.slice(1)) data += `${String(offset).padStart(10, '0')} 00000 n \n`;
  return data + `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
}

const python = process.env.HAEDAP_PYTHON || 'python';
const available = spawnSync(python, ['-c', 'import pypdf'], { windowsHide: true, timeout: 10000 }).status === 0;
test('real PDF parser preserves blank page offsets and rejects paths outside PDF root', { skip: !available && 'Install requirements-pdf.txt / set HAEDAP_PYTHON' }, async t => {
  const dir = temporary(t), file = join(dir, 'page test.pdf');
  writeFileSync(file, fixturePdf(), 'ascii');
  const result = await extractPdfDocument(file, { python, root: dir });
  assert.deepEqual(result.summary.emptyPages, [2]);
  assert.equal(result.document.title, 'page test.pdf');
  assert.match(result.document.sections.find(s => s.page === 3).text, /Propulsion/);
  const otherRoot = join(dir, 'unrelated'); mkdirSync(otherRoot);
  await assert.rejects(extractPdfDocument(file, { python, root: otherRoot }), /data\/pdfs/);
  const db = await database(t);
  await importDocuments(db, [result.document]);
  assert.equal((await retrieve(db, 'Propulsion'))[0].page, 3);
});

test('one explicitly selected local PDF: complete extraction, JSON coexistence, reimport and page search', {
  skip: !process.env.HAEDAP_TEST_PDF && 'Set HAEDAP_TEST_PDF to one PDF under data/pdfs', timeout: 240000,
}, async t => {
  assert.ok(available, 'Python/pypdf is required for the selected PDF');
  const result = await extractPdfDocument(process.env.HAEDAP_TEST_PDF, { python });
  const db = await database(t, seed);
  {
    assert.equal((await importDocuments(db, [result.document]))[0].status, 'created');
    assert.equal((await importDocuments(db, [result.document]))[0].status, 'unchanged');
    const hits = await retrieve(db, 'offshore support vessels');
    assert.ok(hits.some(h => h.title === result.document.title && h.page > 0));
    assert.ok(hits.every(h => h.document_id && h.heading && h.text));
    const stored = (await listDocuments(db)).find(d => d.logical_id === result.document.id);
    assert.deepEqual([...new Set(stored.sections.map(c => c.page))], result.document.sections.map(s => s.page).filter((p, i, a) => a.indexOf(p) === i));
    t.diagnostic(JSON.stringify({ title: result.document.title, ...result.summary, chunks: stored.sections.length,
      search: hits.slice(0, 3).map(h => ({ title: h.title, page: h.page })) }));
  }
});
