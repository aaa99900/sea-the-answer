import { readFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDatabase, importDocuments } from '../backend/db.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
try { process.loadEnvFile(resolve(root, '.env')); } catch (e) { if (e.code !== 'ENOENT') throw e; }
const path = process.argv[2];
if (!path) { console.error('Usage: node scripts/ingest.mjs knowledge/seed.json'); process.exitCode = 1; }
else {
  const raw = await readFile(resolve(path), 'utf8');
  const target = process.env.HAEDAP_DB_BACKEND === 'sqlite'
    ? resolve(root, process.env.HAEDAP_DB_PATH || 'data/haedap.sqlite') : process.env.DATABASE_URL;
  const db = await openDatabase(target);
  try { console.log(JSON.stringify(await importDocuments(db, JSON.parse(raw.replace(/^\uFEFF/, ''))), null, 2)); }
  finally { await db.close(); }
}
