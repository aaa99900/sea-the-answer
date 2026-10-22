import { textToSections } from './pdf.js';

const metadataDefaults = {
  issuer: '',
  issuedAt: '',
  revisedAt: '',
  scope: 'all',
  status: 'active',
  applicability: '',
};

// Editing starts with metadata only. Existing search chunks are never source input.
export function documentSavePayload(values, { existing = null, id, file = null, today } = {}) {
  const mode = values.documentMode || (existing ? 'metadata' : 'content');
  const meta = Object.fromEntries(
    Object.entries(metadataDefaults).map(([key, fallback]) => [
      key,
      values[key] ?? existing?.meta?.[key] ?? fallback,
    ]),
  );
  const expected = {
    expectedId: existing?.id || '',
    ...(existing ? { expectedMetaRevision: existing.meta?.revision ?? 0 } : {}),
  };
  if (mode === 'metadata') {
    if (!existing) throw Error('정보를 수정할 문서를 다시 열어 주세요.');
    if (
      Object.entries(meta).every(
        ([key, value]) => value === (existing.meta?.[key] ?? metadataDefaults[key]),
      )
    )
      return null;
    return { mode, document: { id: existing.logical_id }, ...expected, meta };
  }
  if (mode !== 'content') throw Error('문서 저장 방식을 확인해 주세요.');
  if (!values.text?.trim())
    throw Error('본문·버전 개정에는 PDF를 다시 선택하거나 원문 전체를 입력해 주세요.');
  const sections = textToSections(values.text, values.reference);
  if (!sections.length) throw Error('검색할 본문이 없습니다. 원문을 확인해 주세요.');
  return {
    mode,
    document: {
      id: existing?.logical_id || id,
      title: values.title,
      version: values.version,
      kind: values.kind,
      url: values.url || null,
      reference: values.reference,
      reviewedAt: today || new Date().toISOString().slice(0, 10),
      language: /[가-힣]/.test(values.text) ? 'ko' : 'en',
      sections,
    },
    ...expected,
    meta,
    ...(file ? { file } : {}),
  };
}
