import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDatabase, importDocuments } from '../backend/db.mjs';
import { extractPdfDocument } from '../backend/pdf.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
try {
  try { process.loadEnvFile(resolve(root, '.env')); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  const files = process.argv.slice(2);
  if (files.length < 1 || files.length > 3 || files.some(file => file.startsWith('--'))) {
    throw new Error('Usage: node scripts/ingest-pdf.mjs "data/pdfs/ABS/file.pdf" [file2.pdf] [file3.pdf] (1~3 files)');
  }
  const inputs = [];
  for (const file of files) {
    console.error(`Extracting: ${file}`);
    inputs.push(await extractPdfDocument(file));
  }
  // Extract every input before opening the DB; importDocuments commits the batch atomically.
  const target = process.env.HAEDAP_DB_BACKEND === 'sqlite'
    ? resolve(root, process.env.HAEDAP_DB_PATH || 'data/haedap.sqlite') : process.env.DATABASE_URL;
  const db = await openDatabase(target);
  try {
    const imported = await importDocuments(db, inputs.map(input => input.document));
    console.log(JSON.stringify(imported.map((result, index) => ({ ...result, title: inputs[index].document.title,
      ...inputs[index].summary, warning: inputs[index].summary.emptyPages.length ? '빈/이미지 페이지는 제외했습니다. OCR은 수행하지 않습니다.' : null })), null, 2));
  } finally { await db.close(); }
} catch (error) { console.error(error.message); process.exitCode = 1; }
