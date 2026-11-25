"""Explicit user constraints that can be executed and checked without guessing values."""
import re
from uuid import UUID

from .question_intent import date_slots
from .ship_identity import named_ships


def language_request(q):
    choices = []
    for code, pattern in [('en', r'영어(?:로만|로|만|판|(?=\s*(?:표|목록|요약|답변)))|영문(?:으로만|으로|(?=\s*(?:표|목록|요약|답변)))|\bin English\b'),
                          ('ko', r'(?:한국어|한글|국문)(?:로만|으로|로|만|(?=\s*(?:표|목록|요약|답변)))|\bin Korean\b')]:
        for m in re.finditer(pattern, q, re.I):
            if not re.match(r'\s*(?:말고|제외|쓰지|하지)', q[m.end():]):
                choices.append((m.start(), code))
    return max(choices)[1] if choices else None


def report_kind(q):
    kinds = {
        'arrival':r'입항\s*(?:보고|리포트)|arrival\s+report',
        'departure':r'출항\s*(?:보고|리포트)|departure\s+report',
        'fuel':r'연료\s*(?:사용|소모)|배출량\s*(?:검토|보고)|fuel.{0,24}(?:review|report)|CO[₂2].{0,8}검토',
        'voyage':r'(?:항차|기간별).{0,15}(?:실적|보고)|(?:voyage|period)\s+(?:performance|report)',
        'daily':r'일일\s*(?:운항|보고)|정오\s*보고|noon\s*report|daily\s*(?:operations?\s*)?report',
    }
    # A named event form has priority over consumption mentioned as report content.
    return next((key for key in ['arrival','departure','daily','voyage','fuel'] if re.search(kinds[key],q,re.I)), 'free')


