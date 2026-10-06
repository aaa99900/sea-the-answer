import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
import { readFile, realpath, stat } from 'node:fs/promises';
import { basename, extname, isAbsolute, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { requireValue } from './validation.mjs';

const execFileAsync = promisify(execFile);
export const pdfRoot = fileURLToPath(new URL('../data/pdfs/', import.meta.url));
const extractor = fileURLToPath(new URL('../scripts/extract-pdf.py', import.meta.url));

export function pdfDocument(pages, { id, title, reference, version, reviewedAt }) {
  requireValue(Array.isArray(pages) && pages.length > 0 && pages.length <= 5000, 'PDF에는 1~5000개 페이지가 필요합니다.');
  const sections = [], emptyPages = [];
  let characters = 0;
  for (const [index, entry] of pages.entries()) {
    requireValue(entry?.page === index + 1 && typeof entry.text === 'string', 'PDF 페이지 번호가 연속적이지 않거나 텍스트가 잘못되었습니다.');
    const text = entry.text.replace(/\r\n?/g, '\n').replace(/\u0000/g, '').trim();
    characters += text.length;
    requireValue(characters <= 20000000, 'PDF 추출 본문은 20,000,000자 이하여야 합니다.');
    if (!text) { emptyPages.push(entry.page); continue; }
    // A simple page heading, not an inferred regulation/chapter hierarchy.
    const heading = text.split('\n').find(line => line.trim())?.trim().slice(0, 180) || `PDF page ${entry.page}`;
    for (let start = 0; start < text.length; start += 20000) {
      const part = text.slice(start, start + 20000).trim();
      if (part) sections.push({ page: entry.page, heading, text: part });
    }
  }
  requireValue(sections.length > 0, '추출 가능한 PDF 텍스트가 없습니다. 이미지/스캔 문서는 OCR이 필요합니다.');
  return {
    document: { id, title, kind: 'pdf', reference, version, reviewedAt, language: /[가-힣]/.test(sections[0].text) ? 'ko' : 'en', sections },
    summary: { pages: pages.length, textPages: pages.length - emptyPages.length, emptyPages, characters },
  };
}

export async function extractPdfDocument(input, { python = process.env.HAEDAP_PYTHON || 'python', root = pdfRoot } = {}) {
  const [base, source] = await Promise.all([realpath(root), realpath(resolve(input))]);
  const local = relative(base, source);
  requireValue(local && local !== '..' && !local.startsWith(`..${sep}`) && !isAbsolute(local), 'PDF는 data/pdfs 아래에 있어야 합니다.');
  requireValue(extname(source).toLowerCase() === '.pdf', 'PDF 파일을 지정하세요.');
  const info = await stat(source);
  requireValue(info.isFile() && info.size <= 128 * 1024 * 1024, 'PDF 파일은 128 MiB 이하여야 합니다.');
  let stdout;
  try {
    ({ stdout } = await execFileAsync(python, [extractor, source], { encoding: 'utf8', windowsHide: true,
      timeout: 180000, maxBuffer: 128 * 1024 * 1024 }));
  } catch (error) {
    if (error.code === 'ENOENT') throw new Error('Python을 찾지 못했습니다. Python 3.9+를 설치하거나 HAEDAP_PYTHON에 python 실행 파일 경로를 지정하세요.');
    throw new Error(`PDF 텍스트 추출 실패: ${error.stderr?.trim() || error.message}`);
  }
  const reference = `data/pdfs/${local.split(sep).join('/')}`;
  const identity = process.platform === 'win32' ? reference.toLowerCase() : reference;
  const id = `pdf-${createHash('sha256').update(identity).digest('hex').slice(0, 24)}`;
  const version = `sha256-${createHash('sha256').update(await readFile(source)).digest('hex')}`;
  // For PDF input this legacy field is the source modification date, NOT a review certification.
  return pdfDocument(JSON.parse(stdout).pages, { id, title: basename(source), reference, version,
    reviewedAt: info.mtime.toISOString().slice(0, 10) });
}
