import test from 'node:test';
import assert from 'node:assert/strict';
import { documentSavePayload } from '../src/lib/document-save.js';

const existing = {
  id: 'manual-old',
  logical_id: 'manual',
  title: '기존 문서',
  version: '1',
  reviewed_at: '2026-10-01',
  sections: [{ id: 'manual-old-1', page: 7, heading: 'Part 1', text: '이미 가공된 청크' }],
  meta: {
    revision: 10,
    issuer: '',
    issuedAt: '',
    revisedAt: '',
    scope: 'all',
    status: 'active',
    applicability: '',
  },
};

test('opening and saving an unchanged document produces no request, even on a later date', () => {
  assert.equal(
    documentSavePayload(
      { documentMode: 'metadata', ...existing.meta },
      { existing, today: '2026-10-18' },
    ),
    null,
  );
});

test('metadata request contains only the logical ID and preserves opening version tokens', () => {
  const payload = documentSavePayload(
    {
      documentMode: 'metadata',
      issuer: '새 발행기관',
      text: 'hidden draft',
      title: 'hidden title',
    },
    { existing, file: { base64: 'hidden PDF' } },
  );
  assert.deepEqual(payload.document, { id: 'manual' });
  assert.equal(payload.expectedId, 'manual-old');
  assert.equal(payload.expectedMetaRevision, 10);
  assert.equal(payload.meta.issuer, '새 발행기관');
  assert.equal(payload.meta.scope, 'all');
  assert.equal(payload.file, undefined);
  assert.equal(payload.document.reviewedAt, undefined);
});

test('legacy missing optional metadata does not make an unchanged form dirty', () => {
  assert.equal(
    documentSavePayload(
      {
        issuer: '',
        issuedAt: '',
        revisedAt: '',
        applicability: '',
        scope: 'all',
        status: 'active',
      },
      { existing: { ...existing, meta: {} } },
    ),
    null,
  );
});

test('content revision requires new source and never falls back to stored chunks', () => {
  for (const text of [undefined, '', '   ', '--- PAGE 7 ---\n']) {
    assert.throws(
      () => documentSavePayload({ documentMode: 'content', text }, { existing }),
      /본문|원문/,
    );
  }
});

test('explicit revision sends fresh page source, PDF and the opening conflict tokens', () => {
  const file = { name: 'new.pdf', base64: 'PDF bytes' };
  const payload = documentSavePayload(
    {
      documentMode: 'content',
      title: '새 문서',
      version: '2',
      kind: 'onboard',
      reference: '제2조',
      text: '--- PAGE 9 ---\n새 원문입니다.',
    },
    { existing, file, today: '2026-10-18' },
  );
  assert.equal(payload.document.id, 'manual');
  assert.equal(payload.document.reviewedAt, '2026-10-18');
  assert.deepEqual(payload.document.sections, [
    { page: 9, heading: '제2조', text: '새 원문입니다.' },
  ]);
  assert.equal(payload.file, file);
  assert.equal(payload.expectedMetaRevision, 10);
  assert.equal(existing.sections[0].text, '이미 가공된 청크');
});

test('new registration keeps the existing full-document API contract', () => {
  const payload = documentSavePayload(
    { title: '신규', kind: 'onboard', version: '1', reference: '본문', text: '새로 등록할 원문' },
    { id: 'manual-new', today: '2026-10-18' },
  );
  assert.equal(payload.mode, 'content');
  assert.equal(payload.document.id, 'manual-new');
  assert.equal(payload.expectedId, '');
  assert.equal('expectedMetaRevision' in payload, false);
});
