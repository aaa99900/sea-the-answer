from types import SimpleNamespace
from uuid import uuid4

from api import question_requests as req
from api.question_intent import date_slots
from api.question_router import answer_document_request
from test_tool_selection import Store


def test_report_fields_and_advice():
    q='HAE 01 부산항 입항 보고서를 작성해 줘. 선수 흘수 7.5m, 접안 08:30, 연료 사용량 10톤'
    draft=req.report_request(q)
    assert draft['kind']=='arrival' and draft['fuelUsed']=='10'
    assert draft['values']=={'fore':'7.5','port':'부산항','alongside':'08:30'}
    assert req.report_request('입항 보고서를 어떻게 작성해?') is None
    assert req.report_request('입항 보고서를 작성하지 마') is None


def test_source_alias_and_range():
    q='해사 기본 용어집만 인용하고 영어로 답해 줘'
    assert req.document_matches(q,[{'id':'x','title':'(테스트용) 해사 기본 용어집 (한·영)'}])[0][2]=='x'
    assert req.language_request(q)=='en'
    _,periods=date_slots('2026년 9월 22~28일')
    assert (periods[0].start,periods[0].end)==('2026-09-22','2026-09-28')


def test_ranked_records_and_same_session_ship_switch():
    db=Store()
    db.fleet=[{'id':'a','name':'HAE 01'},{'id':'b','name':'HAE 02'}]
    db.ship_records=lambda ship_id:[dict(id=str(i)+s,ship=s,date=f'2026-09-{20+i:02}',fuel=i*2,sample=False) for i in range(1,10) for s in [ship_id]]
    parent=str(uuid4())
    ctx=SimpleNamespace(db=db,user={'id':'crew'},body={'conversationId':parent})
    def capture(ctx,fields,routing):return fields
    q='HAE 01의 2026년 9월 22~28일 운항 기록에서 연료를 가장 많이 쓴 날 3개만 영어 표로 보여줘'
    res=req.record_selection(ctx,q,capture)
    assert [r['cells'][1] for r in res['recordSelection']['rows']]==[16,14,12]
    assert ctx.body['language']=='en'
    db.answers[parent]={**res,'id':parent};db.owners[parent]='crew'
    ctx.body['context']={'previousQueryId':parent}
    other=req.record_selection(ctx,'같은 조건으로 HAE 02도 보여줘',capture)['recordSelection']
    assert other['scope']['ship']=='b' and other['columns'][0]=='Date'
    ctx.user={'id':'stranger'}
    assert req.previous_answer(ctx)=={}


def test_scoped_document_answer_uses_only_resolved_readable_sources():
    db=Store();calls=[]
    db.search=lambda user,q,kind,ids:calls.append(ids) or []
    ctx=SimpleNamespace(db=db,user={'id':'crew'},body={'question':'선박안전법만 인용해줘','language':'ko'})
    docs=[{'id':'doc-a','title':'(테스트용) 선박안전법 (법률 제19134호)'},{'id':'doc-b','title':'운항 매뉴얼'}]
    ans=answer_document_request(ctx,ctx.body['question'],docs)
    assert calls==[['doc-a']] and ans['routing']['documentIds']==['doc-a']
    calls.clear()
    ans=answer_document_request(ctx,'“없는 문서”에서만 찾아줘',docs)
    assert not calls and ans['status']=='needs_input'


def test_draft_continuation_uses_only_the_same_owner_and_readable_evidence():
    db=Store();identifier=str(uuid4())
    db.documents=lambda user:[{'id':'doc-a','title':'검토 지침','active':True}]
    ctx=SimpleNamespace(db=db,user={'id':'crew'},body={'conversationId':identifier,'context':{'previousQueryId':identifier}})
    db.owners[identifier]='crew'
    db.answers[identifier]={'id':identifier,'question':'이전 수치 확인','evidence':[{'id':'c1','document_id':'doc-a'}],
                            'statements':[{'text':'검증 문장','chunkId':'c1'}]}
    draft={'values':{}}
    req.enrich_draft(ctx,draft,'방금 내용으로 보고서를 만들어줘')
    assert draft['sources']==['doc-a'] and '검증 문장' in draft['contextNote']
    db.documents=lambda user:[]
    draft={'values':{}}
    req.enrich_draft(ctx,draft,'방금 내용으로 보고서를 만들어줘')
    assert draft.get('contextNote') is None


def test_explaining_a_form_does_not_open_a_draft():
    assert req.report_request('입항 보고서와 출항 보고서의 차이를 정리해 줘') is None
    assert req.report_request('보고서를 만들지 말고 일일 운항 보고서 내용을 정리해 줘') is None


def test_departure_port_and_next_port_are_separate_fields():
    q='부산항 출항 보고서를 만들어 줘. 이안 17:10, 다음 기항지: 울산항, SOSP 18:00.'
    assert req.report_request(q)['values']==dict(port='부산항',next='울산항',unberth='17:10',sosp='18:00')
    assert 'port' not in req.report_request('출항 보고서를 작성해줘. 다음 기항지: 울산항, 이안 17:10')['values']
