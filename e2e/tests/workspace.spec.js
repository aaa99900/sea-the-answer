// Full workspace flow in one browser session (ported from scripts/next-browser-smoke.mjs).
// Steps share state (login, sample data, created records), so they run in order inside one test.
import { test, expect } from '@playwright/test';

// A real one-page PDF exercises the local PDF.js worker and persisted source bytes.
function onePagePdf(text) {
  const content = `BT /F1 12 Tf 50 750 Td (${text}) Tj ET`;
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
  ];
  let pdf = '%PDF-1.4\n';
  const offsets = [];
  objects.forEach((o, i) => {
    offsets.push(Buffer.byteLength(pdf));
    pdf += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = Buffer.byteLength(pdf);
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets
    .map((x) => String(x).padStart(10, '0') + ' 00000 n ')
    .join('\n')}\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return pdf;
}

test.beforeAll(async ({ request }) => {
  // The stack may still be starting (local runs); compose waits on health checks already.
  await expect
    .poll(async () => (await request.get('/api/health').catch(() => null))?.ok() ?? false, {
      timeout: 120_000,
      intervals: [500, 1000, 2000],
    })
    .toBe(true);
});

test('workspace: documents, operations, reports, admin review, backup', async ({ page, context }, testInfo) => {
  const errors = [];
  const warnings = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (['error', 'warning'].includes(m.type())) warnings.push(m.text());
  });

  const action = (a) => page.locator(`[data-action=${a}]`);
  const go = async (name) => {
    await page.locator(`[data-nav=${name}]`).click();
    await page.waitForTimeout(100);
  };
  const confirm = () => action('confirm').click();
  const close = () => action('closeModal').click();
  const submit = (form) => page.locator(form).evaluate((f) => f.requestSubmit());
  const dialogClosed = () => page.waitForFunction(() => !document.querySelector('dialog').open);
  const login = async (password = 'E2e-personal-admin-2026', username = 'e2e-admin') => {
    await page.locator('#auth-username').fill(username);
    await page.locator('#auth-password').fill(password);
    await submit('#authForm');
  };
  // Calls the API from the page, like the UI does (CSRF token + identity headers).
  const api = (path, body) =>
    page.evaluate(
      async ({ path, body }) => {
        const health = await (await fetch('/api/health')).json();
        const r = await fetch(path, {
          method: body ? 'POST' : 'GET',
          headers: body
            ? {
                'Content-Type': 'application/json',
                'X-Haedap-Token': health.csrfToken,
                'X-Haedap-Identity': health.user.id,
              }
            : {},
          body: body ? JSON.stringify(body) : undefined,
        });
        return { status: r.status, data: await r.json() };
      },
      { path, body },
    );
  const records = async () => (await api('/api/operations')).data.records;

  await test.step('Anonymous access blocked; bootstrap password rotation and crew provisioning', async () => {
    await page.goto('/');
    await page.locator('#authForm').waitFor();
    expect((await api('/api/documents')).status).toBe(401);
    await expect(page.locator('#question')).toHaveCount(0);
    await login('E2e-initial-only-2026');
    await page.locator('#passwordForm').waitFor();
    expect((await api('/api/documents')).data.error.code).toBe('PASSWORD_CHANGE_REQUIRED');
    await page.locator('#auth-password').fill('E2e-initial-only-2026');
    await page.locator('#auth-new-password').fill('E2e-personal-admin-2026');
    await page.locator('#auth-confirm-password').fill('E2e-personal-admin-2026');
    await submit('#passwordForm');
    await page.locator('#question').waitFor();
    await expect(page).toHaveURL(/\/chat$/);
    await expect(page.locator('.brand small')).toHaveText('SEA THE ANSWER');
    await go('admin');
    await action('adminTab').filter({ hasText: '사용자' }).click();
    await action('newUser').click();
    await page.locator('#f-name').fill('E2E 선원');
    await page.locator('#f-username').fill('e2e-crew');
    await expect(page.locator('#f-role')).toHaveValue('operator');
    await page.locator('#f-password').fill('E2e-initial-crew-2026');
    await submit('#userForm');
    await dialogClosed();
    await action('logout').click();
    await page.locator('#authForm').waitFor();
    await login('E2e-initial-crew-2026', 'e2e-crew');
    await page.locator('#passwordForm').waitFor();
    await page.locator('#auth-password').fill('E2e-initial-crew-2026');
    await page.locator('#auth-new-password').fill('E2e-personal-crew-2026');
    await page.locator('#auth-confirm-password').fill('E2e-personal-crew-2026');
    await submit('#passwordForm');
    await page.locator('#question').waitFor();
    expect((await api('/api/users')).status).toBe(403);
  });

  await test.step('Question, real search, source dialog', async () => {
    await page.locator('#question').fill('연료 황 함유량 기준을 알려줘');
    await submit('#askForm');
    await expect(page.locator('.answer')).toContainText('0.50%');
    await action('source').first().click();
    expect(await page.locator('dialog').evaluate((d) => d.open)).toBe(true);
    await close();
  });

  await test.step('Document routing, direct refresh, crew controls', async () => {
    await go('docs');
    await expect(action('newDocument')).toHaveCount(0);
    await action('document').first().click();
    await page.waitForURL('**/documents/*');
    await expect(action('editDocument')).toHaveCount(0);
    const documentUrl = page.url();
    await page.reload();
    await page.locator('.paper h2').waitFor();
    expect(page.url()).toBe(documentUrl);
  });

  await test.step('Crew mutation buttons hidden and backend rejects writes', async () => {
    await go('operations');
    for (const a of ['newShip', 'newRecord', 'importOperations', 'editRecord', 'deleteRecord'])
      await expect(action(a)).toHaveCount(0);
    expect((await api('/api/changes', { kind: 'ship.save', payload: {} })).status).toBe(403);
  });

  await test.step('Failed login retry, admin login, sample initialization', async () => {
    await action('logout').click();
    await page.locator('#authForm').waitFor();
    await login('wrong');
    await page.locator('#authError').filter({ hasText: '올바르지' }).waitFor();
    await expect(page.locator('#authForm button[type=submit]')).toBeEnabled();
    await page.locator('#auth-password').fill('E2e-personal-admin-2026');
    await submit('#authForm');
    await action('logout').waitFor();
    await go('operations');
    await action('seedExample').click();
    await confirm();
    await page.locator('table tbody tr').first().waitFor();
    expect(await records()).toHaveLength(21);
  });

  await test.step('Document create, revision and immediate deletion', async () => {
    await go('docs');
    await action('newDocument').click();
    await page.locator('#f-title').fill('Next.js 검증 문서');
    await page.locator('#f-reference').fill('NEXT TEST');
    await page.locator('#f-text').fill('--- PAGE 7 ---\n원문을 확인하고 운항 기록을 점검합니다.');
    await page.locator('[name=checked]').check();
    await submit('#documentForm');
    const created = page.locator('.docrow').filter({ hasText: 'Next.js 검증 문서' });
    await created.waitFor();
    await created.locator('[data-action=document]').click();
    await action('editDocument').click();
    await expect(page.locator('#documentForm button[type=submit]')).toHaveText('저장');
    await page.locator('#f-title').fill('Next.js 수정 문서');
    await page.locator('#f-version').fill('2');
    await page.locator('[name=checked]').check();
    await submit('#documentForm');
    await dialogClosed();
    await go('docs');
    const revised = page.locator('.docrow').filter({ hasText: 'Next.js 수정 문서' });
    await revised.locator('[data-action=document]').click();
    await action('deleteDocument').click();
    await expect(action('confirm')).toHaveText('삭제');
    await confirm();
    await page.waitForURL('**/documents');
    await expect(revised).toHaveCount(0);
  });

  await test.step('PDF.js extraction, page provenance, persisted PDF retrieval', async () => {
    const pdfText = 'Next.js migration PDF evidence.';
    const pdf = onePagePdf(pdfText);
    await go('docs');
    await action('newDocument').click();
    await page
      .locator('#document-file')
      .setInputFiles({ name: 'migration.pdf', mimeType: 'application/pdf', buffer: Buffer.from(pdf) });
    await page.waitForFunction(
      (t) => document.querySelector('#f-text')?.value.includes(t),
      pdfText,
    );
    await page.locator('#f-title').fill('원문 PDF 검증');
    await page.locator('[name=checked]').check();
    await submit('#documentForm');
    await page.locator('.docrow').filter({ hasText: '원문 PDF 검증' }).locator('[data-action=document]').click();
    await action('documentPdf').click();
    const src = await page.locator('iframe.pdf-frame').getAttribute('src');
    const response = await context.request.get(src);
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toMatch(/application\/pdf/);
    expect((await response.body()).toString()).toBe(pdf);
  });

  await test.step('Ship and record registration, record deletion', async () => {
    await go('operations');
    await action('newShip').click();
    await page.locator('#f-name').fill('Next 검증 선박');
    await page.locator('#f-type').fill('벌크선');
    await page.locator('#f-dwt').fill('2000');
    await submit('#shipForm');
    await dialogClosed();
    expect((await api('/api/operations')).data.ships).toHaveLength(4);
    await action('newRecord').click();
    await page.locator('#f-date').fill('2026-09-30');
    for (const [field, value] of Object.entries({ fuel: '20', factor: '3.114', distance: '200', speed: '10', fuelType: 'LSFO' }))
      await page.locator('#f-' + field).fill(value);
    await submit('#recordForm');
    await dialogClosed();
    const added = (await records()).find((r) => r.date === '2026-09-30');
    expect(added).toBeTruthy();
    await page.locator(`[data-action=deleteRecord][data-id="${added.id}"]`).click();
    await confirm();
    await dialogClosed();
    expect(await records()).toHaveLength(21);
  });

  await test.step('Record editing with date filter', async () => {
    await page.locator('#to').fill('2026-09-28');
    await go('operations');
    await action('editRecord').first().click();
    await page.locator('#f-note').fill('React 즉시 수정 검증');
    await submit('#recordForm');
    await dialogClosed();
    expect((await records()).some((r) => r.note === 'React 즉시 수정 검증')).toBe(true);
  });

  await test.step('Server calculation and rendered result', async () => {
    await page.locator('[data-tab=calculation]').click();
    await action('useSampleInputs').click();
    await submit('#calcForm');
    await page.locator('.formula').waitFor();
    await expect(page.locator('.calculation-result')).toContainText('CO₂');
  });

  await test.step('CSV upload, validation preview and import', async () => {
    await go('operations');
    await page.locator('[data-tab=overview]').click();
    await action('importOperations').click();
    const ship = (await api('/api/operations')).data.ships[0].id;
    await page.locator('#csvForm [type=file]').setInputFiles({
      name: 'voyage.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(`ship,date,fuel,factor,distance,speed,fuelType\n${ship},2026-09-29,20,3.114,200,10,LSFO`),
    });
    await submit('#csvForm');
    await action('commitCsv').click();
    await dialogClosed();
    expect(await records()).toHaveLength(22);
  });

  await test.step('Crew report generation, saving, navigation, reload, review submission', async () => {
    await action('logout').click();
    await page.locator('#authForm').waitFor();
    await login('E2e-personal-crew-2026', 'e2e-crew');
    await page.locator('#question').waitFor();
    await go('reports');
    await action('templateNoon').click();
    await page.waitForFunction(() => document.querySelector('#report-text')?.value.includes('Noon'));
    expect(page.url()).toMatch(/\/reports\/(?!new)/);
    await page.locator('#report-title').fill('게스트 Next 보고서');
    await action('saveReport').click();
    await page.waitForFunction(() => document.querySelector('#saveStatus')?.textContent === '저장된 내용');
    await go('docs');
    await page.goBack();
    await expect(page.locator('#report-title')).toHaveValue('게스트 Next 보고서');
    await page.reload();
    await page.locator('#report-text').waitFor();
    await expect(page.locator('#report-title')).toHaveValue('게스트 Next 보고서');
    if (await action('submitReport').isDisabled()) {
      await action('saveReport').click();
      await expect(action('submitReport')).toBeEnabled();
    }
    await action('submitReport').click();
    await confirm();
    await page.waitForFunction(() => document.querySelector('#report-text')?.readOnly);
  });

  await test.step('Report approval workflow', async () => {
    await action('logout').click();
    await page.locator('#authForm').waitFor();
    await login();
    await action('logout').waitFor();
    await go('admin');
    await action('adminTab').filter({ hasText: '승인' }).click();
    await page
      .locator('.docrow')
      .filter({ hasText: '보고서 확정 검토' })
      .locator('[data-action=reviewChange]')
      .click();
    await action('approveChange').click();
    await confirm();
    await dialogClosed();
    const report = (await api('/api/reports')).data.reports.find((r) => r.title === '게스트 Next 보고서');
    expect(report.status).toBe('approved');
  });

  await test.step('Backup creation, restoration and login invalidation', async () => {
    await action('adminTab').filter({ hasText: '백업·복구' }).click();
    const created = page.waitForResponse((response) =>
      response.url().endsWith('/api/backups') && response.request().method() === 'POST');
    await action('createBackup').click();
    const { backup } = await (await created).json();
    const restore = page.locator(`[data-action=restoreBackup][data-id="${backup.id}"]`);
    await restore.click();
    await page.locator('#f-confirm').fill('복구');
    await submit('#restoreForm');
    await page.locator('#authForm').waitFor();
    expect((await api('/api/health')).data.user.role).toBe('guest');
    expect((await api('/api/operations')).status).toBe(401);
    await login();
    await action('logout').waitFor();
    expect(await records()).toHaveLength(22);
  });

  await test.step('Mobile navigation and overflow', async () => {
    await go('chat');
    await page.waitForFunction(() => !document.querySelector('.toast'));
    await page.screenshot({ path: testInfo.outputPath('desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('.mobile-menu').click();
    await expect(page.locator('.sidebar')).toHaveClass(/\bopen\b/);
    await page.locator('[data-nav=docs]').click();
    await page.waitForTimeout(300);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('mobile.png'), fullPage: true });
  });

  await test.step('No browser exceptions or React warnings', async () => {
    expect(errors, 'Browser runtime errors').toEqual([]);
    const significant = warnings.filter(
      (t) => !['favicon', '403', '401', '[HMR]', 'React DevTools'].some((s) => t.includes(s)),
    );
    expect(significant, 'React/browser warnings').toEqual([]);
  });
});
