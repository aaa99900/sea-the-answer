// The five sheets share identification and sign-off fields. Keys stay stable in saved drafts.
const labels = {
  ship:'선박명|Vessel', imo:'IMO 번호|IMO number', company:'운항사|Operator', voyage:'항차 번호|Voyage number',
  number:'보고서 번호|Report number', zone:'선내 시간대 (UTC±)|Ship time zone (UTC±)', start:'시작 일시|Start date and time',
  end:'종료 일시|End date and time', status:'운항 상태|Operating status', location:'현재 항구 / 해역|Port or sea area',
  lat:'위도 (N/S)|Latitude (N/S)', lon:'경도 (E/W)|Longitude (E/W)', next:'다음 기항지|Next port', eta:'ETA · 시간대|ETA and time zone',
  distance:'항해 거리 (nm)|Distance (nm)', hours:'항해 시간 (h)|Sailing hours', speed:'평균 속력 (kn)|Average speed (kn)',
  wind:'풍향 / 풍속 (m/s)|Wind direction / speed (m/s)', wave:'파고 (m)|Wave height (m)', observed:'기상 관측 일시|Observation time',
  ref:'운항 기록 번호|Operation record ID', fuel:'연료 종류|Fuel grade', opening:'시작 잔량 (t)|Opening ROB (t)',
  added:'급유 / 반입 (t)|Bunkered (t)', landed:'반출 (t)|Landed (t)', used:'사용량 (t)|Consumption (t)', closing:'종료 잔량 (t)|Closing ROB (t)',
  mode:'집계 구분|Reporting scope', origin:'출발항|Departure port', destination:'도착항 / 예정항|Arrival / intended port',
  expected:'대상 기록 일수|Days in scope', days:'확보한 기록 일수|Days with records', elapsed:'구간 경과시간 (h)|Elapsed hours',
  day:'날짜 / 구간|Date / interval', refs:'운항 기록 번호|Record references', sounding:'잔량 계측 기록|ROB measurement record',
  proof:'급유·반출 증빙|Transfer evidence', method:'잔량 계측 방법|Measurement method', correction:'계측 보정량 (±t)|Signed adjustment (t)',
  derived:'잔량 기준 사용량 A (t)|ROB consumption A (t)', logged:'기록상 사용량 B (t)|Logged consumption B (t)', diff:'차이 A − B (t)|Difference A − B (t)',
  factor:'계수 (tCO₂/t)|Factor (tCO₂/t)', co2:'배출량 (tCO₂)|Emissions (tCO₂)', source:'계수 출처 / 문서 번호|Factor source / document',
  port:'기항지|Port of call', code:'항구 코드 (UN/LOCODE)|UN/LOCODE', priorPort:'직전 출발항|Previous departure port', berth:'선석 / 정박지|Berth / anchorage',
  eosp:'해상 항해 종료 (EOSP)|End of sea passage (EOSP)', alongside:'접안 완료 일시|All fast time', sosp:'해상 항해 시작 (SOSP)|Start of sea passage (SOSP)',
  unberth:'이안 일시|Unberthing time', fore:'선수 흘수 (m)|Forward draught (m)', aft:'선미 흘수 (m)|Aft draught (m)', load:'적재 상태|Loading condition',
  cargo:'화물량 / 단위|Cargo quantity / unit', prior:'직전 보고 번호|Previous report number', priorTime:'직전 보고 일시|Previous report time',
  arrivalRef:'연결 입항 보고 번호|Arrival report reference', arrivalRob:'입항 잔량 (t)|Arrival ROB (t)', departureRob:'출항 잔량 (t)|Departure ROB (t)',
  author:'작성자 · 직책|Prepared by / rank', prepared:'작성 일시|Prepared at', reviewer:'검토자 · 직책|Reviewed by / rank', reviewed:'검토 일시|Reviewed at',
};
export const label = (value, lang='ko') => (labels[value] || value).split('|')[lang === 'en' ? 1 : 0] || value.split('|')[0];
const fields = (title, keys, table=false) => ({title, keys:keys.split(' '), table});
const table = (title, keys) => fields(title, keys, true);
const id = fields('선박 및 보고 정보|Vessel and report details','ship imo company voyage number zone');
const sign = fields('작성 및 검토|Preparation and review','author prepared reviewer reviewed');
const cargo = fields('선박 상태|Vessel condition','fore aft load cargo');
export const forms = {
  daily:{name:'일일 운항 보고서|Daily operations report', type:'일일 운항', sections:[
    fields('보고 구간과 종료 시점의 선박 상태|Reporting interval and end position','start end status location lat lon next eta'),
    fields('항해 실적 및 기상|Passage and weather','distance hours speed wind wave observed ref'),
    table('연료 사용 및 선내 잔량|Consumption and remaining on board','fuel opening added landed used closing')]},
  voyage:{name:'항차·기간별 운항 실적 보고서|Voyage / period performance report',type:'종합 검토', sections:[
    fields('집계 범위|Reporting scope','mode origin destination start end expected days'),
    table('운항 상태별 집계|Totals by operating status','status elapsed distance hours used'),
    table('운항 기록 명세|Operation record detail','day status distance hours used ref')]},
  fuel:{name:'연료 사용·CO₂ 배출량 검토 보고서|Fuel consumption and CO₂ review',type:'배출량 검토',sections:[
    fields('검토 범위와 근거|Scope and evidence','start end sounding refs proof method'),
    table('연료 수지 대조|Fuel reconciliation','fuel opening added landed correction closing derived logged diff'),
    table('연료 연소에 따른 CO₂ 산정|Combustion CO₂ calculation','fuel used factor co2 source')]},
  arrival:{name:'입항 보고서|Arrival report',type:'종합 검토',sections:[
    fields('기항지와 보고 기준 시점|Port call and event times','port code priorPort berth eosp alongside'),cargo,
    fields('직전 보고부터 EOSP까지의 실적|From previous report to EOSP','prior priorTime distance hours'),
    table('연료 사용 및 입항 잔량|Consumption and arrival ROB','fuel used arrivalRob')]},
  departure:{name:'출항 보고서|Departure report',type:'종합 검토',sections:[
    fields('기항지와 보고 기준 시점|Port call and event times','port code next berth sosp unberth'),cargo,
    fields('연결 보고 및 도착 예정|Linked report and ETA','arrivalRef eta'),
    table('항내 사용량과 출항 잔량|In-port consumption and departure ROB','fuel arrivalRob added landed used correction departureRob')]},
};
export function sections(kind) {return [id,...forms[kind].sections,sign];}
export function validReportBody(body) {
  if (!body || !Object.hasOwn(body,'formType')) return true;
  if (!Object.hasOwn(forms,body.formType)) return false;
  const object=v=>v !== null && typeof v==='object' && !Array.isArray(v);
  const scalar=v=>typeof v==='string' || typeof v==='number' && Number.isFinite(v);
  if (!object(body.values) || !Object.values(body.values).every(scalar) || !object(body.tables)) return false;
  if (body.notes!==undefined && typeof body.notes!=='string') return false;
  if (body.recordIds!==undefined && (!Array.isArray(body.recordIds) || !body.recordIds.every(id=>typeof id==='string'))) return false;
  return sections(body.formType).every((s,i)=>!s.table || (Array.isArray(body.tables[i]) && body.tables[i].every(r=>object(r) && Object.values(r).every(scalar))));
}
const number = value => value === '' || value == null || !Number.isFinite(Number(value)) ? null : Number(value);
const rounded = value => String(Math.round(value * 10000)/10000);
const formulas = {
  closing: [['opening','added','landed','used'],(a,b,c,d)=>a+b-c-d],
  derived: [['opening','added','landed','correction','closing'],(a,b,c,d,e)=>a+b-c+d-e],
  diff: [['derived','logged'],(a,b)=>a-b], co2:[['used','factor'],(a,b)=>a*b],
  departureRob:[['arrivalRob','added','landed','used','correction'],(a,b,c,d,e)=>a+b-c-d+e],
};
export function computed(key,keys) {return Boolean(formulas[key] && formulas[key][0].every(k=>keys.includes(k)));}
export function rowValues(row,keys) {
  const out={...row};
  for (const key of keys.filter(k=>computed(k,keys))) {
    const [inputs,calc]=formulas[key], values=inputs.map(k=>number(out[k]));
    out[key]=values.includes(null) ? '' : rounded(calc(...values));
  }
  return out;
}
const summable=new Set('opening added landed correction closing used derived logged diff co2 arrivalRob departureRob elapsed distance hours'.split(' '));
export function totals(rows,keys) {
  return keys.map(k=>summable.has(k) && rows.length && rows.every(r=>number(r[k])!==null) ? rounded(rows.reduce((sum,r)=>sum+Number(r[k]),0)) : '');
}
export function formText(body) {
  const {formType,values={},tables={},notes='',language}=body;
  const t = key=>label(key,language);
  const lines=[t(forms[formType].name)];
  for (const [i,s] of sections(formType).entries()) {
    lines.push('',t(s.title));
    if (!s.table) {for(const k of s.keys) lines.push(t(k)+' · '+(values[k] ?? ''));continue;}
    const rows=(tables[i] || []).map(r=>rowValues(r,s.keys));
    lines.push(s.keys.map(t).join(' | '),...rows.map(r=>s.keys.map(k=>r[k] ?? '').join(' | ')));
    const sums=totals(rows,s.keys);
    if(sums.some(Boolean)) {sums[0]=t('합계|Total');lines.push(sums.join(' | '));}
  }
  if(body.recordIds?.length) lines.push('',t('선택한 운항 기록|Selected operation records'),body.recordIds.join(', '));
  if(body.sample) lines.push(t('가상 예시 운항 기록 포함|Includes sample operation records'));
  if(notes) lines.push('',t('특이사항 및 검토 메모|Remarks and review notes'),notes);
  return lines.join('\n');
}
export function makeBody(kind, rows, ship, seed={}, language='ko') {
  const ordered=[...rows].sort((a,b)=>a.date.localeCompare(b.date));
  const v={}, tables={};
  sections(kind).forEach((s,i)=>{if(s.table) tables[i]=[{}];});
  if(ship){v.ship=ship.name;v.imo=ship.imo || '';}
  if(ordered.length){
    const first=ordered[0],last=ordered.at(-1);
    if(['daily','voyage','fuel'].includes(kind)){v.start=first.date;v.end=last.date;}
    if(first.voyage && ordered.every(r=>r.voyage===first.voyage)) v.voyage=first.voyage;
    const groups=new Map();
    for(const r of ordered) groups.set(r.fuelType,(groups.get(r.fuelType)||0)+r.fuel);
    if(kind==='daily'){
      v.ref=first.id;v.distance=first.distance;v.location=first.position || '';v.speed=first.speed;
      tables[3]=[{fuel:first.fuelType,used:first.fuel}];
    } else if(kind==='voyage'){
      v.expected=1+(Date.parse(last.date)-Date.parse(first.date))/86400000;
      v.mode=label('지정 기간|Selected period',language);v.days=new Set(ordered.map(r=>r.date)).size;
      tables[2]=[{status:label('기타 / 미분류|Other / unclassified',language),distance:ordered.reduce((n,r)=>n+r.distance,0),used:ordered.reduce((n,r)=>n+r.fuel,0)}];
      tables[3]=ordered.map(r=>({day:r.date,distance:r.distance,used:r.fuel,ref:r.id}));
    } else if(kind==='fuel'){
      v.refs=ordered.map(r=>r.id).join(', ');
      tables[2]=Array.from(groups,([fuel,logged])=>({fuel,logged}));
      tables[3]=ordered.map(r=>({fuel:r.fuelType,used:r.fuel,factor:r.factor,source:r.id}));
    }
  }
  for (const [key,value] of Object.entries(seed.values || {})) if(sections(kind).some(s=>!s.table && s.keys.includes(key))) v[key]=value;
  if(seed.fuelUsed != null && !ordered.length && ['daily','arrival','departure'].includes(kind)){
    const tableIndex=sections(kind).findIndex(s=>s.table);
    tables[tableIndex]=[{used:seed.fuelUsed,fuel:seed.fuelGrade || ''}];
  }
  if(kind==='fuel' && !ordered.length && seed.fuelUsed!=null){
    tables[3]=[{fuel:seed.fuelGrade || '',used:seed.fuelUsed}];
  }
  return {formType:kind,language,from:v.start || '',to:v.end || '',values:v,tables,notes:[seed.note,seed.contextNote].filter(Boolean).join('\n\n'),recordIds:ordered.map(r=>r.id),sample:ordered.some(r=>r.sample)};
}

// Used by both the confirmation in chat and the draft editor.
export function suggestedRecords(seed,state){
  const selected=new Set(seed.recordIds || []);
  return state.operationRecords.filter(r=>r.ship===seed.shipId && selected.has(r.id) &&
    (!seed.values?.start || r.date>=seed.values.start) && (!seed.values?.end || r.date<=seed.values.end));
}
