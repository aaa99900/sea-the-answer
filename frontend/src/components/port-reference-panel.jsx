'use client';
import {UiText,UiControl} from './ui-language';
import React, { useEffect, useRef, useState } from 'react';
import { useWorkspace } from '../workspace/provider';
import { berthStates, checkLabels, checkStates, metres, referenceReason, referenceTime } from '../lib/port-reference';
import { NavigationReadiness, OperationalChecks } from './navigation-readiness';
import { NavigationContext, HistoricalChecks } from './navigation-context';
import OfficialGuidance from './navigation-guidance';

export default function PortReferencePanel() {
  const { workspace } = useWorkspace(), state = workspace.state;
  const ship = state.ships.find(s => s.id === state.ship);
  // Re-mount on an account/ship/version change. An old in-flight response cannot
  // render for the next selection, even in the render before effects run.
  const scope = JSON.stringify([state.ready, state.user?.id, state.user?.version, state.user?.role, ship?.id, ship?.version, ship?.imo]);
  return <ReferenceForm key={scope} workspace={workspace} ship={ship} ready={state.ready} />;
}

function ReferenceForm({ workspace, ship, ready }) {
  const [expanded, setExpanded] = useState(false), [catalog, setCatalog] = useState(null);
  const [port, setPort] = useState(''), [berth, setBerth] = useState('');
  const [answer, setAnswer] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [wind, setWind] = useState(''), [tugs, setTugs] = useState(''), [ukc, setUkc] = useState('');
  const generation = useRef(0), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; ++generation.current; }; }, []);
  useEffect(() => {
    if (!ready || !expanded) return;
    let active = true;
    ++generation.current;
    setError(''); setAnswer(null); setBusy(false); setCatalog(null);
    workspace.api.request('/api/operations/port-references').then(data => {
      if (!active) return;
      setCatalog(data);
      setPort(old => data.ports.some(p => p.port_id === old) ? old : data.ports.length === 1 ? data.ports[0].port_id : '');
      setBerth('');
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [ready, expanded, workspace]);
  function resetSelection(update) {
    ++generation.current; setAnswer(null); setError(''); setBusy(false); update();
  }
  async function submit(e) {
    e.preventDefault(); e.stopPropagation();
    if (!ship || ship.sample || !port || busy) return;
    const ticket = ++generation.current;
    setAnswer(null); setError(''); setBusy(true);
    try {
      const scenario = { ...(wind!=='' ? {wind_m_s:wind} : {}), ...(tugs!=='' ? {available_tugs:Number(tugs)} : {}),
        ...(ukc!=='' ? {ukc_m:ukc} : {}) };
      const data = await workspace.api.request('/api/operations/port-reference-screen', {
        ship: ship.id, port_id: port, ...(berth ? { berth_id: berth } : {}),
        ...(Object.keys(scenario).length ? {scenario} : {}),
      });
      if (mounted.current && ticket === generation.current && data.context?.ship === ship.id
          && data.context.ship_version === ship.version) setAnswer(data);
      else if (mounted.current && ticket === generation.current) setError('선박 정보가 변경되었습니다. 화면을 새로고침한 뒤 다시 조회해 주세요.');
    } catch (e) { if (mounted.current && ticket === generation.current) setError(e.message); }
    finally { if (mounted.current && ticket === generation.current) setBusy(false); }
  }
  const selected = catalog?.ports.find(p => p.port_id === port), result = answer?.result;
  return <details className="card pad mt port-reference-panel" onToggle={e => { if (e.target === e.currentTarget) setExpanded(e.currentTarget.open); }}
    onInput={e => e.stopPropagation()} onChange={e => e.stopPropagation()}>
    <summary><UiText>{"항구·선석 참조 비교"}</UiText></summary>
    <p className="small"><UiText>{"선택한 앱 선박의 AIS 신고값과 선석 공개 수치를 부분 비교합니다. 상단 기간 필터와 별개로 수집본 시점을 사용하며, 입항 가능 여부는 판정하지 않습니다."}</UiText></p>
    <p><UiText>{"선택 선박:"}</UiText><strong>{ship?.name || '운항 화면 위에서 선박을 선택해 주세요'}</strong><UiText>{ship?.sample ? ' (가상 예시)' : ''}</UiText></p>
    {catalog && <>
      <p className="small muted"><UiText>{"연결된 AIS"}</UiText>{catalog.ais_observation_count}<UiText>{"건 ·"}</UiText>{catalog.ais_unique_vessels ?? catalog.ais_observation_count}<UiText>{"척 · 확보된 수신권역 자료이며 전 세계 선박을 포괄하지 않습니다."}</UiText><br />
        {catalog.ais_source_counts && <><UiText>{"출처별 기록:"}</UiText>{Object.entries(catalog.ais_source_counts).map(([id,n])=>`${id==='ais_no'?'노르웨이 Kystverket':id==='ais'?'핀란드 Fintraffic':id} ${n}건`).join(' · ')}<br /></>}<UiText>{"제공 항구"}</UiText>{catalog.ports.length}<UiText>{"곳 · 자료 생성:"}</UiText>{referenceTime(catalog.generated_at)}<UiText>{"· 항구 원문의 적용일은 미확인입니다."}</UiText></p>
      {(catalog.freshness?.ais_capture_issue || selected?.capture_issue || catalog.freshness?.catalog_issue) &&
        <p className="notice warning">{[catalog.freshness.ais_capture_issue, selected?.capture_issue, catalog.freshness.catalog_issue].filter(Boolean).map(referenceReason).join(' · ')}</p>}
      <form onSubmit={submit}>
        <div className="controls">
          <label className="field"><UiText>{"항구"}</UiText><UiControl as="select" aria-label="참조 항구" value={port} onChange={e => resetSelection(() => { setPort(e.target.value); setBerth(''); })}>
            <option value=""><UiText>{"항구 선택"}</UiText></option>{catalog.ports.map(p => <option key={p.port_id} value={p.port_id}>{p.name} · {p.unlocode} · {p.port_id}</option>)}
          </UiControl></label>
          <label className="field"><UiText>{"선석"}</UiText><UiControl as="select" aria-label="참조 선석" value={berth} disabled={!selected} onChange={e => resetSelection(() => setBerth(e.target.value))}>
            <option value=""><UiText>{"전체 선석"}</UiText></option>{selected?.berths.map(b => <option key={b.berth_id} value={b.berth_id}>{b.label}<UiText>{b.issues.includes('DUPLICATE_BERTH_VARIANTS_REQUIRE_REVIEW') ? ' (조건 중복)' : ''}</UiText></option>)}
          </UiControl></label>
          <button type="submit" className="btn primary" disabled={!ready || !ship || !!ship.sample || !port || busy}><UiText>{busy ? '비교 중…' : '선석 참조 비교'}</UiText></button>
        </div>
        <details className="mt"><summary><UiText>{"가정 조건 비교 (선택)"}</UiText></summary>
          <p className="small"><UiText>{"입항 조건을 이해하기 위한 가정값입니다. 미입력은 미확인으로 두며, 실측·기상 관측·예선 확보 증빙이나 입항 승인으로 사용하지 않습니다."}</UiText></p>
          <div className="controls">
            <label className="field"><UiText>{"가정 풍속 (m/s)"}</UiText><UiControl as="input" aria-label="가정 풍속" type="number" min="0" max="100" step="0.1" value={wind} onChange={e=>resetSelection(()=>setWind(e.target.value))} /></label>
            <label className="field"><UiText>{"가정 예선 수 (척)"}</UiText><UiControl as="input" aria-label="가정 예선 수" type="number" min="0" max="20" step="1" value={tugs} onChange={e=>resetSelection(()=>setTugs(e.target.value))} /></label>
            <label className="field"><UiText>{"가정 선저 여유 (m)"}</UiText><UiControl as="input" aria-label="가정 선저 여유" type="number" min="0" max="20" step="0.01" value={ukc} onChange={e=>resetSelection(()=>setUkc(e.target.value))} /></label>
          </div>
        </details>
      </form>
      {selected && <p className="small"><UiText>{"항구 자료 수집:"}</UiText>{referenceTime(selected.retrieved_at)}<br />
        <UiText>{selected.source_id === 'helsinki_berths' ? '크루즈 선석 자료입니다. 선종·서비스 적합성은 별도 확인해야 합니다.' :
          selected.source_id === 'aalborg_berths' ? '2026 Oil Terminals의 6개 선석만 포함합니다. 최신 측심·도선 제한·터미널 확인이 필요합니다.' :
          '공개된 선석 자료의 부분 비교입니다. 화물·터미널 적합성은 별도 확인해야 합니다.'}</UiText></p>}
    </>}
    {expanded && !catalog && !error && <p role="status"><UiText>{"참조 자료 목록을 불러오는 중…"}</UiText></p>}
    {ship?.sample && <p className="notice warning"><UiText>{"가상 예시 선박은 실제 항구 참조 비교에 사용할 수 없습니다."}</UiText></p>}
    {error && <p role="alert" className="notice warning">{error}</p>}
    {answer && <div aria-live="polite" data-port-reference-result>
      <p className="notice warning">{answer.notice}</p>
      {result && <>
        <p>IMO {answer.context.imo_number} · {result.port_name}<UiText>{"· 비교 시각"}</UiText>{referenceTime(result.assessed_at)}</p>
        <p className="small"><UiText>{"AIS 기록 수신:"}</UiText>{referenceTime(result.observation?.metadata_received_at)}<UiText>{". 이 시각은 흘수 측정 시각이 아닙니다."}</UiText></p>
        {result.ship_issues.length > 0 && <p className="notice warning">{result.ship_issues.map(referenceReason).join(' · ')}</p>}
        {result.observation?.position_reported_at && <p className="small"><UiText>{"위치 보고:"}</UiText>{referenceTime(result.observation.position_reported_at)}<UiText>{"· 제원·흘수 신고/측정 시각은 미확인입니다."}</UiText></p>}
        <NavigationReadiness value={result.readiness} />
        <NavigationContext registered={result.static_reference} environment={result.environment} />
        <OfficialGuidance value={result.official_guidance} />
        {answer.latest_record_draught && <p className="notice"><UiText>{"최근 흘수 입력 기록:"}</UiText>{answer.latest_record_draught.date} · {metres(answer.latest_record_draught.draught_m)}
          <UiText>{answer.latest_record_draught.sample ? ' (가상 예시 기록)' : ''}</UiText>. {answer.latest_record_draught.notice}<UiText>{"이 비교에는 사용하지 않았습니다."}</UiText></p>}
        {result.berths.map(b => <section className="mt" key={b.berth_id}>
          <h3><UiText>{"선석"}</UiText>{b.berth_id.split(':BERTH:')[1]} · <UiText>{berthStates[b.status] || b.status}</UiText></h3>
          <div className="tablewrap"><table><thead><tr><th><UiText>{"항목"}</UiText></th><th><UiText>{"AIS 신고값"}</UiText></th><th><UiText>{"선석 공개값"}</UiText></th><th><UiText>{"비교"}</UiText></th><th><UiText>{"확인할 사유"}</UiText></th></tr></thead>
            <tbody>{b.checks.map(c => <tr key={c.kind}><th><UiText>{checkLabels[c.kind] || c.kind}</UiText></th><td>{metres(c.vessel_reported_m)}</td><td>{metres(c.berth_listed_m)}</td>
              <td><UiText>{checkStates[c.status] || c.status}</UiText></td><td>{c.reasons.map(referenceReason).join(' · ') || '추가 조건 별도 확인'}</td></tr>)}</tbody></table></div>
          <OperationalChecks checks={b.operational_checks} />
          <HistoricalChecks checks={b.static_reference_checks} />
          <details><summary><UiText>{"원문 조건 확인 · 자동 판정에 미반영"}</UiText></summary>{b.conditions.map((text, i) => <pre key={i} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{text}</pre>)}</details>
        </section>)}
        <p className="small"><UiText>{"현재 선박 치수·흘수, 항만 최신 공고와 선석 승인, 접근 수로·조석·수밀도·선저 여유수심·날씨, 수면 위 높이·화물·예선·도선 조건을 별도로 확인해야 합니다."}</UiText></p>
        <details className="mt"><summary><UiText>{"출처와 수집 시각"}</UiText></summary>{result.sources.map(s => <p key={s.id}>
          <a href={s.url} target="_blank" rel="noreferrer">{{ais: 'Fintraffic AIS', berths: 'Gothenburg 항만 선석 자료', helsinki_berths: 'Helsinki 항만 크루즈 선석 자료', schema: 'AIS 공식 API 명세',
            ais_no:'Kystverket · 노르웨이 공개 AIS',schema_no:'Kystdatahuset 공식 API 명세',aalborg_berths:'Aalborg 항만청 · 2026 Oil Terminals',
            norway_static:'Kystdatahuset · 과거 등록 제원',schema_no_static:'등록 제원 공식 명세',smhi_wind_vinga:'SMHI · Vinga 풍속',
            smhi_wind_gothenburg:'SMHI · Göteborg 풍속',smhi_water_gothenburg:'SMHI · Göteborg-Tångudden 수위'}[s.id] || s.id}</a>
          {' · '}{referenceTime(s.retrieved_at)}<br /><small>{s.attribution}{s.license_url && <> · <a href={s.license_url} target="_blank" rel="noreferrer"><UiText>{"이용 조건"}</UiText></a></>}</small>
        </p>)}</details>
      </>}
    </div>}
  </details>;
}
