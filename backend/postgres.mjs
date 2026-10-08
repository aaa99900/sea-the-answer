import pg from 'pg';
import { randomUUID } from 'node:crypto';
import { prepareDocument, tokens } from './knowledge.mjs';
import { object, string, requireValue } from './validation.mjs';

const { Pool } = pg;

const schema = [
  `CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, logical_id TEXT NOT NULL, hash TEXT NOT NULL, title TEXT NOT NULL,
    kind TEXT NOT NULL, url TEXT, reference TEXT NOT NULL, version TEXT NOT NULL,
    reviewed_at TEXT NOT NULL, language TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE, imported_at TEXT NOT NULL
  )`,
  'CREATE UNIQUE INDEX IF NOT EXISTS one_active_revision ON documents(logical_id) WHERE active',
  `CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id), position INTEGER NOT NULL,
    heading TEXT NOT NULL, text TEXT NOT NULL, page INTEGER CHECK(page IS NULL OR page BETWEEN 1 AND 5000),
    terms TEXT NOT NULL, search_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', terms)) STORED
  )`,
  'CREATE INDEX IF NOT EXISTS chunks_search_vector_idx ON chunks USING GIN(search_vector)',
  'CREATE INDEX IF NOT EXISTS chunks_document_id_idx ON chunks(document_id)',
  `CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT NOT NULL, text TEXT NOT NULL,
    sources TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS tool_runs (
    id TEXT PRIMARY KEY, tool TEXT NOT NULL, version TEXT NOT NULL, input TEXT NOT NULL,
    output TEXT NOT NULL, created_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS queries (
    id TEXT PRIMARY KEY, question TEXT NOT NULL, response TEXT NOT NULL, created_at TEXT NOT NULL
  )`,
];

export async function openDatabase(connectionString, { pool: suppliedPool } = {}) {
  const pool = suppliedPool || new Pool({ connectionString, max: 5, connectionTimeoutMillis: 5000 });
  try {
    for (const statement of schema) await pool.query(statement);
    return { kind: 'postgres', pool, close: () => pool.end() };
  } catch (error) {
    if (!suppliedPool) await pool.end();
    throw error;
  }
}