def report_request(q, previous_kind=None, default_year=None):
    if not previous_kind and not re.search(r'보고서|리포트|report|초안', q, re.I):
        return None
    if re.search(r'작성법|작성\s*방법|어떻게.{0,12}(?:쓰|써|작성|만들)|(?:작성|생성|만들|써)\s*(?:하지\s*마|지\s*마)|how (?:do|to|can)|do not|don.t (?:create|draft|write)', q, re.I):
        return None
    if re.search(r'(?:보고서|양식).{0,20}(?:차이|작성법|준비물|필수\s*항목|양식의\s*구성).{0,16}(?:정리|알려|설명)|보고서.{0,12}(?:쓰지|만들지|작성하지)\s*(?:마|말)',q,re.I):
        return None
    if not re.search(r'(?:작성|생성|준비|정리)(?:해|하자|하고\s*싶|해\s*줘|할래|을?\s*부탁)|만들어|써\s*(?:줘|주|줄)|\b(?:draft|prepare|create|write|generate)\b.{0,70}\breport\b', q, re.I):
        return None
    kind = report_kind(q)
    if kind == 'free' and previous_kind:
        kind = previous_kind
    values={}
    fields={'ship':r'(?:선박명|vessel name)', 'company':r'(?:운항사|operator)', 'number':r'(?:보고서 번호|report number)',
            'origin':r'(?:출발항|departure port)', 'destination':r'(?:도착항|예정항|destination)', 'port':r'(?:기항지|입항항|출항항|port of call)', 'berth':r'(?:선석|berth)',
            'next':r'(?:다음\s*기항지|다음\s*항구|next port)', 'voyage':r'(?:항차\s*번호|voyage no\.?)',
            'code':r'(?:UN/LOCODE)', 'eta':r'ETA', 'eosp':r'EOSP', 'sosp':r'SOSP', 'zone':r'(?:시간대|time zone)'}
    for key,title in fields.items():
        m=re.search(title+r'\s*[:=]\s*([^,;\n。]{1,80})',q,re.I)
        if key=='port':
            m=next((candidate for candidate in re.finditer(title+r'\s*[:=]\s*([^,;\n。]{1,80})',q,re.I)
                    if not re.search(r'다음\s*$',q[:candidate.start()])),None)
        if m: values[key]=m[1].strip()
    for key,tag,unit in [('distance','항해\\s*거리|거리|distance','nm|해리'),('hours','항해\\s*시간|sailing time','h|시간'),
                         ('fore','선수\\s*흘수|forward draught','m'),('aft','선미\\s*흘수|aft draught','m')]:
        m=re.search(r'(?:'+tag+r')\s*(?:[:=]|는|은)?\s*(\d+(?:\.\d+)?)\s*(?:'+unit+r')',q,re.I)
        if m: values[key]=m[1]
    result={'kind':kind,'values':values}
    note = re.search(r"""(?:특이사항|비고|메모|remarks?|notes?)(?:에는|에|은|는)?\s*[:=]?\s*["“‘']([^"”’']+)["”’']""", q, re.I)
    if not note:
        note = re.search(r'(?:특이사항|비고|메모|remarks?|notes?)\s*[:=]\s*([^;\n]+)', q, re.I)
    if note:
        result['note'] = note[1].strip()
    fuel=re.search(r'(?:연료\s*(?:사용량|사용|소모량)?|fuel\s*(?:used|consumption)?)\s*(?:[:=]|는|은)?\s*(\d+(?:\.\d+)?)\s*(?:t\b|톤)',q,re.I)
    if fuel: result['fuelUsed']=fuel[1]
    grade=re.search(r'\b(VLSFO|HFO|MGO|LNG|MDO)\b',q,re.I)
    if grade: result['fuelGrade']=grade[1].upper()
    if 'port' not in values and kind in ('arrival','departure'):
        m=next((p for p in re.finditer(r'([가-힣A-Za-z]{2,20}항)(?:에서|에|으로|을|를)?(?:\s|,|$)',q) if not re.search(r'(?:다음\s*(?:기항지|항구)|직전\s*출발항)\s*[:=]\s*$',q[:p.start()])),None)
        if m and m[1] not in ('입항','출항'):values['port']=m[1]
    for event,key in [('접안','alongside'),('이안','unberth'),('EOSP','eosp'),('SOSP','sosp')]:
        match=re.search(event+r'\s*(?:완료)?\s*(?:시각|일시|시간)?\s*(?:[:=]|은|는)?\s*((?:\d{4}-\d{2}-\d{2}[ T])?\d{1,2}:\d{2})',q,re.I)
        if match:values[key]=match[1]
    try:
        _, periods=date_slots(q,default_year=default_year)
        if len(periods)==1:
            values.update(start=periods[0].start,end=periods[0].end)
    except ValueError:
        pass  # Keep the original question intact for human review.
    return result


def enrich_draft(ctx,draft,q):
    documents=ctx.db.documents(ctx.user)
    current={d['id'] for d in documents if d.get('active',True)}
    draft['sources']=list(dict.fromkeys(id for _,_,id in document_matches(q,documents)))
    if draft.get('shipId'):
        v=draft['values']
        whole=ALL_RECORDS.search(q)
        if whole or v.get('start') and v.get('end'):
            rows=ctx.db.ship_records(draft['shipId'])
            selected=[r for r in rows if (not v.get('start') or r['date']>=v['start'])
                      and (not v.get('end') or r['date']<=v['end'])]
            draft['recordIds']=[r['id'] for r in selected]
            if whole and selected:
                v.setdefault('start',min(r['date'] for r in selected))
                v.setdefault('end',max(r['date'] for r in selected))
    if not re.search(r'방금|앞서|위\s*(?:내용|결과)|(?:이|그)\s*(?:내용|결과|답변|기록)(?:으?로|을)|previous (?:answer|result)|these results',q,re.I):
        return
    prior=previous_answer(ctx)
    sources=[e['document_id'] for e in prior.get('evidence',[]) if e.get('document_id')]
    if not prior or not set(sources)<=current:return
    draft['sources']=list(dict.fromkeys(draft['sources']+sources))
    notes=[]
    for item in prior.get('statements',[]):
        if item.get('text') and any(e.get('id')==item.get('chunkId') for e in prior.get('evidence',[])):
            notes.append(item['text'])
    selection=prior.get('recordSelection',{})
    scope=selection.get('scope',{})
    if scope and not (draft.get('shipId') and scope.get('ship')!=draft['shipId']):
        if not draft.get('shipId'):draft['shipId']=scope.get('ship')
        draft['recordIds']=[i for r in selection.get('rows',[]) for i in r.get('recordIds',[r['id']])]
        for key in ('start','end'):
            if scope.get(key):draft['values'].setdefault(key,scope[key])
    draft['contextNote']='\n'.join(filter(None,notes))[:5000]


