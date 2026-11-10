import {UiText} from '../components/ui-language';
import {UiControl} from '../components/ui-language';
import React from 'react';
import * as helpers from '../components/common';
export function createExtendedViews(model, views) {
  const noop = () => {};
  const { state, isAdmin } = model;
  const { esc, I, btn, badge, head, empty, dateText, n, options, notice, stat } = helpers;
  const { chartSVG } = views;
  const roleName = {
    guest: '로그인 필요',
    admin: '관리자 · 승인',
    operator: '일반 선원',
    viewer: '열람 전용',
  };
  const statusName = {
    draft: '작성 중',
    review: '검토 대기',
    approved: '승인 완료',
    pending: '승인 대기',
    rejected: '반려',
  };
  function authPage() {
    const changing = state.user?.must_change_password || state.passwordOpen;
    return (
      <main className={'login-layout'}>
        <section className={'login-brand'}>
          <div className={'brandmark'}>{I('ship')}</div>
          <h1><UiText>{'해답'}</UiText></h1>
          <p>
            <UiText>{'문서의 근거부터'}</UiText>
            <br />
            <UiText>{'오늘의 운항 기록까지.'}</UiText>
          </p>
          <small><UiText>{'선박 운항 업무지원'}</UiText></small>
        </section>
        <section className={'login-card'}>
          <button className="btn ghost sm" data-action="selectLanguage">Select Language</button>
          <span className={'eyebrow'}>{'SEA THE ANSWER WORKSPACE'}</span>
          <h2><UiText>{changing ? '비밀번호 변경' : '선원·관리자 로그인'}</UiText></h2>
          <p className={'muted mb'}>
            <UiText>{changing
              ? '본인만 아는 12~128자의 비밀번호를 설정해 주세요. 변경 후 다른 기기의 세션은 종료됩니다.'
              : '관리자가 발급한 개인 계정으로 로그인해 주세요. 계정 발급·초기화는 관리자에게 요청하세요.'}</UiText>
          </p>
          <form id={changing ? 'passwordForm' : 'authForm'}>
            {!changing ? <div className={'field'}>
              <label htmlFor={'auth-username'}><UiText>{'아이디'}</UiText></label>
              <input
                id={'auth-username'}
                name={'username'}
                required
                maxLength={'40'}
                autoComplete={'username'}
                onChange={noop}
              />
            </div> : <p className={'mb'}>{state.user.name} · {state.user.username}</p>}
            <div className={'field'}>
              <label htmlFor={'auth-password'}><UiText>{changing ? '현재 비밀번호' : '비밀번호'}</UiText></label>
              <input
                id={'auth-password'}
                name={changing ? 'currentPassword' : 'password'}
                type={'password'}
                required
                maxLength={'128'}
                autoComplete={'current-password'}
                onChange={noop}
              />
            </div>
            {changing ? <>
              <div className={'field'}>
                <label htmlFor={'auth-new-password'}><UiText>{"새 비밀번호"}</UiText></label>
                <input id={'auth-new-password'} name={'newPassword'} type={'password'} required
                  minLength={12} maxLength={128} autoComplete={'new-password'} />
              </div>
              <div className={'field'}>
                <label htmlFor={'auth-confirm-password'}><UiText>{"새 비밀번호 확인"}</UiText></label>
                <input id={'auth-confirm-password'} name={'confirmPassword'} type={'password'} required
                  minLength={12} maxLength={128} autoComplete={'new-password'} />
              </div>
            </> : null}
            <p className={'inline-error mt'} id={'authError'} role={'alert'}>
              {state.authError || state.connectionError}
            </p>
            <button
              type={'submit'}
              className={'btn primary login-submit'}
              {...(state.connecting || state.authBusy
                ? {
                    disabled: true,
                  }
                : {})}
            >
              <UiText>{state.connecting || state.authBusy ? '처리 중…' : changing ? '비밀번호 변경' : '로그인'}</UiText>
            </button>
          </form>
          <UiText>{changing ? btn('로그아웃', 'logout', 'mt') : null}</UiText>
          <UiText>{changing && !state.user?.must_change_password ? btn('돌아가기', 'cancelPassword', 'mt') : null}</UiText>
          <UiText>{state.connectionError ? btn('서버 다시 연결', 'reconnect', 'mt') : ''}</UiText>
        </section>
      </main>
    );
  }
  function ciiText(cii, en = false) {
    if (cii?.status === 'available' && Number.isFinite(cii.value))
      return `${en ? 'CII result' : 'CII 산출값'}: ${n(cii.value, 3)} ${cii.unit || ''} · ${en ? 'Rating' : '등급'} ${cii.rating || '미제공'} · ${cii.year || ''} / ${cii.method || '산식 확인 필요'}`;
    return en
      ? 'CII unavailable: verified annual coverage, vessel-specific method and adjustment criteria are required.'
      : 'CII 산출 불가: ' + (cii?.reason || '산출 조건과 입력 데이터가 부족합니다.');
  }
  function operationAnswer(a) {
    const s = a.operations;
    if (!s) return a.operationNotice ? notice(a.operationNotice) : '';
    const en = a.language === 'en',
      c = a.compliance || {
        status: 'unknown',
        label: '판단 불가',
        reason: '규정 근거 확인이 필요합니다.',
      };
    return (
      <section className={'integrated-result mt'}>
        <div className={'sectiontitle'}>
          <h3><UiText>{en ? 'Operations summary' : '운항 데이터 요약'}</UiText></h3>
          <UiText>{s.sample
            ? badge(en ? 'Sample data' : '가상 데이터', 'warn')
            : badge(en ? 'Saved records' : '저장 기록', 'teal')}</UiText>
        </div>
        <p className={'small muted'}>
          {s.ship.name}
          {' · '}
          {s.from}
          {' ~ '}
          {s.to}
          {' · '}
          {s.count}
          <UiText>{en ? ' records' : '개 기록'}</UiText>
        </p>
        {s.count ? (
          <>
            <div className={'grid3 mt'}>
              {stat(en ? 'Fuel' : '연료', n(s.fuel), 't', '')}
              {stat('CO₂', n(s.emission), 't', '')}
              {stat(en ? 'Distance' : '거리', n(s.distance), 'nm', '')}
            </div>
            <div className={'card pad mt'}>
              <h3><UiText>{en ? 'Daily CO₂ emissions' : '일별 CO₂ 배출량'}</UiText></h3>
              {s.rowsTruncated && notice(en
                ? `Totals include all ${n(s.totalRows, 0)} records; the graph and table below show only the first ${n(s.rows.length, 0)}.`
                : `총 ${n(s.totalRows, 0)}건으로 집계했으며, 아래 그래프·표는 처음 ${n(s.rows.length, 0)}건만 표시합니다.`)}
              {chartSVG([s.ship.id], 'emission', s.rows, [s.ship], s.from, s.to)}
              <details>
                <summary><UiText>{s.rowsTruncated
                  ? en ? `View displayed records (${n(s.rows.length, 0)} / ${n(s.totalRows, 0)})`
                    : `표시한 기록 보기 (${n(s.rows.length, 0)} / ${n(s.totalRows, 0)}건)`
                  : en ? 'View input records' : '계산에 사용한 기록 보기'}</UiText></summary>
                <div className={'tablewrap'}>
                  <table>
                    <thead>
                      <tr>
                        <th><UiText>{en ? 'Date' : '일자'}</UiText></th>
                        <th><UiText>{en ? 'Fuel (t)' : '연료 (t)'}</UiText></th>
                        <th><UiText>{en ? 'Factor' : '배출계수'}</UiText></th>
                        <th>{'CO₂ (t)'}</th>
                        <th>{'nm'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {s.rows.map((r, __index) => (
                        <React.Fragment key={__index}>
                          {
                            <tr>
                              <td>{r.date}</td>
                              <td>{r.fuel}</td>
                              <td>{r.factor}</td>
                              <td>{n(r.fuel * r.factor, 3)}</td>
                              <td>{r.distance}</td>
                            </tr>
                          }
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          </>
        ) : (
          notice(
            en ? 'No records for this period.' : '해당 기간의 운항 기록이 없습니다.',
            'warning',
          )
        )}
        <div className={'card pad mt'}>
          <div className={'sectiontitle'}>
            <h3><UiText>{en ? 'Rule comparison' : '규정 기준 비교'}</UiText></h3>
            {badge(
              en
                ? {
                    met: 'Entered criterion met',
                    unmet: 'Entered criterion not met',
                    unknown: 'Cannot determine',
                  }[c.status]
                : c.label,
              c.status === 'met' ? 'good' : 'warn',
            )}
          </div>
          {c.rule ? (
            <p className={'small'}>
              {c.rule.metric}
              {': '}
              {n(c.actual, 3)}
              {' / '}
              <UiText>{en ? 'Entered limit' : '입력 기준'}</UiText> {n(c.limit, 3)}
              <br />
              {c.rule.quote}
            </p>
          ) : (
            ''
          )}
          <p className={'small muted'}>
            {en
              ? 'A comparison against a user-verified criterion, not a complete regulatory compliance certification. Missing criteria or data produce no determination.'
              : c.reason}
          </p>
          {btn(en ? 'Review criterion' : '적용 기준 확인', 'criterion', 'sm mt')}
        </div>
        <p className={'footnote mt'}>{ciiText(s.cii, en)}</p>
      </section>
    );
  }
  function adminPage() {
    if (!isAdmin())
      return empty('관리자 권한이 필요해요', '사용자·승인·로그·백업은 관리자가 확인합니다.');
    const tab = state.adminTab;
    let content = '';
    if (tab === 'connection')
      content = (
        <div className={'status-grid'}>
          <div className={'card pad'}>
            <h2><UiText>{'작업공간 상태'}</UiText></h2>
            {[
              ['서버', '연결됨'],
              ['문서', state.docs.filter((d) => d.active).length + '개'],
              [
                '선박 / 운항 기록',
                state.ships.length + '척 / ' + state.operationRecords.length + '건',
              ],
              ['보고서', state.reports.length + '개'],
              ['AI 답변', state.health?.llmConfigured ? '설정됨' : '근거 문단 보기 사용'],
            ].map(([k, v], __index) => (
              <React.Fragment key={__index}>
                {
                  <div className={'status-line'}>
                    <span><UiText>{k}</UiText></span>
                    <strong>{v}</strong>
                  </div>
                }
              </React.Fragment>
            ))}
          </div>
          <div className={'card pad'}>
            <h2><UiText>{'운영 안내'}</UiText></h2>
            <p className={'muted mt'}>
              <UiText>{
                '문서와 운항 정보는 관리자만 등록·수정·삭제하며 저장 즉시 반영됩니다. 보고서는 승인 탭에서 검토합니다. 모든 업무 기능은 개인 계정으로 로그인한 뒤 사용합니다.'
              }</UiText>
            </p>
            {notice(
              '텍스트 PDF 검색·기록 관리·계산·초안·백업은 로컬에서 동작합니다. 선택적 외부 AI 답변에는 인터넷이 필요합니다.',
            )}
            <div className={'mt'}>{btn('정보 새로고침', 'refreshAll', '', 'refresh')}</div>
          </div>
        </div>
      );
    if (tab === 'users')
      content = (
        <>
          <div className={'sectiontitle'}>
            <h3>
              <UiText>{'사용자 '}</UiText>
              {state.users.length}
              <UiText>{'명'}</UiText>
            </h3>
            {btn('사용자 추가', 'newUser', 'primary', 'plus')}
          </div>
          <div className={'card tablewrap'}>
            <table>
              <thead>
                <tr>
                  <th><UiText>{'이름 / 아이디'}</UiText></th>
                  <th><UiText>{'권한'}</UiText></th>
                  <th><UiText>{'상태'}</UiText></th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {state.users.map((u, __index) => (
                  <React.Fragment key={__index}>
                    {
                      <tr>
                        <td>
                          {u.name}
                          <br />
                          <small>{u.username}</small>
                        </td>
                        <td><UiText>{roleName[u.role]}</UiText></td>
                        <td>{badge(u.active ? '활성' : '비활성', u.active ? 'good' : '')}</td>
                        <td>
                          {btn('수정', 'editUser', 'sm', '', {
                              'data-id': u.id,
                            })}
                        </td>
                      </tr>
                    }
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      );
    if (tab === 'approvals')
      content = (
        <>
          <div className={'sectiontitle'}>
            <h3><UiText>{'변경·보고서 검토'}</UiText></h3>
            {btn('새로고침', 'refreshAdmin', 'sm', 'refresh')}
          </div>
          <div className={'card'}>
            {state.changes.length
              ? state.changes.map((c, __index) => (
                  <React.Fragment key={__index}>
                    {
                      <div className={'docrow'}>
                        <div className={'docmain'}>
                          <h3>{changeLabel(c.kind, c.payload)}</h3>
                          <p className={'small muted'}>
                            {c.actor_name || '삭제된 사용자'}
                            {' · '}
                            {dateText(c.at)}
                          </p>
                          <p className={'small'}>{changeTarget(c)}</p>
                          {badge(statusName[c.status], c.status === 'pending' ? 'warn' : '')}
                        </div>
                        {btn('검토 내용', 'reviewChange', 'sm', '', {
                          'data-id': c.id,
                        })}
                      </div>
                    }
                  </React.Fragment>
                ))
              : empty(
                  '검토할 요청이 없어요',
                  '업무 담당자의 변경 요청과 보고서 검토 요청이 표시됩니다.',
                )}
          </div>
        </>
      );
    if (tab === 'logs') {
      const rows = state.logs.filter(
        (l) => state.logFilter === 'all' || l.category === state.logFilter,
      );
      content = (
        <>
          <div className={'controls'}>
            <UiControl as="select"
              className={'control'}
              aria-label={'로그 종류'}
              data-field={'logFilter'}
              value={state.logFilter}
              onChange={noop}
            >
              {options([
                ['all', '전체'],
                ['query', '질의'],
                ['change', '데이터 변경'],
                ['error', '오류'],
                ['tool', '계산'],
                ['auth', '로그인'],
                ['report', '보고서'],
                ['backup', '백업'],
                ['users', '사용자'],
              ])}
            </UiControl>
            {btn('새로고침', 'refreshAdmin', '', 'refresh')}
            <span className={'small muted'}><UiText>{'최근 500건'}</UiText></span>
          </div>
          <div className={'card tablewrap'}>
            <table>
              <thead>
                <tr>
                  <th><UiText>{'시각'}</UiText></th>
                  <th><UiText>{'수행자'}</UiText></th>
                  <th><UiText>{'동작'}</UiText></th>
                  <th><UiText>{'대상'}</UiText></th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.length ? (
                  rows.map((l, __index) => (
                    <React.Fragment key={__index}>
                      {
                        <tr>
                          <td>{dateText(l.at)}</td>
                          <td>{l.actor}</td>
                          <td>{l.action}</td>
                          <td className={'truncate-cell'}>{l.target}</td>
                          <td>
                            {btn('상세', 'logDetail', 'sm', '', {
                              'data-id': l.id,
                            })}
                          </td>
                        </tr>
                      }
                    </React.Fragment>
                  ))
                ) : (
                  <tr>
                    <td colSpan={'5'}><UiText>{'기록이 없습니다.'}</UiText></td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      );
    }
    if (tab === 'backup')
      content = (
        <>
          <div className={'sectiontitle'}>
            <div>
              <h3><UiText>{'전체 데이터 백업'}</UiText></h3>
              <p className={'small muted mt'}>
                <UiText>{'문서·원본 PDF·운항 기록·보고서·계정 및 권한·이력·시스템 설정 포함'}</UiText>
              </p>
            </div>
            <div className={'actions wrap'}>
              {btn('파일 가져오기', 'importBackup', '', 'database')}
              {btn('백업 만들기', 'createBackup', 'primary', 'save')}
            </div>
          </div>
          {notice(
            '복구는 현재 데이터를 선택한 시점으로 되돌립니다. 복구 직전 자동 백업을 만들고, 모든 계정은 다시 로그인합니다.',
          )}
          <div className={'controls mt'}>
            <label htmlFor={'auto-backup'}><UiText>{'자동 백업'}</UiText></label>
            <select
              id={'auto-backup'}
              className={'control'}
              data-backup-setting={'true'}
              value={state.autoBackup || 'daily'}
              onChange={noop}
            >
              {options([
                ['daily', '하루 1회'],
                ['off', '사용 안 함'],
              ])}
            </select>
            <span className={'small muted'}><UiText>{'서버 실행 중 · UTC 날짜 기준 · 1분마다 확인'}</UiText></span>
          </div>
          <div className={'card mt'}>
            {state.backups.length
              ? state.backups.map((b, __index) => (
                  <React.Fragment key={__index}>
                    {
                      <div className={'docrow'}>
                        <div className={'docmain'}>
                          <h3>{b.label}</h3>
                          <p className={'small muted'}>
                            {dateText(b.createdAt)}
                            <UiText>{' · 형식 v'}</UiText>
                            {b.version}
                          </p>
                          <p className={'small'}>
                            <UiText>{'문서 '}</UiText>
                            {b.counts.documents}
                            <UiText>{' · 운항 '}</UiText>
                            {b.counts.operations}
                            <UiText>{' · 보고서 '}</UiText>
                            {b.counts.reports}
                          </p>
                        </div>
                        <div className={'actions'}>
                          {btn('파일 보관', 'downloadBackup', 'sm', 'download', {
                            'data-id': b.id,
                          })}
                          {btn('복구', 'restoreBackup', 'sm', 'refresh', {
                            'data-id': b.id,
                          })}
                        </div>
                      </div>
                    }
                  </React.Fragment>
                ))
              : empty('아직 백업이 없어요', '중요한 데이터를 등록한 뒤 백업을 만들어 주세요.')}
          </div>
          <p className={'footnote mt'}>
            <UiText>{
              '백업에는 계정 정보와 문서가 포함됩니다. 관리자만 내려받을 수 있습니다. 외부 AI 비밀키(.env)는 백업에서 제외되며 서버에서 별도로 보관합니다.'
            }</UiText>
          </p>
        </>
      );
    return (
      <>
        {head('관리', '사용자와 변경 내역을 확인하고 데이터를 보관하세요.')}
        {
          <>
            <div className={'admin-tabs'}>
              {[
                ['connection', '연결 상태'],
                ['users', '사용자·권한'],
                ['approvals', '승인'],
                ['logs', '시스템 로그'],
                ['backup', '백업·복구'],
              ].map(([id, l], __index) => (
                <React.Fragment key={__index}>
                  {btn(l, 'adminTab', tab === id ? 'primary' : '', '', {
                    'data-id': id,
                  })}
                </React.Fragment>
              ))}
            </div>
            {state.adminError ? notice(state.adminError, 'warning') : ''}
            {state.adminLoading ? <p role={'status'}><UiText>{'불러오는 중…'}</UiText></p> : content}
          </>
        }
      </>
    );
  }
  function changeLabel(kind, payload) {
    if (kind === 'document.save' && payload?.mode === 'metadata') return '문서 정보 수정';
    return (
      {
        'document.save': '문서 등록·개정',
        'document.delete': '문서 삭제',
        'ship.save': '선박 등록·수정',
        'operation.save': '운항 기록 등록·수정',
        'operation.import': '운항 기록 일괄 등록',
        'operation.delete': '운항 기록 삭제',
        'report.approve': '보고서 확정 검토',
      }[kind] || kind
    );
  }
  function changeTarget(c) {
    const p = c.payload;
    return (
      p.document?.title ||
      (p.document?.id && state.docs.find((d) => d.logical_id === p.document.id)?.title) ||
      p.document?.id ||
      p.title ||
      p.name ||
      (p.rows ? p.rows.length + '개 기록' : p.date || p.id || '')
    );
  }
  return {
    roleName,
    statusName,
    authPage,
    ciiText,
    operationAnswer,
    adminPage,
    changeLabel,
    changeTarget,
  };
}
