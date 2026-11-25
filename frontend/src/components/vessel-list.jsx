import React from 'react';
import {UiControl, UiText} from './ui-language';

const dwtLabels = {mrv_report: 'MRV 보고값', public_candidate: '공개 후보값'};

export default function VesselList({value}) {
  const {items, source, source_label: sourceLabel, has_more: hasMore} = value;
  return <UiControl as="section" className="mt" data-testid="vessel-list" aria-label="선박 목록">
    <p className="small muted"><UiText>{sourceLabel}</UiText>
      {' · '}<UiText>표시한 선박</UiText>{' '}{items.length}
      {hasMore && <>{' · '}<UiText>추가 선박 있음</UiText></>}
    </p>
    {items.length > 0 && <div className="tablewrap"><table>
      <thead><tr>
        {['선박명', 'IMO 번호', '선종', 'DWT (t)'].map(label => <th key={label} scope="col"><UiText>{label}</UiText></th>)}
        {source === 'mrv' && <th scope="col"><UiText>MRV 보고연도</UiText></th>}
      </tr></thead>
      <tbody>{items.map((vessel, index) => <tr key={index}>
        <th scope="row">{vessel.name || '—'} {vessel.sample && <small className="muted"><UiText>가상 예시</UiText></small>}</th>
        <td>{vessel.imo || '—'}</td>
        <td>{vessel.ship_type || '—'}</td>
        <td>{vessel.dwt_t ?? '—'} {dwtLabels[vessel.dwt_source] &&
          <small className="muted"><UiText>{dwtLabels[vessel.dwt_source]}</UiText></small>}</td>
        {source === 'mrv' && <td>{vessel.reporting_year ?? '—'}</td>}
      </tr>)}</tbody>
    </table></div>}
  </UiControl>;
}
