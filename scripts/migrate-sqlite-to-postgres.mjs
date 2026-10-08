import { stat } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';
import { openDatabase } from '../backend/db.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
try { process.loadEnvFile(resolve(root, '.env')); } catch (error) { if (error.code !== 'ENOENT') throw error; }

let source, target, client;
try {
  if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL을 .env에 설정하세요.');
  const path = resolve(root, process.argv[2] || 'data/haedap.sqlite');
  if (!(await stat(path)).isFile()) throw new Error(`SQLite 파일이 아닙니다: ${path}`);
  // Read-only open leaves the original database and WAL files unchanged.
  source = new DatabaseSync(path, { readOnly: true });
  target = await openDatabase(process.env.DATABASE_URL);
  client = await target.pool.connect();
  await client.query('BEGIN');
  const tables = ['documents', 'chunks', 'reports', 'tool_runs', 'queries'];
  for (const table of tables) {
    if ((await client.query(`SELECT 1 FROM ${table} LIMIT 1`)).rows.length) {
      throw new Error('대상 PostgreSQL DB가 비어 있지 않습니다. 새 빈 DB를 준비하세요. 기존 데이터는 변경하지 않았습니다.');
    }
  }
  const counts = {};
  const documents = source.prepare('SELECT * FROM documents ORDER BY imported_at, id').all();
  for (const d of documents) await client.query(`INSERT INTO documents
    (id,logical_id,hash,title,kind,url,reference,version,reviewed_at,language,active,imported_at)
    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)`,
    [d.id, d.logical_id, d.hash, d.title, d.kind, d.url, d.reference, d.version, d.reviewed_at, d.language, !!d.active, d.imported_at]);
  counts.documents = documents.length;
  const hasPage = source.prepare('PRAGMA table_info(chunks)').all().some(column => column.name === 'page');
  const chunks = source.prepare(`SELECT c.id,c.document_id,c.position,c.heading,c.text,${hasPage ? 'c.page' : 'NULL AS page'},f.terms
    FROM chunks c JOIN chunks_fts f ON f.chunk_id=c.id ORDER BY c.document_id,c.position`).all();
  for (const c of chunks) await client.query('INSERT INTO chunks(id,document_id,position,heading,text,page,terms) VALUES($1,$2,$3,$4,$5,$6,$7)',
    [c.id, c.document_id, c.position, c.heading, c.text, c.page, c.terms]);
  counts.chunks = chunks.length;
  for (const [table, columns] of [
    ['reports', 'id,title,type,text,sources,version,updated_at'],
    ['tool_runs', 'id,tool,version,input,output,created_at'],
    ['queries', 'id,question,response,created_at'],
  ]) {
    const rows = source.prepare(`SELECT ${columns} FROM ${table}`).all();
    const placeholders = columns.split(',').map((_, index) => `$${index + 1}`).join(',');
    for (const row of rows) await client.query(`INSERT INTO ${table}(${columns}) VALUES(${placeholders})`, columns.split(',').map(column => row[column]));
    counts[table] = rows.length;
  }
  await client.query('COMMIT');
  console.log(JSON.stringify({ source: path, destination: 'PostgreSQL', copied: counts }, null, 2));
} catch (error) {
  if (client) await client.query('ROLLBACK');
  console.error(`Migration failed: ${error.message}`);
  process.exitCode = 1;
} finally {
  client?.release();
  if (source) source.close();
  if (target) await target.close();
}
