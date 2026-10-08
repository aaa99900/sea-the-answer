import { randomBytes } from 'node:crypto';
import { AppError, requireValue } from './validation.mjs';
import { countDocuments, listDocuments, getReport, saveReport, retrieve } from './db.mjs';
import { answerQuestion, modelConfigured } from './rag.mjs';
import { runTool, toolDefinitions } from './tools.mjs';

function json(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
  res.end(JSON.stringify(body));
}
function readJson(req) {
  requireValue(req.headers['content-type']?.split(';')[0].trim() === 'application/json', 'application/json 요청이 필요합니다.', 'CONTENT_TYPE', 415);
  return new Promise((resolve, reject) => {
    let size = 0, chunks = [], tooLarge = false;
    req.on('data', data => { size += data.length; if (size > 1048576) { tooLarge = true; chunks = []; } else if (!tooLarge) chunks.push(data); });
    req.on('error', reject);
    req.on('end', () => {
      if (tooLarge) return reject(new AppError(413, 'BODY_TOO_LARGE', '요청은 1MB 이하여야 합니다.'));
      try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
      catch { reject(new AppError(400, 'INVALID_JSON', '올바른 JSON이 필요합니다.')); }
    });
  });
}
export function createApi(db, options = {}) {
  const token = randomBytes(32).toString('hex');
  let active = 0;
  return async (req, res, pathname) => {
    try {
      const host = req.headers.host;
      const allowed = options.allowRequest ? options.allowRequest(req) : /^(127\.0\.0\.1|localhost)(:\d+)?$/.test(host || '');
      requireValue(allowed, '실행 창에 표시된 서버 주소로 접속해 주세요.', 'HOST_DENIED', 403);
      requireValue(!req.headers.origin || req.headers.origin === `http://${host}`, '동일 출처 요청만 허용합니다.', 'ORIGIN_DENIED', 403);
      requireValue(!['cross-site', 'same-site'].includes(req.headers['sec-fetch-site']), '동일 출처 요청만 허용합니다.', 'ORIGIN_DENIED', 403);
      const method = req.method;
      if (method === 'GET' && pathname === '/api/health') return json(res, 200, { ok: true, storage: 'postgresql',
        retrieval: 'postgres-tsrank-ko-bigram',
        llmConfigured: modelConfigured(options.env), csrfToken: token,
        documents: await countDocuments(db) });
      if (method === 'GET' && pathname === '/api/documents') return json(res, 200, { documents: await listDocuments(db) });
      if (method === 'GET' && pathname === '/api/reports/current') return json(res, 200, { report: await getReport(db) });
      if (method === 'GET' && pathname === '/api/tools') return json(res, 200, { tools: toolDefinitions });
      if (method !== 'POST') throw new AppError(404, 'NOT_FOUND', 'API 경로를 찾을 수 없습니다.');
      requireValue(req.headers['x-haedap-token'] === token, '서버 연결을 새로고침한 뒤 다시 시도하세요.', 'SESSION_EXPIRED', 403);
      requireValue(active < 4, '처리 중인 요청이 많습니다. 잠시 후 다시 시도하세요.', 'BUSY', 429);
      active++;
      try {
        const body = await readJson(req);
        if (pathname === '/api/ask') return json(res, 200, await answerQuestion(db, body, options));
        if (pathname === '/api/search') return json(res, 200, { evidence: await retrieve(db, body?.question, { kind: body?.filter || 'all' }) });
        if (pathname === '/api/reports/current') {
          requireValue(body && !Array.isArray(body) && (body.id === undefined || body.id === 'current'), '현재 초안만 저장할 수 있습니다.');
          return json(res, 200, { report: await saveReport(db, { ...body, id: 'current' }) });
        }
        if (pathname.startsWith('/api/tools/')) return json(res, 200, { result: await runTool(db, pathname.slice('/api/tools/'.length), body) });
        throw new AppError(404, 'NOT_FOUND', 'API 경로를 찾을 수 없습니다.');
      } finally { active--; }
    } catch (error) {
      if (error instanceof AppError) json(res, error.status, { error: { code: error.code, message: error.message } });
      else { console.error('API failure:', error.code || error.name); json(res, 500, { error: { code: 'INTERNAL_ERROR', message: '처리에 실패했습니다. 입력 내용은 유지됩니다.' } }); }
    }
  };
}