async function transaction(db, fn) {
  const client = await db.pool.connect();
  try {
    await client.query('BEGIN');
    const result = await fn(client);
    await client.query('COMMIT');
    return result;
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally { client.release(); }
}

export async function importDocuments(db, input) {
  requireValue(Array.isArray(input) && input.length > 0 && input.length <= 100, '1~100개 문서의 JSON 배열이 필요합니다.');
  const docs = input.map(prepareDocument);
  requireValue(new Set(docs.map(d => d.id)).size === docs.length, '한 번에 같은 문서 ID를 중복 등록할 수 없습니다.');
  return transaction(db, async client => {
    const result = [];
    for (const d of docs) {
      // Serialize imports of the same logical document across server processes.
      await client.query('SELECT pg_advisory_xact_lock(hashtext($1))', [d.id]);
      const old = (await client.query('SELECT id, hash FROM documents WHERE logical_id=$1 AND active=TRUE', [d.id])).rows[0];
      if (old?.hash === d.hash) { result.push({ id: old.id, status: 'unchanged' }); continue; }
      await client.query('UPDATE documents SET active=FALSE WHERE logical_id=$1', [d.id]);
      const existing = (await client.query('SELECT id FROM documents WHERE id=$1', [d.revisionId])).rows[0];
      if (existing) await client.query('UPDATE documents SET active=TRUE WHERE id=$1', [d.revisionId]);
      else {
        await client.query(`INSERT INTO documents(id,logical_id,hash,title,kind,url,reference,version,reviewed_at,language,active,imported_at)
          VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,TRUE,$11)`,
          [d.revisionId, d.id, d.hash, d.title, d.kind, d.url, d.reference, d.version, d.reviewedAt, d.language, new Date().toISOString()]);
        for (const c of d.chunks) await client.query(
          'INSERT INTO chunks(id,document_id,position,heading,text,page,terms) VALUES($1,$2,$3,$4,$5,$6,$7)',
          [c.id, d.revisionId, c.position, c.heading, c.text, c.page, c.terms]);
      }
      result.push({ id: d.revisionId, status: old ? 'updated' : 'created', chunks: d.chunks.length });
    }
    return result;
  });
}

export async function listDocuments(db) {
  const documents = (await db.pool.query('SELECT * FROM documents ORDER BY active DESC, title, imported_at DESC')).rows;
  if (!documents.length) return [];
  const chunks = (await db.pool.query('SELECT id,document_id,page,heading,text,position FROM chunks WHERE document_id = ANY($1::text[]) ORDER BY document_id,position', [documents.map(d => d.id)])).rows;
  const byDocument = new Map();
  for (const c of chunks) {
    if (!byDocument.has(c.document_id)) byDocument.set(c.document_id, []);
    byDocument.get(c.document_id).push(c);
  }
  return documents.map(d => ({ ...d, active: Number(d.active), sections: (byDocument.get(d.id) || []).map(c => ({ ...c, title: d.title })) }));
}

export async function retrieve(db, question, { kind = 'all', limit = 5 } = {}) {
  string(question, '질문', 2000);
  requireValue(['all', 'imo', 'manual'].includes(kind), '문서 필터가 올바르지 않습니다.');
  const terms = tokens(question).slice(0, 80);
  if (!terms.length) return [];
  // tokens() emits only alphanumeric/Hangul terms; the tsquery remains parameterized.
  const query = terms.join(' | ');
  const rows = (await db.pool.query(`SELECT c.id,c.document_id,c.position,c.heading,c.text,c.page,
      d.title,d.kind,d.url,d.reference,d.version,d.reviewed_at,d.hash,
      ts_rank_cd(c.search_vector, to_tsquery('simple', $1)) AS rank
      FROM chunks c JOIN documents d ON d.id=c.document_id
      WHERE c.search_vector @@ to_tsquery('simple', $1) AND d.active=TRUE
        AND ($2='all' OR ($2='imo' AND d.kind='official-summary') OR ($2='manual' AND d.kind!='official-summary'))
      ORDER BY rank DESC, c.id LIMIT 30`, [query, kind])).rows;
  return rows.map(r => {
    const bodyTerms = new Set(tokens(`${r.heading} ${r.text}`));
    const matched = terms.filter(t => bodyTerms.has(t));
    const concept = matched.some(t => t.startsWith('concept'));
    const substantial = matched.filter(t => !t.startsWith('concept') && t.length >= 3);
    return { ...r, matched, supported: concept || substantial.length >= 1 || matched.length >= 2 };
  }).filter(r => r.supported).slice(0, limit).map(({ supported, ...r }) => r);
}

export async function saveReport(db, input) {
  object(input);
  const id = string(input.id || 'current', '보고서 ID', 80);
  requireValue(/^[a-zA-Z0-9-]+$/.test(id), '보고서 ID가 올바르지 않습니다.');
  const title = string(input.title, '제목', 120), text = string(input.text, '내용', 200000);
  requireValue(['규정 검토', '일일 운항', '배출량 검토', '종합 검토'].includes(input.type), '보고서 유형이 올바르지 않습니다.');
  requireValue(Array.isArray(input.sources) && input.sources.length <= 100 && input.sources.every(s => typeof s === 'string'), '근거 ID 배열이 필요합니다.');
  requireValue(Number.isInteger(input.version) && input.version >= 0, '보고서 버전이 필요합니다.');
  const sources = [...new Set(input.sources)];
  return transaction(db, async client => {
    await client.query('SELECT pg_advisory_xact_lock(hashtext($1))', [`report:${id}`]);
    for (const s of sources) if (!['sulfur','cii','checklist','noon','carbon'].includes(s)) {
      requireValue(!!(await client.query('SELECT id FROM documents WHERE id=$1', [s])).rows[0], '존재하지 않는 근거입니다.');
    }
    const old = (await client.query('SELECT version FROM reports WHERE id=$1', [id])).rows[0];
    requireValue((old?.version || 0) === input.version, '다른 창에서 초안이 변경되었습니다. DB 초안을 다시 불러온 뒤 저장하세요.', 'VERSION_CONFLICT', 409);
    const version = input.version + 1, updatedAt = new Date().toISOString();
    await client.query(`INSERT INTO reports(id,title,type,text,sources,version,updated_at) VALUES($1,$2,$3,$4,$5,$6,$7)
      ON CONFLICT(id) DO UPDATE SET title=EXCLUDED.title,type=EXCLUDED.type,text=EXCLUDED.text,
      sources=EXCLUDED.sources,version=EXCLUDED.version,updated_at=EXCLUDED.updated_at`,
      [id, title, input.type, text, JSON.stringify(sources), version, updatedAt]);
    return { id, title, type: input.type, text, sources, version, updatedAt };
  });
}

export async function getReport(db, id = 'current') {
  const row = (await db.pool.query('SELECT * FROM reports WHERE id=$1', [id])).rows[0];
  return row ? { ...row, sources: JSON.parse(row.sources), updatedAt: row.updated_at } : null;
}
export async function logTool(db, name, input, output) {
  const id = randomUUID();
  await db.pool.query('INSERT INTO tool_runs(id,tool,version,input,output,created_at) VALUES($1,$2,$3,$4,$5,$6)',
    [id, name, output.version, JSON.stringify(input), JSON.stringify(output), new Date().toISOString()]);
  return { id, name, ...output };
}
export async function logQuery(db, question, response) {
  const id = randomUUID();
  await db.pool.query('INSERT INTO queries(id,question,response,created_at) VALUES($1,$2,$3,$4)',
    [id, question, JSON.stringify(response), new Date().toISOString()]);
  return { id, ...response };
}
export async function countDocuments(db) {
  return Number((await db.pool.query('SELECT count(*) AS count FROM documents WHERE active=TRUE')).rows[0].count);
}