def document_matches(q, documents):
    matches=[]
    for d in documents:
        if not d.get('active',True):continue
        name=re.sub(r'^\(테스트용\)\s*|\s*\(가상\)$','',' '.join(d['title'].split()),flags=re.I)
        names=[name,re.sub(r'\s*\([^()]*\)\s*$','',name).strip()]
        if ' · ' in name:names.append(name.split(' · ',1)[1].strip())
        code=re.search(r'\bMEPC[\s.]+\d+(?:\s*\(\d+\)|/\d+(?:/Add\.\d+)?)',name,re.I)
        if code:names.append(code[0])
        for alias in names:
            if len(alias)<3:continue
            pattern=r'(?<![\w/])'+r'\s*'.join(re.escape(w) for w in alias.split())+r'(?![A-Za-z0-9/(])'
            match=re.search(pattern,q,re.I)
            if match:
                matches.append((match.start(),match.end(),d['id']))
                break
    return [(a,b,k) for a,b,k in matches if not any(c<=a and e>=b and (a,b)!=(c,e) for c,e,_ in matches)]


def previous_answer(ctx):
    query=(ctx.body.get('context') or {}).get('previousQueryId')
    if not query or not ctx.body.get('conversationId'):return {}
    try: UUID(query)
    except (TypeError,ValueError,AttributeError): return {}
    row=ctx.db.one('SELECT q.response FROM queries q JOIN query_owner o ON o.id=q.id WHERE q.id=%s AND o.owner=%s',(query,ctx.user['id']))
    a=(row or {}).get('response',{})
    if a.get('conversationId',a.get('id'))!=ctx.body['conversationId']:return {}
    return a


METRICS={'fuel':('연료 사용량 (t)','Fuel consumption (t)',r'연료|기름|사용량|소모량|\bfuel\b'),
         'distance':('항해 거리 (nm)','Distance (nm)',r'거리|해리|몇\s*마일|얼마나\s*(?:항해|달렸|다녔)|\bdistance\b|\bnautical miles\b'),
         'speed':('속력 (kn)','Speed (kn)',r'속력|속도|\bspeed\b'),
         'co2':('배출량 (tCO₂)','Emissions (tCO₂)',r'배출|탄소|CO[₂2]|emissions?')}


ALL_RECORDS = re.compile(r'(?:모든|전체|전\s*기간|전부)\s*(?:운항\s*)?(?:기록|자료|데이터|기간)|(?:기록|자료|데이터)(?:을|를)?\s*(?:전체|전부|모두|다\s*합)|전\s*기간|전체\s*기간|누적|누계|지금(?:까지|껏)|여태(?:까지|껏)?|그동안|기록된\s*(?:거|것)\s*전부|등록된\s*(?:거|것)\s*전부|처음(?:부터|\s*기록부터)|기록(?:을|이)?\s*(?:시작|남기기 시작)한\s*(?:이래|이후)|since (?:records began|the first record)|all[ -](?:time|records)|all (?:operation|voyage) records|to date', re.I)


