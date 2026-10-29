// Real Next.js UI with mocked HTTP responses. Does not claim DB/LLM integration coverage.
import { test, expect } from '@playwright/test';

async function mockWorkspace(page, admin = false) {
  const state = {
    admin, loggedIn: true, deleteError: false, deleteCalls: [], history: [], waitForAnswer: null,
    waitForOperations: null, generationCalls: [],
    reports: [{ id: 'report-1', title: '삭제 검증 보고서', type: '규정 검토', text: '보존할 보고서 본문',
      sources: [], version: 3, status: 'draft', owner: 'crew_3edf36ec', body: {}, updatedAt: '2026-10-18' }],
  };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  state.errors = errors;
  await page.route('**/api/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    const json = (data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    const user = !state.loggedIn ? { id: 'guest_test', name: '일반 사용자', role: 'guest' }
      : state.admin ? { id: 'admin', name: '관리자', role: 'admin' }
        : { id: 'crew_3edf36ec', name: '일반 사용자', role: 'operator' };
    if (path === '/api/health') return json({ csrfToken: 'test', user, authenticated: state.loggedIn,
      publicAccess: false, llmConfigured: false });
    if (path === '/api/auth/login') {
      state.admin = true; state.loggedIn = true;
      return json({ user: { id: 'admin', name: '관리자', role: 'admin' } });
    }
    if (path === '/api/auth/logout') { state.admin = false; state.loggedIn = false; return json({ ok: true }); }
    if (path === '/api/documents') return json({ documents: [{ id: 'manual-1', logical_id: 'manual',
      title: '검증 문서', reference: 'Part 1', kind: 'onboard', version: '1', active: true, currentRevision: true,
      reviewed_at: '2026-10-18', meta: { scope: 'all', status: 'active' },
      sections: [{ id: 'chunk-1', heading: '기본 조항', text: '검증 본문', page: 1 }] }] });
    if (path === '/api/operations') {
      if (state.waitForOperations) await state.waitForOperations();
      return json({ ships: [{ id: 'ship-1', name: '검증 선박', type: 'Bulk carrier', dwt: 1000 }],
        records: [{ id: 'record-1', ship: 'ship-1', date: '2026-09-25', fuel: 10, factor: 3.114, distance: 100,
          speed: 10, fuelType: 'HFO', version: 1 }] });
    }
    if (path === '/api/reports') return json({ reports: state.reports });
    if (path === '/api/reports/generate') {
      const payload = request.postDataJSON();
      state.generationCalls.push(payload);
      const report = {
        id: 'generated-report-' + state.generationCalls.length, title: '검증 선박 · Noon Report',
        type: '일일 운항', text: '# Noon Report\n검증 선박의 운항 기록으로 생성한 초안입니다.',
        sources: [], version: 1, status: 'draft', owner: user.id, body: payload, updatedAt: '2026-10-29',
      };
      state.reports.push(report);
      return json({ report });
    }
    if (path === '/api/reports/delete') {
      const payload = request.postDataJSON(); state.deleteCalls.push(payload);
      if (state.deleteError) return json({ error: { code: 'VERSION_CONFLICT', message: '보고서가 변경되었습니다. 다시 열어 확인해 주세요.' } }, 409);
      state.reports = state.reports.filter(report => report.id !== payload.id);
      return json({ ok: true, id: payload.id });
    }
    if (path.startsWith('/api/reports/')) return json({ report: state.reports.find(r => r.id === path.split('/').at(-1)) });
    if (path === '/api/ask') {
      const question = request.postDataJSON().question;
      if (state.waitForAnswer) await state.waitForAnswer();
      const answer = { id: 'answer-1', question, language: 'ko', generation: 'extractive', status: 'insufficient_evidence',
        notice: '검증 응답', warnings: [], statements: [], evidence: [], toolRuns: [] };
      state.history = [{ id: answer.id, question, answer, at: '2026-10-18T00:00:00Z' }];
      return json(answer);
    }
    if (path === '/api/history') return json({ history: state.history });
    return json({ changes: [], logs: [], users: [], backups: [] });
  });
  return state;
}

