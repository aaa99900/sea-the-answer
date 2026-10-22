import test from 'node:test';
import assert from 'node:assert/strict';
import { textToSections } from '../src/lib/pdf.js';
import { documentSavePayload } from '../src/lib/document-save.js';

function assertPreserved(sections, source) {
  assert.equal(sections.map((section) => section.text).join(''), source.trim());
  assert.ok(sections.every((section) => section.text.trim() && section.text.length <= 19000));
}

test('text before the first page marker is retained with no invented page number', () => {
  assert.deepEqual(textToSections('  머리말 본문\n\n--- PAGE 7 ---\n일곱째 페이지\n'), [
    { page: null, heading: '본문', text: '머리말 본문' },
    { page: 7, heading: '페이지 7', text: '일곱째 페이지' },
  ]);
  const sections = textToSections('머리말\n--- PAGE ? ---\n페이지 미상 본문', '제3조');
  assert.deepEqual(
    sections.map((section) => section.page),
    [null, null],
  );
  assert.ok(sections.every((section) => section.heading === '제3조'));
});

test('blank prefixes and empty marked pages do not create empty input sections', () => {
  assert.deepEqual(textToSections(' \r\n\t\r\n--- PAGE 1 ---\n\n--- PAGE 2 ---\n본문'), [
    { page: 2, heading: '페이지 2', text: '본문' },
  ]);
  for (const source of ['', ' \r\n\t', '--- PAGE 1 ---\n--- PAGE ? ---\n']) {
    assert.deepEqual(textToSections(source), []);
  }
  assert.deepEqual(textToSections(' 짧은 본문 '), [{ heading: '본문', text: '짧은 본문' }]);
});

test('long text prefers a paragraph boundary over later sentence and word boundaries', () => {
  const paragraph = '첫 문단 내용 '.repeat(1200) + '\r\n \r\n';
  const source = paragraph + '다음 문장입니다. '.repeat(2000);
  const sections = textToSections(source);
  assert.equal(sections[0].text, paragraph);
  assertPreserved(sections, source);
});

test('long text prefers a sentence boundary and retains numeric values', () => {
  const sentence = '연료 0.50% / 3.114 검증 '.repeat(600) + '문장 끝.”';
  const source = sentence + '\n' + '다음 문장 내용 '.repeat(1600);
  const sections = textToSections(source);
  assert.equal(sections[0].text, sentence);
  assertPreserved(sections, source);
});

test('long text prefers a line boundary when no paragraph or sentence ends nearby', () => {
  const line = '열 데이터 '.repeat(1600) + '\n';
  const source = line + '다음 행 데이터 '.repeat(2000);
  const sections = textToSections(source);
  assert.equal(sections[0].text, line);
  assertPreserved(sections, source);
});

test('a word crossing the old 19000-character cut remains whole', () => {
  const prefix = '가 '.repeat(9497);
  const word = 'electroencephalographically';
  const source = prefix + word + ' 끝';
  const sections = textToSections(source);
  assert.equal(sections[0].text, prefix);
  assert.equal(sections[1].text, word + ' 끝');
  assertPreserved(sections, source);
});

test('a continuous long string has a bounded fallback without broken Unicode pairs', () => {
  const source = '가'.repeat(18999) + '🛳' + '나'.repeat(21000);
  const sections = textToSections(source);
  assert.equal(sections.length, 3);
  assert.equal(sections[0].text.length, 18999);
  assert.ok(sections.every((section) => section.text.isWellFormed()));
  assertPreserved(sections, source);
});

test('CRLF remains intact when it straddles the input size limit', () => {
  const source = '가'.repeat(18999) + '\r\n' + '나'.repeat(100);
  const sections = textToSections(source);
  assert.ok(!sections[0].text.endsWith('\r'));
  assert.ok(sections[1].text.startsWith('\r\n'));
  assertPreserved(sections, source);
});

test('long prefix and long pages retain source order and their own page metadata', () => {
  const prefix = '페이지 미상 머리말 '.repeat(2200);
  const page4 = '넷째 페이지 본문 '.repeat(2300);
  const page8 = '여덟째 페이지 본문 '.repeat(2100);
  const sections = textToSections(
    prefix + '\n--- PAGE 4 ---\r\n' + page4 + '\n--- PAGE 8 ---\n' + page8,
    '제7조',
  );
  const expectedPages = [null, 4, 8];
  assert.deepEqual([...new Set(sections.map((section) => section.page))], expectedPages);
  for (const [index, source] of [prefix, page4, page8].entries()) {
    assertPreserved(
      sections.filter((section) => section.page === expectedPages[index]),
      source,
    );
  }
  assert.ok(sections.every((section) => section.heading === '제7조'));
});

test('document save sends the preserved prefix and whole words through the existing API', () => {
  const page = '가 '.repeat(9497) + 'electroencephalographically 끝';
  const payload = documentSavePayload(
    {
      title: '신규 문서',
      kind: 'onboard',
      version: '1',
      text: '보존할 머리말\n--- PAGE 7 ---\n' + page,
    },
    { id: 'manual-new', today: '2026-10-18' },
  );
  assert.equal(payload.mode, 'content');
  assert.deepEqual(payload.document.sections[0], {
    page: null,
    heading: '본문',
    text: '보존할 머리말',
  });
  assertPreserved(
    payload.document.sections.filter((section) => section.page === 7),
    page,
  );
  assert.equal(payload.document.sections.at(-1).text, 'electroencephalographically 끝');
});