def record_list_intent(q):
    if re.search(r'규정|절차|무슨\s*뜻|작성법|현황|수집|출처|유무|몇\s*(?:건|개)|합계|합산|총합|평균|비교|순위|추이|현재\s*위치|마지막.{0,8}위치|보고서|문서|삭제|수정|등록해|추가해|definition|average|summary|compare|how many',q,re.I):
        return False
    subject = re.search(r'(?:운항|항해)\s*(?:일지|기록|내역|로그|데이터)|(?:operation|voyage|sailing)\s+(?:logs?|records?)',q,re.I)
    listing = re.search(r'알려|보여|꺼내|목록|리스트|조회|나열|열거|열람|건별|기록별|개별|한\s*건씩|list|show|display',q,re.I)
    return bool(listing and (subject or re.search(r'(?:HAE\s*\d+|선박|\w+호).{0,80}(?:기록|내역)',q,re.I)))


def list_records(ctx, q, save, mentions=()):
    """Return bounded rows and the matching count for the entire database scope."""
    en = ctx.body.get('language') == 'en' or ctx.body.get('language','auto') == 'auto' and not re.search('[가-힣]',q)
    def clarify(ko,eng):
        return save(ctx,{'notice':eng if en else ko},{'method':'rules','route':'clarify'})
    ships = ctx.db.ships()
    try:
        selected = named_ships(q,ships)
        years, periods = date_slots(q)
    except ValueError:
        return clarify('선박명과 조회할 날짜 범위를 확인해 주세요.','Please check the vessel name and date range.')
    names = {s['id']:s['name'] for s in ships}
    explicit = [*mentions,*re.findall(r'\bHAE\s*\d+|IMO\s*\d{7}|[가-힣]{2,}호(?=의|에서|는|\s|$)',q,re.I)]
    for mention in explicit:
        lookup = re.sub(r'\s+', '',mention).casefold()
        if lookup not in re.sub(r'\s+','',q).casefold():
            return clarify('조회할 선박명을 확인해 주세요.','Please confirm the vessel name.')
        found = [s for s in ships if (s in selected and lookup in re.sub(r'\s+','',s['name']).casefold()) or
                 (s.get('imo') and lookup == 'imo'+str(s['imo']).lower().removeprefix('imo').strip())]
        if len(found) != 1:
            return clarify('해당 선박을 확인할 수 없습니다. 등록된 선박명을 알려 주세요.','Please specify a registered vessel.')
        if found[0] not in selected:
            selected.append(found[0])
    if len(periods)>1 or (not periods and len(years)>1):
        return clarify('조회할 기간 하나를 지정해 주세요.','Specify one date range.')
    start,end = (periods[0].start, periods[0].end) if periods else (f'{years[0]}-01-01',f'{years[0]}-12-31') if years else (None,None)
    count = re.search(r'(\d+)\s*(?:개|건)|(?:last|first|latest)\s+(\d+)\s+(?:records|entries)',q,re.I)
    limit = int(count[1] or count[2]) if count else 100 if ALL_RECORDS.search(q) else 20
    if not 1 <= limit <= 100:
        return clarify('한 번에 표시할 기록은 1~100건입니다. 기간을 좁혀 주세요.','Choose 1–100 records or narrow the dates.')
    real_only = bool(re.search(r'가상.{0,8}제외|실제.{0,8}만|exclude sample|real only',q,re.I))
    sample_only = bool(re.search(r'가상.{0,8}만|sample only',q,re.I))
    subset = False if real_only else True if sample_only else None
    latest = not start and not re.search(r'시간순|오래된|oldest|chronological',q,re.I) or bool(re.search(r'최신|최근순|newest|latest',q,re.I))
    rows = ctx.db.record_page([s['id'] for s in selected], start, end, limit, latest, subset)
    total = rows[0]['matches'] if rows else 0
    scope = ', '.join(s['name'] for s in selected) or ('All vessels' if en else '전체 선박')
    span = f'{start} ~ {end}' if start else ('All dates' if en else '전체 기간')
    notice = f'{scope} · {span} · ' + (f'{len(rows)} of {total} records' if en else f'{total}건 중 {len(rows)}건 표시')
    if any(r['body'].get('sample') for r in rows):
        notice += ' · ' + ('Includes sample records' if en else '가상 예시 기록 포함')
    columns = ['Date','Vessel','Distance (nm)','Fuel (t)','CO₂ (t)'] if en else ['날짜','선박','거리 (nm)','연료 (t)','CO₂ (t)']
    result = []
    for item in rows:
        row = item['body']
        co2 = round(row['fuel']*row['factor'],4) if row.get('fuel') is not None and row.get('factor') is not None else '—'
        result.append({'id':row['id'],'cells':[row['date'],names.get(row['ship'],row['ship']),row.get('distance','—'),row.get('fuel','—'),co2]})
    fmt = 'list' if re.search(r'리스트|목록으로|as a list',q,re.I) else 'table'
    return save(ctx,{'task':'operations_selection','status':'completed','notice':notice,
                'recordSelection':{'format':fmt,'columns':columns,'rows':result}},
                {'method':'rules','route':'operations_selection'})