const action = (page, name) => page.locator(`[data-action="${name}"]`);
const go = (page, name) => page.locator(`[data-nav="${name}"]`).click();
const ask = async (page, text) => {
  await page.locator('#question').fill(text);
  await page.locator('#askForm').evaluate(form => form.requestSubmit());
};

test('crew label, branding, brand navigation and admin-only controls', async ({ page }) => {
  const state = await mockWorkspace(page);
  await page.goto('/documents/manual-1');
  await expect(page.locator('.account .small')).toHaveText('일반 사용자');
  await expect(page.locator('body')).not.toContainText('3edf36ec');
  await expect(page.locator('.doc-kicker')).toHaveText('SEA THE ANSWER / DOCUMENT');
  await expect(action(page, 'deleteDocument')).toHaveCount(0);
  await action(page, 'home').click();
  await expect(page).toHaveURL(/\/chat$/);
  await go(page, 'operations');
  await expect(action(page, 'deleteRecord')).toHaveCount(0);
  await go(page, 'reports');
  await action(page, 'openReport').click();
  await expect(action(page, 'deleteReport')).toHaveCount(0);
  await action(page, 'logout').click();
  await expect(page.locator('.eyebrow')).toHaveText('SEA THE ANSWER WORKSPACE');
  expect(state.errors).toEqual([]);
});

test('question menu resets the answer and input while stored history still opens', async ({ page }) => {
  const state = await mockWorkspace(page);
  await page.goto('/chat');
  await ask(page, '저장할 질문');
  await expect(page.locator('.answer')).toBeVisible();
  await go(page, 'chat');
  await expect(page.locator('.answer')).toHaveCount(0);
  await expect(page.locator('#question')).toHaveValue('');
  await action(page, 'history').click();
  await action(page, 'historyAnswer').click();
  await expect(page.locator('.answer')).toBeVisible();
  await go(page, 'docs');
  await go(page, 'chat');
  await expect(page.locator('.answer')).toHaveCount(0);
  await page.locator('#question').fill('전송 전 입력');
  await go(page, 'chat');
  await expect(page.locator('#question')).toHaveValue('');
  expect(state.history).toHaveLength(1);
  expect(state.errors).toEqual([]);
});

test('late response cannot repopulate a question screen reset from the menu', async ({ page }) => {
  const state = await mockWorkspace(page);
  let release, started;
  const requestStarted = new Promise(resolve => { started = resolve; });
  state.waitForAnswer = () => { started(); return new Promise(resolve => { release = resolve; }); };
  await page.goto('/chat');
  await ask(page, '오래 걸리는 질문');
  await requestStarted;
  await go(page, 'chat');
  const response = page.waitForResponse('**/api/ask');
  release(); await response;
  await expect(page.locator('.chat-intro')).toBeVisible();
  await expect(page.locator('.answer')).toHaveCount(0);
  state.waitForAnswer = null;
  await ask(page, '새 질문');
  await expect(page.locator('.question-bubble')).toHaveText('새 질문');
  expect(state.errors).toEqual([]);
});

