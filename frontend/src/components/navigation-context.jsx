import {UiText} from './ui-language';
import React from 'react';
import { checkLabels, metres, referenceTime } from '../lib/port-reference';

const states = {reference_available:'일치하는 참고 치수 있음',unavailable:'연결된 참고값 없음',
  period_unknown:'등록 유효기간 미확인',identity_conflict:'등록 식별자 충돌',insufficient_reference:'참고 치수 부족/충돌'};
const ages = {within_age_window:'2시간 이내',stale:'2시간 초과 · 오래된 수집본',time_in_future:'시각 확인 필요'};
const quality = {checked:'검수·승인',suspect_or_aggregated:'의심 또는 집계값',unchecked:'미검수',unknown:'품질 미확인'};

export function NavigationContext({ registered, environment }) {
  return <>
    {registered?.candidate_count > 0 && <section className="card pad mt" data-static-reference>
      <h3><UiText>{"과거 등록 제원 참고"}</UiText></h3>
      <p><UiText>{states[registered.status] || registered.status}</UiText>{' '}<UiText>{"· 요청 기간 끝"}</UiText>{' '}{referenceTime(registered.as_of)}{' '}<UiText>{"직전 기준"}</UiText></p>
      <p><UiText>{"길이"}</UiText>{' '}{metres(registered.length_m)}{' '}<UiText>{"· 폭"}</UiText>{' '}{metres(registered.beam_m)}{' '}<UiText>{"· 기록 후보"}</UiText>{' '}{registered.candidate_count}<UiText>{"건"}</UiText></p>
      <p className="notice warning" style={{display:'block'}}>{registered.notice}</p>
      <details><summary><UiText>{"등록 후보·유효기간 확인"}</UiText></summary>
        {registered.candidates?.map((r,i)=><p key={i}><UiText>{"등록 IMO"}</UiText>{' '}{r.registry_imo_number || '미확인'} · MMSI {r.mmsi}<br /><UiText>{"길이"}</UiText>{' '}{metres(r.reference_length_m)}{' '}<UiText>{"· 폭"}</UiText>{' '}{metres(r.reference_beam_m)}{' '}<UiText>{"· 등록 흘수"}</UiText>{' '}{metres(r.registry_draught_m)}<br /><UiText>{"등록 유효 시작"}</UiText>{' '}{referenceTime(r.valid_from)}{' '}<UiText>{"/ 종료"}</UiText>{' '}{referenceTime(r.valid_to)}<br />
          <small>{r.issues?.join(' · ')} · {r.source_ref?.locator}</small></p>)}
        {registered.candidate_count>20 && <p><UiText>{"후보 중 처음 20건만 표시합니다. 참고 치수는 전체 후보를 검사한 결과입니다."}</UiText></p>}
      </details>
    </section>}
    {environment?.observations?.length>0 && <section className="card pad mt" data-environment-context>
      <h3><UiText>{"Gothenburg 지역 관측 수집본"}</UiText></h3>
      <p className="notice warning" style={{display:'block'}}>{environment.notice}</p>
      <ul>{environment.observations.map(r=><li key={r.source_ref.source_id}>
        <strong>{r.station_name}: {r.value} {r.unit}{r.vertical_datum ? ' / '+r.vertical_datum : ''}</strong><br /><UiText>{"관측"}</UiText>{' '}{referenceTime(r.observed_at)} · <UiText>{ages[r.age_status] || r.age_status}</UiText><br /><UiText>{"품질"}</UiText>{' '}{r.quality} (<UiText>{quality[r.quality_status] || r.quality_status}</UiText><UiText>{") · 수집본"}</UiText><UiText>{ages[r.capture_age_status] || r.capture_age_status}</UiText><br />
        <small><UiText>{"좌표"}</UiText>{' '}{r.latitude}, {r.longitude} · <UiText>{r.unit==='m/s'?'10분 평균 · 시간당 제공':'분 단위 수위 · 기준면 RH2000'}</UiText><br />
          <a href={r.station_metadata.url} target="_blank" rel="noreferrer"><UiText>{"관측소 정보"}</UiText></a>
          {r.datum_evidence && <> · <a href={r.datum_evidence.url} target="_blank" rel="noreferrer"><UiText>{"수위 기준면·품질 설명"}</UiText></a></>}
        </small>
      </li>)}</ul>
      <p className="small"><UiText>{"2시간은 앱의 노후화 표시 기준입니다. 가정 풍속·예선·선저 여유 입력값은 자동으로 채우지 않습니다."}</UiText></p>
    </section>}
  </>;
}

export function HistoricalChecks({ checks }) {
  const rows = checks?.filter(c=>c.reference_value_m!=null);
  if (!rows?.length) return null;
  return <div className="notice mt" style={{display:'block'}} data-historical-checks>
    <strong><UiText>{"과거 등록 치수와의 별도 참고 비교"}</UiText></strong>
    {rows.map(c=><p className="small" key={c.kind}><UiText>{checkLabels[c.kind]}</UiText> {metres(c.reference_value_m)}{' '}<UiText>{"/ 선석"}</UiText>{' '}{metres(c.berth_listed_m)} · <UiText>{
      c.status==='reference_value_exceeded'?'과거 등록값이 공개 수치 초과':
      c.status==='within_historical_reference'?'과거 등록값이 공개 수치 이내':'선석 수치 미확인으로 비교 보류'}</UiText></p>)}
    <small><UiText>{"기존 AIS 비교 상태와 현재 입항 판정은 변경하지 않습니다."}</UiText></small>
  </div>;
}
