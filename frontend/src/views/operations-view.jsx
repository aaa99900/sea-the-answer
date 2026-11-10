import {UiText} from '../components/ui-language';
import {UiControl} from '../components/ui-language';
import React from 'react';
import SkillsPanel from '../components/skills-panel';
import PortReferencePanel from '../components/port-reference-panel';
import * as helpers from '../components/common';
export function createOperationsViews(model, views) {
  const noop = () => {};
  const { state, currentShip, records, metrics, canWrite, isAdmin } = model;
  const { esc, I, btn, badge, n, options, head, notice, empty, stat } = helpers;
  const metricLabels = {
    fuel: ['연료 소비량', 't'],
    emission: ['CO₂ 배출량', 't CO₂'],
    distance: ['운항거리', 'nm'],
    speed: ['속력', 'kn'],
    intensity: ['단순 탄소집약도', 'gCO₂/(DWT·nm)'],
  };
  function valueOf(r, key, ship) {
    return key === 'emission'
      ? r.fuel * r.factor
      : key === 'intensity'
        ? r.distance > 0 && ship?.dwt > 0
          ? (r.fuel * r.factor * 1e6) / (ship.dwt * r.distance)
          : null
        : r[key];
  }
  function chartSVG(
    ids = [state.ship],
    metric = state.metric,
    source = state.operationRecords,
    vessels = state.ships,
    from = state.from,
    to = state.to,
  ) {
    const lists = ids.map((id) =>
        source.filter((r) => r.ship === id && r.date >= from && r.date <= to),
      ),
      dates = [...new Set(lists.flat().map((r) => r.date))].sort();
    if (!dates.length)
      return empty('이 기간의 기록이 없어요', '선박과 기간을 확인하거나 기록을 등록해 주세요.');
    const values = lists
        .flatMap((rs, i) =>
          rs.map((r) =>
            valueOf(
              r,
              metric,
              vessels.find((s) => s.id === ids[i]),
            ),
          ),
        )
        .filter((v) => v !== null),
      max = Math.max(1, ...values) * 1.1,
      W = 900,
      H = 220,
      left = 70,
      right = 30,
      top = 15,
      bottom = 35,
      x = (i) => left + (i * (W - left - right)) / Math.max(1, dates.length - 1),
      y = (v) => H - bottom - (v / max) * (H - top - bottom);
    return (
      <UiControl as="svg"
        className={'chart'}
        viewBox={'0 0 ' + W + ' ' + H}
        role={'img'}
        aria-label={metricLabels[metric][0] + ' 추이. 상세 값은 아래 표에서 확인할 수 있습니다.'}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((t, __index) => (
          <React.Fragment key={__index}>
            {
              <>
                <line
                  x1={left}
                  y1={y(t * max)}
                  x2={W - right}
                  y2={y(t * max)}
                  stroke={'#e7eef1'}
                ></line>
                <text
                  x={'60'}
                  y={y(t * max) + 4}
                  textAnchor={'end'}
                  fontSize={'11'}
                  fill={'#7a8c98'}
                >
                  {n(t * max, max > 100 ? 0 : 1)}
                </text>
              </>
            }
          </React.Fragment>
        ))}
        {dates
          .filter((_, i) => i % Math.max(1, Math.ceil(dates.length / 8)) === 0)
          .map((d, __index) => (
            <React.Fragment key={__index}>
              {
                <text
                  x={x(dates.indexOf(d))}
                  y={H - 7}
                  textAnchor={'middle'}
                  fill={'#7a8c98'}
                  fontSize={'11'}
                >
                  {d.slice(5)}
                </text>
              }
            </React.Fragment>
          ))}
        {lists.map((list, ix) => {
          const color = ['#167d83', '#8e9fb7', '#c89962'][ix % 3],
            ship = vessels.find((s) => s.id === ids[ix]),
            valid = list.filter((r) => valueOf(r, metric, ship) !== null);
          return (
            <React.Fragment key={ix}>
              {
                <>
                  <polyline
                    fill={'none'}
                    stroke={color}
                    strokeWidth={'2.7'}
                    points={valid
                      .map((r) => [x(dates.indexOf(r.date)), y(valueOf(r, metric, ship))].join(','))
                      .join(' ')}
                  ></polyline>
                  {valid.map((r, __index) => (
                    <React.Fragment key={__index}>
                      {
                        <circle
                          cx={x(dates.indexOf(r.date))}
                          cy={y(valueOf(r, metric, ship))}
                          r={'3'}
                          fill={color}
                        >
                          <title>
                            {ship?.name} {r.date}
                            {': '}
                            {n(valueOf(r, metric, ship), 3)}
                          </title>
                        </circle>
                      }
                    </React.Fragment>
                  ))}
                </>
              }
            </React.Fragment>
          );
        })}
      </UiControl>
    );
  }
  function operationTable(rows, editable = false) {
    return (
      <div className={'tablewrap'}>
        <table>
          <thead>
            <tr>
              <th><UiText>{'선박 / 일자'}</UiText></th>
              <th><UiText>{'연료 (t)'}</UiText></th>
              <th>{'CO₂ (t)'}</th>
              <th><UiText>{'거리 (nm)'}</UiText></th>
              <th><UiText>{'속력 (kn)'}</UiText></th>
              <th><UiText>{'확인'}</UiText></th>
              {editable ? <th><UiText>{'관리'}</UiText></th> : ''}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, __index) => (
              <React.Fragment key={__index}>
                {
                  <tr>
                    <td>
                      {state.ships.find((s) => s.id === r.ship)?.name || r.ship}
                      <br />
                      <small>{r.date}</small>
                    </td>
                    <td>{n(r.fuel)}</td>
                    <td>{n(r.fuel * r.factor)}</td>
                    <td>{n(r.distance)}</td>
                    <td>{n(r.speed)}</td>
                    <td>
                      {badge(
                        r.sample ? '가상 예시' : r.note ? '점검 기록' : '등록 기록',
                        r.sample ? 'warn' : '',
                      )}
                      <button className={'tabletitle'} data-action={'recordDetail'} data-id={r.id}>
                        <UiText>{'상세'}</UiText>
                      </button>
                    </td>
                    {editable ? (
                      <td>
                        <div className={'actions'}>
                          {btn('수정', 'editRecord', 'sm', '', {
                            'data-id': r.id,
                          })}
                          {btn('삭제', 'deleteRecord', 'danger-outline sm', '', {
                            'data-id': r.id,
                          })}
                        </div>
                      </td>
                    ) : (
                      ''
                    )}
                  </tr>
                }
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  function contextControls(compact = false) {
    return (
      <div className={'controls ' + (compact ? 'context-controls' : '')}>
        <div className={'field'}>
          <label htmlFor={'ship'}><UiText>{'대상 선박'}</UiText></label>
          <select id={'ship'} data-field={'ship'} value={state.ship} onChange={noop}>
            {options([
              ['', '선박 선택'],
              ...state.ships.map((s) => [s.id, <>{s.name}{s.sample && <UiText> · 예시</UiText>}</>]),
            ])}
          </select>
        </div>
        <div className={'field'}>
          <label htmlFor={'from'}><UiText>{'시작일'}</UiText></label>
          <input id={'from'} type={'date'} data-field={'from'} value={state.from} onChange={noop} />
        </div>
        <div className={'field'}>
          <label htmlFor={'to'}><UiText>{'종료일'}</UiText></label>
          <input id={'to'} type={'date'} data-field={'to'} value={state.to} onChange={noop} />
        </div>
      </div>
    );
  }
  function overview() {
    const m = metrics(),
      s = currentShip(),
      rows = records(),
      last = rows.at(-1);
    return (
      <>
        <div className={'grid4'}>
          {stat('연료 소비량', n(m.fuel), 't', <>{m.count}<UiText>개 기록 합계</UiText></>)}
          {stat('CO₂ 배출량', n(m.co2), 't', '기록별 배출계수 적용')}
          {stat('운항거리', n(m.distance), 'nm', '선택 기간 합계', 'ship')}
          {stat('점검 기록', m.anomalies, '건', '점검 사유가 입력된 기록', 'alert')}
        </div>
        <div className={'card ship-strip'}>
          <div>
            <h3>
              {s.name} <UiText>{s.sample ? badge('가상 예시', 'warn') : ''}</UiText>
            </h3>
            <span className={'muted small'}>
              {s.type || ''}
              {' · DWT '}
              {n(s.dwt, 0)}
              {' t'}
            </span>
          </div>
          <div className={'small muted'}>
            <UiText>{'최근 기록 '}</UiText>
            {last?.date || <UiText>없음</UiText>}
            <br />
            <UiText>{'위치 '}</UiText>
            {last?.position || <UiText>미입력</UiText>}
            <UiText>{' · 속력 '}</UiText>
            {last ? n(last.speed) + ' kn' : '—'}
          </div>
          <UiText>{isAdmin()
            ? btn('선박 정보', 'editShip', 'sm', '', {
                'data-id': s.id,
              })
            : ''}</UiText>
        </div>
        {analysisChart([state.ship])}
        <div className={'sectiontitle mt'}>
          <h3>
            <UiText>{'운항 기록 '}</UiText>
            {rows.length}
            <UiText>{'건'}</UiText>
          </h3>
          {btn('CSV 내보내기', 'exportRecords', 'ghost sm', 'download')}
        </div>
        <div className={'card'}>
          <UiText>{rows.length
            ? operationTable(rows, isAdmin())
            : empty('등록된 기록이 없어요', '선택한 선박·기간의 기록을 등록해 주세요.')}</UiText>
        </div>
        {timeTool()}
      </>
    );
  }
  function analysisChart(ids) {
    return (
      <div className={'card pad'}>
        <div className={'sectiontitle'}>
          <h3>
            <UiText>{metricLabels[state.metric][0]}</UiText>
            <UiText>{' 추이'}</UiText>
          </h3>
          <UiControl as="select"
            className={'control'}
            aria-label={'표시 지표'}
            data-field={'metric'}
            value={state.metric}
            onChange={noop}
          >
            {options(Object.entries(metricLabels).map(([k, v]) => [k, v[0]]))}
          </UiControl>
        </div>
        {chartSVG(ids)}
        <p className={'small muted'}>
          <UiText>{'단위: '}</UiText>
          {metricLabels[state.metric][1]}
          <UiText>{' · CII 등급을 의미하지 않습니다.'}</UiText>
        </p>
      </div>
    );
  }
  function analysis() {
    const ids = state.compare.length ? state.compare : [state.ship];
    return (
      <>
        <div className={'compare-controls mb'}>
          {state.ships.map((s, __index) => (
            <React.Fragment key={__index}>
              {
                <label className={'checkline'}>
                  <input
                    type={'checkbox'}
                    data-compare={s.id}
                    {...(ids.includes(s.id)
                      ? {
                          checked: true,
                        }
                      : {})}
                    onChange={noop}
                  />
                  {s.name}
                </label>
              }
            </React.Fragment>
          ))}
        </div>
        {analysisChart(ids)}
        <div className={'legend mt'}>
          {ids.map((id, i) => (
            <React.Fragment key={i}>
              {
                <span
                  style={{
                    '--legend-color': ['#167d83', '#8e9fb7', '#c89962'][i % 3],
                  }}
                >
                  {state.ships.find((s) => s.id === id)?.name}
                </span>
              }
            </React.Fragment>
          ))}
        </div>
        <div className={'card mt'}>{operationTable(ids.flatMap((id) => records(id)))}</div>
      </>
    );
  }
  function calculation() {
    const c = state.calc,
      v = state.calcInputs;
    return (
      <div className={'grid2'}>
        <form id={'calcForm'} className={'card pad'}>
          <div className={'sectiontitle'}>
            <h3><UiText>{'계산 입력값'}</UiText></h3>
            {badge('서버 계산', 'teal')}
          </div>
          {btn('선택 기록에서 가져오기', 'useSampleInputs', 'sm mb', 'database')}
          <div className={'grid2 mb'}>
            {[
              ['fuel', '연료 소비량 (t)', 0, 1e7],
              ['factor', '배출계수 (t CO₂/t)', 0.000001, 10],
              ['dwt', '재화중량 (DWT, t)', 0.000001, 1e7],
              ['distance', '운항거리 (nm)', 0.000001, 1e7],
            ].map(([id, l, min, max], __index) => (
              <React.Fragment key={__index}>
                {
                  <div className={'field'}>
                    <label htmlFor={id}><UiText>{l}</UiText></label>
                    <input
                      id={id}
                      name={id}
                      data-calc={id}
                      type={'number'}
                      min={min}
                      max={max}
                      step={'any'}
                      value={v[id]}
                      required
                      onChange={noop}
                    />
                  </div>
                }
              </React.Fragment>
            ))}
          </div>
          <div className={'inline-error mb'} role={'alert'}>
            {state.calcError}
          </div>
          <button
            className={'btn primary'}
            {...(state.calcBusy
              ? {
                  disabled: true,
                }
              : {})}
          >
            <UiText>{state.calcBusy ? '계산 중…' : '지표 계산'}</UiText>
          </button>
        </form>
        <div>
          <div className={'calculation-result'} aria-live={'polite'}>
            <h3><UiText>{'계산 결과'}</UiText></h3>
            {c ? (
              <>
                <div className={'mt'}><UiText>{'CO₂ 배출량'}</UiText></div>
                <div className={'stat-value'}>
                  {n(c.emission, 3)} <small>{'t CO₂'}</small>
                </div>
                <div className={'divider'}></div>
                <div><UiText>{'단순 탄소집약도'}</UiText></div>
                <div className={'stat-value'}>
                  {n(c.intensity, 3)} <small>{'gCO₂/(DWT·nm)'}</small>
                </div>
                <p className={'formula'}>
                  {c.formula}
                  <br />
                  <UiText>{'계산 버전: '}</UiText>
                  {c.version}
                </p>
              </>
            ) : (
              <p className={'mt'}><UiText>{'입력값을 확인하고 계산을 실행하세요.'}</UiText></p>
            )}
          </div>
          <div className={'card pad mt'}>
            <h3>
              {'CII '}
              {badge('산출 불가', 'warn')}
            </h3>
            <p className={'small muted mt'}>
              <UiText>{
                '공식 CII 산식·선종별 용량 기준·보정 및 제외 조건·적용 연도 검증이 필요합니다. 위 단순 집약도를 CII 등급으로 사용하지 마세요.'
              }</UiText>
            </p>
          </div>
          <UiText>{c && canWrite() ? btn('계산 결과를 보고서에 담기', 'calcReport', 'mt', 'edit') : ''}</UiText>
        </div>
      </div>
    );
  }
  function timeTool() {
    const t = state.timeInputs,
      r = state.timeResult;
    return (
      <details className={'card pad time-tool'}>
        <summary><UiText>{'항해 시각 계산'}</UiText></summary>
        <form id={'timeForm'}>
          <div className={'grid2'}>
            {[
              ['start', '시작 UTC', 'datetime-local'],
              ['end', '종료 UTC', 'datetime-local'],
              ['before', '시작 오프셋 (분)', 'number'],
              ['after', '종료 오프셋 (분)', 'number'],
            ].map(([id, l, type], __index) => (
              <React.Fragment key={__index}>
                {
                  <div className={'field'}>
                    <label htmlFor={'time-' + id}><UiText>{l}</UiText></label>
                    <input
                      id={'time-' + id}
                      data-time={id}
                      type={type}
                      value={t[id]}
                      required
                      onChange={noop}
                    />
                  </div>
                }
              </React.Fragment>
            ))}
          </div>
          <p className={'inline-error'} role={'alert'}>
            {state.timeError}
          </p>
          <button
            className={'btn'}
            {...(state.timeBusy
              ? {
                  disabled: true,
                }
              : {})}
          >
            <UiText>{'시간 계산'}</UiText>
          </button>
        </form>
        {r ? (
          <p className={'mt'}>
            <UiText>{'실제 경과 '}</UiText>
            {n(r.elapsedHours)}
            <UiText>{'시간 · 선내 시계 차이 '}</UiText>
            {n(r.clockHours)}
            <UiText>{'시간'}</UiText>
          </p>
        ) : (
          ''
        )}
      </details>
    );
  }
  function operationsPage() {
    return (
      <>
        {
          <>
            {
              <>
                {head(
                  '운항 정보',
                  '기록을 관리하고, 변화를 비교하고, 지표를 계산하세요.',
                  isAdmin() ? (
                    <>
                      {
                        <>
                          {btn('선박 등록', 'newShip', '', 'ship')}
                          {btn('CSV 불러오기', 'importOperations', '', 'database')}
                        </>
                      }
                      {btn('기록 등록', 'newRecord', 'primary', 'plus')}
                    </>
                  ) : (
                    ''
                  ),
                )}
                {contextControls()}
              </>
            }
            {
              <div className={'tabs'}>
                {[
                  ['overview', '현황'],
                  ['analysis', '분석'],
                  ['calculation', '지표 계산'],
                ].map(([id, l], __index) => (
                  <React.Fragment key={__index}>
                    {
                      <button className={'tab ' + (state.tab === id ? 'active' : '')} data-tab={id}>
                        <UiText>{l}</UiText>
                      </button>
                    }
                  </React.Fragment>
                ))}
              </div>
            }
          </>
        }
        {state.tab !== 'calculation' && !state.ships.length
          ? empty(
              '첫 선박을 등록해 주세요',
              '새로 등록한 기록은 PostgreSQL에 저장됩니다.',
              isAdmin() ? (
                <>
                  {btn('선박 등록', 'newShip', 'primary')}
                  <UiText>{isAdmin() ? btn('가상 예시로 둘러보기', 'seedExample', 'mt') : ''}</UiText>
                </>
              ) : (
                '관리자에게 선박 등록을 요청해 주세요.'
              ),
            )
          : {
              overview,
              analysis,
              calculation,
            }[state.tab]()}
        <PortReferencePanel />
        <SkillsPanel group="operations" />
      </>
    );
  }
  return {
    metricLabels,
    valueOf,
    chartSVG,
    operationTable,
    contextControls,
    operationsPage,
  };
}