test('report templates wait for login operation data before generating a draft', async ({ page }) => {
  const state = await mockWorkspace(page);
  state.reports = [];
  await page.clock.install();
  await page.goto('/reports');
  await expect(page.locator('.connection')).toHaveText('서버 연결됨');
  await action(page, 'logout').click();
  await expect(page.locator('#authForm')).toBeVisible();
  await expect(page.locator('#toasts')).toContainText('로그아웃했습니다.');

  let releaseOperations, operationsStarted;
  const operationsBarrier = new Promise(resolve => { releaseOperations = resolve; });
  const operationsRequested = new Promise(resolve => { operationsStarted = resolve; });
  state.waitForOperations = async () => {
    operationsStarted();
    await operationsBarrier;
  };
  await page.locator('#auth-username').fill('admin');
  await page.locator('#auth-password').fill('Test-only-password');
  await page.locator('#authForm').evaluate(form => form.requestSubmit());
  await operationsRequested;
  try {
    // Expiring the real logout toast rerenders after health has authenticated
    // the account, while refreshAll still waits for its operation data.
    await page.clock.fastForward(5000);
    await expect(page.locator('#toasts')).not.toContainText('로그아웃했습니다.');
    await go(page, 'reports');
    await expect(page).toHaveURL(/\/reports$/);
    await expect(page.locator('.connection')).toHaveText('연결 확인');
    await expect(action(page, 'templateNoon')).toBeDisabled();
    await expect(action(page, 'templateMrv')).toBeDisabled();
    expect(state.generationCalls).toEqual([]);
  } finally {
    state.waitForOperations = null;
    releaseOperations();
  }

  await expect(page.locator('.connection')).toHaveText('서버 연결됨');
  await expect(action(page, 'templateNoon')).toBeEnabled();
  await expect(action(page, 'templateMrv')).toBeEnabled();
  await action(page, 'templateNoon').click();
  await expect(page).toHaveURL(/\/reports\/generated-report-1$/);
  await expect(page.locator('#report-text')).toHaveValue('# Noon Report\n검증 선박의 운항 기록으로 생성한 초안입니다.');
  expect(state.generationCalls).toEqual([{
    template: 'noon', ship: 'ship-1', from: '2026-09-22', to: '2026-09-28',
  }]);
  expect(state.errors).toEqual([]);
});

test('delete buttons share red outline and adjacent button sizing', async ({ page }, testInfo) => {
  const state = await mockWorkspace(page, true);
  const check = async (deleteName, neighbor) => {
    const button = action(page, deleteName);
    await expect(button).toBeVisible();
    const style = await button.evaluate(el => {
      const css = getComputedStyle(el);
      return { color: css.color, border: css.borderTopColor, height: el.getBoundingClientRect().height };
    });
    expect(style.color).toBe('rgb(183, 66, 61)'); expect(style.border).toBe(style.color);
    expect(style.height).toBe(await action(page, neighbor).evaluate(el => el.getBoundingClientRect().height));
  };
  await page.goto('/documents/manual-1');
  await check('deleteDocument', 'editDocument');
  await page.screenshot({ path: testInfo.outputPath('document-desktop.png'), fullPage: true });
  await go(page, 'operations');
  await check('deleteRecord', 'editRecord');
  await go(page, 'reports'); await action(page, 'openReport').click();
  await check('deleteReport', 'reportList');
  await page.screenshot({ path: testInfo.outputPath('report-desktop.png'), fullPage: true });
  expect(state.errors).toEqual([]);
});

test('report deletion cancel, conflict, success, local draft cleanup and reload', async ({ page }) => {
  const state = await mockWorkspace(page, true);
  await page.goto('/reports'); await action(page, 'openReport').click();
  await action(page, 'deleteReport').click(); await page.getByRole('button', { name: '취소', exact: true }).click();
  expect(state.deleteCalls).toEqual([]);
  state.deleteError = true;
  await action(page, 'deleteReport').click(); await action(page, 'confirm').click();
  await expect(page.locator('.body .notice.warning')).toContainText('보고서가 변경되었습니다.');
  await expect(page.locator('#report-text')).toHaveValue('보존할 보고서 본문');
  state.deleteError = false;
  await action(page, 'deleteReport').click(); await action(page, 'confirm').click();
  await expect(page).toHaveURL(/\/reports$/);
  await expect(action(page, 'openReport')).toHaveCount(0);
  expect(state.deleteCalls.at(-1)).toEqual({ id: 'report-1', version: 3 });
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('haedap-workspace-draft-v2-admin')).id)).toBe('');
  await page.reload(); await action(page, 'newReport').click();
  await expect(page.locator('#report-text')).toHaveValue('');
  await expect(action(page, 'deleteReport')).toHaveCount(0);
  expect(state.errors).toEqual([]);
});

test('mobile brand and report actions remain visible without page overflow', async ({ page }, testInfo) => {
  const state = await mockWorkspace(page, true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/reports'); await action(page, 'openReport').click();
  await expect(action(page, 'deleteReport')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('report-mobile.png'), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.locator('.mobile-menu').click();
  await action(page, 'home').focus(); await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.locator('.sidebar')).not.toHaveClass(/\bopen\b/);
  expect(state.errors).toEqual([]);
});
