import {UiText} from '../components/ui-language';
import {UiControl} from '../components/ui-language';
import React from 'react';
import {ReportFields, ReportPaper} from '../components/report-builder';
import {forms, label} from '../lib/report-forms';
import * as helpers from '../components/common';
export function createReportViews(model, views) {
  const noop = () => {};
  const { state, reportTypes, canWrite, isAdmin } = model;
  const { esc, btn, badge, dateText, options, head, notice, empty } = helpers;
  const { contextControls } = views;
  const { statusName } = views;
  function reportsPage() {
    const templatesLoading = !state.ready || state.connecting;
    const rows = state.reports.filter((r) =>
      (r.title + ' ' + r.type + ' ' + (forms[r.body?.formType]?.name || '')).toLowerCase().includes(state.reportQuery.toLowerCase()),
    );
    return (
      <>
        {
          <>
            {head(
              '보고서',
              '여러 보고서를 따로 보관하고 검토 상태를 확인하세요.',
              canWrite() ? <div className="report-entry-actions">
                {btn('보고서 생성', 'newReport', 'primary', 'plus', {disabled: templatesLoading})}
                {btn('이어 작성하기', 'resumeReport', 'report-resume', 'edit', {
                  disabled: templatesLoading || !model.resumableDraft(),
                })}
              </div> : null,
            )}
            <div className="actions mb">
              <a className="btn report-forms-link" href="/report-forms.pdf" target="_blank" rel="noreferrer">
                <UiText>보고서 양식 확인</UiText>
              </a>
            </div>
          </>
        }
        {
          <>
            <form className={'controls'} id={'reportSearch'}>
              <UiControl as="input"
                className={'control'}
                name={'query'}
                aria-label={'보고서 검색'}
                placeholder={'제목 또는 유형 검색'}
                defaultValue={state.reportQuery}
                onChange={noop}
              />
              <button className={'btn'}><UiText>{'검색'}</UiText></button>
              {btn('새로고침', 'refreshReports', 'ghost', 'refresh')}
            </form>
            <div className={'card'}>
              {rows.length
                ? rows.map((r, __index) => (
                    <React.Fragment key={__index}>
                      {
                        <div className={'docrow'}>
                          <div className={'docicon'}><UiText>{'보고'}</UiText></div>
                          <div className={'docmain'}>
                            <h3>{r.title}</h3>
                            <p className={'small muted'}>
                              {Object.hasOwn(forms,r.body?.formType) ? label(forms[r.body.formType].name,state.uiLanguage) : r.type}
                              {' · '}
                              {dateText(r.updatedAt,state.uiLanguage)}
                              <UiText>{' · 버전 '}</UiText>
                              {r.version}
                            </p>
                            <p className={'small'}>
                              {r.body?.from ? `${r.body.from} ~ ${r.body.to}` : ''}
                            </p>
                            {badge(
                              r.status === 'example' ? '예시' : statusName[r.status],
                              r.status === 'approved'
                                ? 'good'
                                : r.status === 'review'
                                  ? 'warn'
                                  : '',
                            )}
                          </div>
                          {btn('열기', 'openReport', 'sm', '', {
                            'data-id': r.id,
                          })}
                        </div>
                      }
                    </React.Fragment>
                  ))
                : empty('저장된 보고서가 없어요', '빈 초안을 작성하거나 운항 기록으로 시작하세요.')}
            </div>
          </>
        }

      </>
    );
  }
  function editorPage() {
    if (state.examplePreview) return <>
      {head('예시 보고서', state.examplePreview.title, btn('목록으로','reportList','','arrowback'))}
      <ReportPaper draft={state.examplePreview} documents={state.docs}/>
    </>;
    const d = state.draft,
      editable =
        !state.deletingReport && canWrite() && d.status === 'draft' && (!d.owner || d.owner === state.user.id || isAdmin());
    return (
      <>
        {head(
          '보고서 작성',
          '내용과 출처를 확인한 뒤 저장·검토를 진행하세요.',
          <>
            {btn('목록으로', 'reportList', '', 'arrowback')}
            <UiText>{isAdmin() && d.id && d.version > 0
              ? btn(state.deletingReport ? '삭제 중…' : '삭제', 'deleteReport', 'danger-outline', '', {
                  disabled: state.saving || state.deletingReport,
                })
              : ''}</UiText>
          </>,
        )}
        {
          <>
            <div className={'controls report-controls'}>
              <div className={'field'}>
                <label htmlFor={'report-type'}><UiText>{'보고서 유형'}</UiText></label>
                {forms[d.body?.formType] ? <strong id="report-type">{label(forms[d.body.formType].name,state.uiLanguage)}</strong> : <select
                  id={'report-type'}
                  data-report={'type'}
                  {...(!editable
                    ? {
                        disabled: true,
                      }
                    : {})}
                  value={d.type}
                  onChange={noop}
                >
                  {options(reportTypes)}
                </select>}
              </div>
              {badge(statusName[d.status] || '작성 중', d.status === 'approved' ? 'good' : '')}
              <span className={'small muted'}>
                <UiText>{'버전 '}</UiText>
                {d.version}
              </span>
              <div className={'actions'}>
                {btn('미리보기', 'previewReport', 'sm', 'file')}
                <UiText>{canWrite() ? btn('새 초안으로 복사', 'copyReport', 'sm', 'plus') : ''}</UiText>
              </div>
            </div>
            {state.reportError ? notice(state.reportError, 'warning') : ''}
            {state.conflict ? (
              <div className={'card pad mb'}>
                <h3><UiText>{'다른 창에서 변경되었어요.'}</UiText></h3>
                <p className={'small muted'}>
                  <UiText>{'서버 버전 '}</UiText>
                  {state.conflict.version}
                  {' · '}
                  {dateText(state.conflict.updatedAt)}
                  <UiText>{'. 편집 중인 내용은 유지됩니다.'}</UiText>
                </p>
                <div className={'actions mt'}>
                  {btn('서버 내용 확인', 'viewConflict', 'sm')}
                  {btn('내 초안 JSON 보관', 'backupDraft', 'sm')}
                  {btn('확인 후 대체 저장', 'replaceConflict', 'sm')}
                </div>
              </div>
            ) : (
              ''
            )}
            <div className={'report-layout'}>
              <section className={'card'}>
                <label className={'a11y-hidden'} htmlFor={'report-title'}>
                  <UiText>{'보고서 제목'}</UiText>
                </label>
                <UiControl as="input"
                  id={'report-title'}
                  className={'report-title'}
                  data-report={'title'}
                  maxLength={'120'}
                  placeholder={'보고서 제목'}
                  value={d.title}
                  {...(!editable
                    ? {
                        readOnly: true,
                      }
                    : {})}
                  onChange={noop}
                />
                {forms[d.body?.formType] && <ReportFields body={d.body} disabled={!editable} language={state.uiLanguage} onEdit={model.editReportBody}/>}
                {forms[d.body?.formType] ? <details className="report-text-preview">
                  <summary><UiText>{'출력용 본문'}</UiText></summary>
                  <textarea id="report-text" aria-label="출력용 본문" className="editor" readOnly value={d.text}/>
                </details> : <>
                  <label className="a11y-hidden" htmlFor="report-text"><UiText>{'보고서 본문'}</UiText></label>
                  <textarea id="report-text" className="editor" data-report="text" maxLength={200000}
                    readOnly={!editable} value={d.text} onChange={noop}/>
                </>}
                <div className={'report-actions'}>
                  <span id={'saveStatus'} className={'saved-state'}>
                    <UiText>{state.localFailed
                      ? '브라우저 보관 실패 · 파일로 보관해 주세요'
                      : state.dirty
                        ? '브라우저 임시 보관 · 저장 전'
                        : '저장된 내용'}</UiText>
                  </span>
                  <div className={'actions wrap'}>
                    {btn(state.downloadingReport ? 'PDF 생성 중…' : '다운로드', 'downloadReport', '', 'download', {disabled:state.downloadingReport})}
                    <UiText>{editable
                      ? btn(
                          state.saving ? '저장 중…' : '저장',
                          'saveReport',
                          'primary',
                          'save',
                          state.saving
                            ? {
                                disabled: true,
                              }
                            : {},
                        )
                      : ''}</UiText>
                    <UiText>{editable && d.id
                      ? btn(
                          '검토 요청',
                          'submitReport',
                          '',
                          '',
                          state.dirty
                            ? {
                                disabled: true,
                                title: '먼저 저장해 주세요',
                              }
                            : {},
                        )
                      : ''}</UiText>
                  </div>
                </div>
              </section>
              <aside>
                <div className={'card pad'}>
                  <h3><UiText>{'작성 근거'}</UiText></h3>
                  {d.sources.length ? (
                    d.sources.map((id, __index) => {
                      const s = state.docs.find((x) => x.id === id);
                      return (
                        <React.Fragment key={__index}>
                          {
                            <div className={'mt'}>
                              <button className={'source-card'} data-action={'source'} data-id={id}>
                                <strong>{s?.title || '열람 불가 문서'}</strong>
                                <small>{s?.version || ''}</small>
                              </button>
                              <UiText>{editable
                                ? btn('제거', 'removeSource', 'ghost sm', '', {
                                    'data-id': id,
                                  })
                                : ''}</UiText>
                            </div>
                          }
                        </React.Fragment>
                      );
                    })
                  ) : (
                    <p className={'small muted mt'}><UiText>{'연결된 문서가 없습니다.'}</UiText></p>
                  )}
                </div>
                <div className={'mt'}>
                  {notice(
                    d.status === 'approved'
                      ? '담당자가 승인한 버전입니다. 수정하려면 새 초안으로 복사하세요.'
                      : '승인 전 검토용 초안입니다. 누락 항목과 원본 기록을 확인해 주세요.',
                  )}
                </div>
              </aside>
            </div>
          </>
        }
      </>
    );
  }
  return {
    reportsPage,
    editorPage,
  };
}
