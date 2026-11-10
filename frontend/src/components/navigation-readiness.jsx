import {UiText} from './ui-language';
import React from 'react';

const states = { needs_information:'추가 정보 필요', action_required:'가정 조건상 조치 필요',
  within_scenario:'가정값이 해당 수치 기준 충족', not_triggered_in_scenario:'가정값에서 해당 조건 미발동' };
const inputs = { wind_at_arrival:'입항 시 풍속', available_tugs:'확보할 예선 수', assessed_under_keel_clearance:'검토된 선저 여유',
  reported_length_for_provisional_trigger:'비교 가능한 선박 신고 길이', unambiguous_berth_source:'중복 없는 선석 원문',
  latest_soundings_and_pilot_restrictions:'최신 측심·도선 제한', port_control_confirmation:'항만 운영부 확인' };
inputs.current_port_source = '오래되거나 시각이 잘못된 항만 자료의 갱신';

export function NavigationReadiness({ value }) {
  if (!value) return null;
  return <details className="card pad mt" data-navigation-readiness>
    <summary><UiText>{"입항 전 추가 확인 ·"}</UiText>{value.items.length}<UiText>{"개 항목 미확인"}</UiText></summary>
    <p className="notice warning mt">{value.notice}</p>
    {value.scenario_only && <p className="notice"><UiText>{"입력한 가정 조건으로만 검토했습니다. 실제 풍속·예선 확보·현재 실측 흘수를 인증한 결과가 아닙니다."}</UiText></p>}
    <ul>{value.items.map(item=><li key={item.id}><strong>{item.title}</strong><UiText>{"· 확인 필요"}</UiText><br />{item.reason}</li>)}</ul>
  </details>;
}

export function OperationalChecks({ checks }) {
  if (!checks?.length) return null;
  return <section className="mt" data-navigation-operational-checks>
    <strong><UiText>{"게시 조건의 추가 검토"}</UiText></strong>
    {checks.map(check=><div key={check.id} className="notice mt" style={{display:'block'}}>
      <strong><UiText>{check.kind==='tug'?'예선 조건':check.kind==='ukc'?'선저 여유 조건':'최신 자료 확인'}</UiText> · <UiText>{states[check.status] || check.status}</UiText></strong>
      <p>{check.scope}</p>
      {check.missing_inputs?.length>0 && <p><UiText>{"필요 정보:"}</UiText>{check.missing_inputs.map(k=>inputs[k] || k).join(' · ')}</p>}
      {check.values?.scenario_wind_m_s!=null && <p><UiText>{"가정 풍속"}</UiText>{check.values.scenario_wind_m_s}<UiText>{"m/s · 가정 예선"}</UiText>{check.values.scenario_available_tugs ?? '미입력'}<UiText>{"척"}</UiText></p>}
      {check.values?.scenario_ukc_m!=null && <p><UiText>{"가정 선저 여유"}</UiText>{check.values.scenario_ukc_m}<UiText>{"m · 게시 기준"}</UiText>{check.minimum_m} m</p>}
      <details><summary><UiText>{"규칙 원문·위치"}</UiText></summary><p>{check.source_text}</p><small>{check.source_ref?.source_id} · {check.source_ref?.locator}</small></details>
    </div>)}
    <p className="small muted"><UiText>{"일부 검토된 조건만 구조화했습니다. 원문 전체 조건과 실제 입항 승인은 별도 확인해야 합니다."}</UiText></p>
  </section>;
}
