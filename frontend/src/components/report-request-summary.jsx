import React from 'react';
import {forms,label,makeBody,sections,suggestedRecords} from '../lib/report-forms';

export default function ReportRequestSummary({answer,state}){
  const seed=answer.reportDraft, en=answer.language==='en', lang=en?'en':'ko';
  const kind=seed.kind, known=Object.hasOwn(forms,kind);
  const ship=state.ships.find(s=>s.id===seed.shipId);
  const rows=suggestedRecords(seed,state);
  const chooseRecord=kind==='daily' && rows.length>1;
  const body=known ? makeBody(kind,chooseRecord?[]:rows,ship,seed,lang) : null;
  const fields=body ? sections(kind).filter(s=>!s.table).flatMap(s=>s.keys).filter(k=>
    Object.hasOwn(seed.values || {},k) && body.values[k]!=='' && body.values[k]!=null) : [];
  const sources=state.docs.filter(d=>d.active && seed.sources?.includes(d.id));
  return <section className="report-request-summary">
    <h3>{known ? (en?'Draft · ':'작성할 보고서 · ')+label(forms[kind].name,lang) :
      en?'Choose a form for this request':'요청 내용을 담을 보고서 양식을 선택해 주세요.'}</h3>
    {(fields.length>0 || seed.fuelUsed!=null && !rows.length && ['daily','arrival','departure','fuel'].includes(kind)) && <dl>
      {fields.map(k=><React.Fragment key={k}><dt>{label(k,lang)}</dt><dd>{body.values[k]}</dd></React.Fragment>)}
      {seed.fuelUsed!=null && !rows.length && ['daily','arrival','departure','fuel'].includes(kind) &&
        <><dt>{kind==='fuel' ? (en?'Applied consumption (t)':'적용 사용량 (t)') : label('used',lang)}</dt><dd>{seed.fuelUsed} t {seed.fuelGrade || ''}</dd></>}
    </dl>}
    {rows.length>0 && <p>{en?'Operation records':'연결할 운항 기록'} · {ship?.name} · {rows.length}{en?' records':'건'}{chooseRecord && (en?' · Select one day':' · 사용할 하루를 선택하세요.')}</p>}
    {sources.length>0 && <p>{en?'Sources':'근거 문서'} · {sources.map(d=>d.title).join(', ')}</p>}
    {seed.note && <p>{en?'Remarks':'특이사항'} · {seed.note}</p>}
  </section>;
}
