import React, {useState} from 'react';
import {forms, label, sections, computed, rowValues, totals} from '../lib/report-forms';

export function ReportChooser({state, seed={}, create}) {
  const t=k=>label(k,state.uiLanguage);
  const [kind,setKind]=useState(seed.kind || 'free'), [ship,setShip]=useState(seed.shipId || ''),
    [ids,setIds]=useState(seed.kind==='daily' ? [] : seed.recordIds || []), [docs,setDocs]=useState(seed.sources || []),
    [from,setFrom]=useState(seed.values?.start?.slice(0,10) || ''), [to,setTo]=useState(seed.values?.end?.slice(0,10) || '');
  const active=state.docs.filter(d=>d.active);
  const records=state.operationRecords.filter(r=>r.ship===ship && (!from||r.date>=from) && (!to||r.date<=to));
  const selected=records.filter(r=>ids.includes(r.id));
  const toggle=(array,value)=>array.includes(value)?array.filter(v=>v!==value):[...array,value];
  return <div className="report-builder">
    <label className="field">{t('보고서 유형|Report type')}<select id="new-report-kind" value={kind} onChange={e=>{setKind(e.target.value);setIds([]);}}>
      <option value="free">{t('빈 양식 · 자유 작성|Blank report')}</option>
      {Object.entries(forms).map(([key,f])=><option key={key} value={key}>{t(f.name)}</option>)}
    </select></label>
    <details open={seed.shipId ? true : undefined}><summary>{t('선박 및 운항 기록 선택|Select vessel and operation records')} ({selected.length})</summary>
      <label className="field">{t('선박명|Vessel')}<select value={ship} onChange={e=>{setShip(e.target.value);setIds([]);}}>
        <option value="">{t('선택 안 함|None')}</option>{state.ships.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
      </select></label>
      {ship && <><div className="report-grid">{[[from,setFrom,'시작일|From'],[to,setTo,'종료일|To']].map(([value,set,key])=>
        <label className="field" key={key}>{t(key)}<input type="date" value={value} onChange={e=>set(e.target.value)}/></label>)}</div>
        <div className="report-choices">{records.map(r=><label key={r.id}><input type={kind==='daily'?'radio':'checkbox'} name="report-record" checked={ids.includes(r.id)} onChange={()=>setIds(kind==='daily'?[r.id]:toggle(ids,r.id))}/>{r.date} · {r.fuel} t · {r.distance} nm {r.sample?t('(가상)|(Sample)'):''}</label>)}
        {!records.length && t('해당 기간에 기록이 없습니다.|No records in this period.')}</div>
        {!!ids.length && <button type="button" className="btn sm ghost" onClick={()=>setIds([])}>{t('기록 선택 해제|Clear record selection')}</button>}
      </>}
    </details>
    <details><summary>{t('근거 문서 선택|Select source documents')} ({docs.length})</summary><div className="report-choices">
      {active.map(d=><label key={d.id}><input type="checkbox" checked={docs.includes(d.id)} onChange={()=>setDocs(toggle(docs,d.id))}/>{d.title}</label>)}
    </div></details>
    <button type="button" id="create-selected-report" className="btn primary" onClick={()=>create(kind,selected,state.ships.find(s=>s.id===ship),docs.filter(id=>active.some(d=>d.id===id)))}>{t('초안 열기|Open draft')}</button>
  </div>;
}

export function ReportFields({body,disabled,onEdit,language}) {
  const t=k=>label(k,language), {formType,values,tables}=body;
  const edit=changes=>{
    const next={...body,...changes};
    onEdit({...next,from:next.values.start || '',to:next.values.end || ''});
  };
  const replace=(i,rows)=>edit({tables:{...tables,[i]:rows}});
  return <div className="report-builder report-sheet">{sections(formType).map((s,i)=>{
    const rows=tables[i] || [];
    const sums=totals(rows.map(row=>rowValues(row,s.keys)),s.keys);
    return <section key={s.title}><h3>{t(s.title)}</h3>{s.table ? <>
      <div className="report-table-scroll"><table><thead><tr>{s.keys.map(k=><th key={k}>{t(k)}</th>)}{!disabled && <th/>}</tr></thead>
      <tbody>{rows.map((row,j)=><tr key={j}>{s.keys.map(k=><td key={k}><input aria-label={t(k)+' '+(j+1)} value={rowValues(row,s.keys)[k] ?? ''} readOnly={disabled || computed(k,s.keys)} maxLength={180}
        onChange={e=>replace(i,rows.map((r,index)=>index===j?{...r,[k]:e.target.value}:r))}/></td>)}
        {!disabled && <td><button type="button" aria-label={t('행 삭제|Remove row')+' '+(j+1)} onClick={()=>replace(i,rows.filter((_,n)=>n!==j))}>×</button></td>}</tr>)}</tbody>
      {sums.some(Boolean) && <tfoot><tr>{sums.map((v,j)=><td key={j}>{j===0?t('합계|Total'):v}</td>)}</tr></tfoot>}</table></div>
      {!disabled && <button type="button" className="btn sm" onClick={()=>replace(i,[...rows,{}])}>{t('행 추가|Add row')}</button>}</> :
      <div className="report-grid">{s.keys.map(k=><label className="field" key={k}>{t(k)}<input readOnly={disabled} value={values[k] ?? ''} maxLength={k==='refs'?6000:300}
        onChange={e=>edit({values:{...values,[k]:e.target.value}})}/></label>)}</div>}</section>;
  })}
    {body.recordIds?.length>0 && <details><summary>{t('선택한 운항 기록|Selected operation records')} ({body.recordIds.length})</summary>
      {body.sample && <p>{t('가상 예시 운항 기록 포함|Includes sample operation records')}</p>}<p>{body.recordIds.join(', ')}</p></details>}
    <label className="field">{t('특이사항 및 검토 메모|Remarks and review notes')}<textarea readOnly={disabled} value={body.notes || ''} onChange={e=>edit({notes:e.target.value})}/></label>
  </div>;
}

export function ReportPaper({draft,documents}) {
  const {body}=draft, t=k=>label(k,body.language);
  return <article className="report-paper" id="printable-report">
    <header><small>해답 / SEA THE ANSWER</small><h2>{draft.title}</h2><p>{t(forms[body.formType].name)}</p></header>
    {sections(body.formType).map((s,i)=>{
      const rows=(body.tables[i] || []).map(r=>rowValues(r,s.keys)), sums=totals(rows,s.keys);
      return <section key={s.title}><h3>{t(s.title)}</h3>
        {s.table ? <table><thead><tr>{s.keys.map(k=><th key={k}>{t(k)}</th>)}</tr></thead><tbody>{rows.map((r,j)=><tr key={j}>{s.keys.map(k=><td key={k}>{r[k] ?? ''}</td>)}</tr>)}</tbody>
          {sums.some(Boolean) && <tfoot><tr>{sums.map((v,j)=><td key={j}>{j===0?t('합계|Total'):v}</td>)}</tr></tfoot>}</table> :
          <dl>{s.keys.map(k=><div key={k}><dt>{t(k)}</dt><dd>{body.values[k]}</dd></div>)}</dl>}
      </section>;
    })}
    {body.notes && <section><h3>{t('특이사항 및 검토 메모|Remarks and review notes')}</h3><p>{body.notes}</p></section>}
    {body.sample && <p>{t('가상 예시 운항 기록 포함|Includes sample operation records')}</p>}
    {(draft.sources.length>0 || body.recordIds?.length>0) && <section><h3>{t('작성 근거|Sources')}</h3><p>{[...draft.sources.map(id=>documents.find(d=>d.id===id)?.title || id),...(body.recordIds || [])].join('\n')}</p></section>}
  </article>;
}