def record_selection(ctx,q,save,metric_hint=None,ranking=None):
    whole = bool(ALL_RECORDS.search(q))
    # Do not turn requests for definitions, forecasts or vessel comparisons into totals.
    if re.search(r'공식|원인|예측|규정|정의|무슨 뜻|비교|그래프|차트|평균|절차|어떻게|몇\s*(?:건|개)|forecast|compare|average',q,re.I):
        return None
    follow=bool(re.search(r'같은\s*조건|동일한?\s*조건|same (?:conditions|filters)',q,re.I))
    prior=previous_answer(ctx).get('recordSelection',{}).get('scope',{}) if follow else {}
    rank=re.search(r'상위|하위|(?:가장|제일)[^?.!,]{0,30}?(?:많|적|높|낮|길|짧)|(?:많|적|높|낮)(?:은|았던|게|이)[^?.!,]{0,15}?(?=(?:기록|순|세\s*건|날))|최다|최소|최대|내림차순|오름차순|\b(?:top|bottom|highest|lowest|descending|ascending)\b',q,re.I)
    threshold=re.search(r'(\d+(?:\.\d+)?)\s*(?:톤|t|nm|kn|해리)?\s*(이상|이하|초과|미만)',q,re.I)
    metrics=[k for k,(_,_,p) in METRICS.items() if re.search(p,q,re.I)]
    if not metrics and metric_hint:
        metrics = [metric_hint]
    individual = bool(re.search(r'건별|각각|기록별|개별|한\s*건씩|each record|per record',q,re.I))
    asks_sum = bool(re.search(r'합계|합산|총합|합(?:을|은|이|해|산|친|치|한다)|누[계적]|총\s*(?:운항|항해|이동|거리|연료|배출)|sum|total',q,re.I))
    if not prior and not rank and not ranking and not threshold and not asks_sum and record_list_intent(q):
        return list_records(ctx,q,save)
    total = whole and bool(metrics) and not (rank or ranking or threshold or individual)
    if not prior and not total and not ranking and (not metrics or not (rank or threshold) or not re.search(r'운항|기록|일별|날|records?|days?',q,re.I)):
        return None
    lang=language_request(q) or prior.get('language') or ctx.body.get('language','auto')
    en=lang=='en' or lang=='auto' and not re.search('[가-힣]',q)
    ctx.body['language']='en' if en else 'ko'
    def missing(ko,eng,field=None):
        fields={'notice':eng if en else ko}
        if field:
            fields['pendingRecordRequest']={'question':q,'field':field}
        return save(ctx,fields,{'method':'rules','route':'clarify'})
    if len(metrics)>1 and total:
        return missing('합산할 지표 하나를 지정해 주세요.','Which metric should I total?')
    if len(metrics)>1:
        return missing('어떤 지표로 순위를 정할까요? 연료, 거리, 속력, 배출량 중 하나를 지정해 주세요.','Choose one ranking metric: fuel, distance, speed or CO₂.')
    metric=(metrics or [prior.get('metric')])[0]
    ships=ctx.db.ships()
    try:
        named=named_ships(q,ships)
        # In a ranking, “높았던 날 3일” gives a result count, not a calendar date.
        date_text = re.sub(r'((?:상위|하위|날(?:짜)?|top|bottom)\s*\d+)\s*일',r'\1건',q,flags=re.I) if (rank or ranking) else q
        years,periods=date_slots(date_text,default_year=int(prior['start'][:4]) if prior.get('start') else None)
    except ValueError as e:
        return missing(str(e),'Please specify a unique vessel and valid reporting period.')
    vessel=named[0] if len(named)==1 else None
    if not named and prior and not re.search(r'IMO\s*\d|HAE\s*\d',q,re.I):vessel=next((s for s in ships if s['id']==prior.get('ship')),None)
    start,end=(periods[0].start,periods[0].end) if len(periods)==1 else (prior.get('start'),prior.get('end')) if not periods else (None,None)
    if len(periods)>1:
        return missing('조회할 기간 하나를 지정해 주세요.','Specify one reporting period.')
    if not vessel:
        return missing('조회할 선박 한 척을 지정해 주세요.','Which vessel should I use?','ship')
    records=ctx.db.ship_records(vessel['id'])
    if (whole or len(years)==1) and not periods:
        if len(years)==1:
            start,end=f'{years[0]}-01-01',f'{years[0]}-12-31'
        elif years:
            return missing('조회할 기간을 하나 지정해 주세요.','Specify one reporting period.')
        else:
            dates=[r['date'] for r in records]
            start,end=min(dates,default=None),max(dates,default=None)
    if (not start or not end) and not whole:
        return missing('조회할 기간을 알려 주세요. 전체 기록도 선택할 수 있습니다.','Specify the dates or ask for all records.','period')
    numerals = {'한':1,'두':2,'세':3,'네':4,'다섯':5}
    quantity_q = re.sub(r'(한|두|세|네|다섯)\s*(?=개|건|날)',lambda m:str(numerals[m[1]]),date_text)
    count=re.search(r'(?:상위|하위|top|bottom)\s*(\d+)|(\d+)\s*(?:개|건)(?=만|을|를|의|이|[?.!,\s]|$)',quantity_q,re.I)
    limit=int(count[1] or count[2]) if count else prior.get('limit',1 if ranking or rank and re.search(r'가장|제일|highest|lowest|최다|최소|최대',rank[0],re.I) else 20)
    if not 1<=limit<=100:return missing('표시할 건수는 1~100개로 지정해 주세요.','Select 1 to 100 results.')
    ascending=bool(re.search(r'하위|적|낮|짧|최소|오름차순|bottom|lowest|ascending',rank[0],re.I)) if rank else ranking=='lowest' if ranking else prior.get('ascending',False)
    rule=[float(threshold[1]),threshold[2]] if threshold else prior.get('threshold')
    sample='real' if re.search(r'실제\s*(?:자료|기록|데이터)만|가상.{0,8}제외|exclude sample',q,re.I) else 'sample' if re.search(r'가상.{0,8}만|sample only',q,re.I) else prior.get('sample','all')
    fmt='list' if re.search(r'목록|리스트|list\b',q,re.I) else 'table' if re.search(r'표로|표\s*형식|table',q,re.I) else prior.get('format','table')
    selected=[]
    daily = bool(re.search(r'하루\s*(?:단위|씩)|일별|날짜별|날\s*\d+\s*일|쓴\s*날|높은\s*날|낮은\s*날|(?:많|적|높|낮|짧|긴|든|먹은|썼던)\S*\s*날|\bdays?\b',q,re.I))
    if prior and not re.search(r'일별|날짜|날|건별|기록별|개별|days?|individual',q,re.I):
        daily=prior.get('daily',False)
    skipped = 0
    for r in records:
        if not start<=r['date']<=end:continue
        if sample=='real' and r.get('sample') or sample=='sample' and not r.get('sample'):continue
        required = ('fuel','factor') if metric=='co2' else (metric,)
        if any(r.get(k) is None for k in required):
            skipped += 1
            continue
        v=r['fuel']*r['factor'] if metric=='co2' else r[metric]
        selected.append((r,v))
    if total:
        unit={'distance':'nm','co2':'tCO₂','fuel':'t','speed':'kn'}[metric]
        if metric=='speed':
            return missing('속력은 합산할 수 없습니다. 평균 또는 순위로 질문해 주세요.','Speed cannot be summed. Ask for a speed ranking.')
        count=len(selected)
        days=sorted(r['date'] for r,v in selected)
        notice=f"{vessel['name']} · " + (('all saved records' if en else '전체 저장 기록') if not periods and not years else f'{start} ~ {end}')
        if count:
            value=round(sum(v for _,v in selected),4)
            notice+=f" · {days[0]} ~ {days[-1]} · {count}" + (' records' if en else '건') + f" · {METRICS[metric][int(en)]} {value:,} {unit}"
        elif skipped:
            notice+=' · '+('No measured values.' if en else '합산 가능한 측정값이 없습니다.')
        else:
            notice+=' · '+('No matching records.' if en else '일치하는 기록이 없습니다.')
        if skipped:
            notice += f' · {skipped} ' + ('records missing the metric' if en else '건 측정값 누락')
        if any(r.get('sample') for r,_ in selected):
            notice+=' · '+('Includes sample data.' if en else '가상 예시 기록 포함')
        return save(ctx,{'task':'operation_total','status':'completed','notice':notice},
                    {'method':'rules','route':'operation_total'})
    if daily:
        groups={}
        for r,v in selected:
            groups.setdefault(r['date'],[]).append((r,v))
        selected=[]
        for day,entries in groups.items():
            values=[v for _,v in entries]
            value=sum(values)/len(values) if metric=='speed' else sum(values)
            ids=[r['id'] for r,_ in entries]
            selected.append(({'date':day,'id':ids[0],'recordIds':ids,'sample':any(r.get('sample') for r,_ in entries)},value))
    if rule:
        n,op=rule
        selected=[(r,v) for r,v in selected if {'이상':v>=n,'이하':v<=n,'초과':v>n,'미만':v<n}[op]]
    selected.sort(key=lambda item:(item[1] if ascending else -item[1],item[0]['date'],item[0]['id']))
    show=selected[:limit]
    scope=dict(ship=vessel['id'],start=start,end=end,metric=metric,ascending=ascending,limit=limit,threshold=rule,sample=sample,format=fmt,daily=daily,language=ctx.body['language'])
    result={'scope':scope,'format':fmt,'columns':['Date' if en else '날짜',METRICS[metric][int(en)]],
            'rows':[{'id':r['id'],**({'recordIds':r['recordIds']} if daily else {}),'cells':[r['date'],round(v,4)]} for r,v in show]}
    span=f'{start} ~ {end}' if start else ('All records' if en else '전체 기록')
    note=f"{vessel['name']} · {span} · " +(f'{len(show)} of {len(selected)} matching records.' if en else f'조건에 맞는 기록 {len(selected)}건 중 {len(show)}건.')
    if daily:
        note=f"{vessel['name']} · {span} · " + (f'{len(show)} of {len(selected)} matching days.' if en else f'조건에 맞는 {len(selected)}일 중 {len(show)}일.')
    if skipped:
        note += f' · {skipped} ' + ('records missing the metric' if en else '건 측정값 누락')
    if any(r.get('sample') for r,v in show):note+=' '+('Includes sample data.' if en else '가상 예시 기록을 포함합니다.')
    return save(ctx,{'task':'operations_selection','status':'completed','notice':note,'recordSelection':result},{'method':'rules','route':'operations_selection'})
