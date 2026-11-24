"""Regression cases for real users' wording, checked through the normal /ask router."""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from api import question_intent, question_router
from api.errors import ApiError
from test_tool_selection import Store, SETTINGS
from tools import registry


def context(q):
    db=Store()
    db.fleet=[{'id':'ship','name':'HAE 01','version':1}]
    db.document_titles=lambda user:[{'id':str(i),'title':s} for i,s in enumerate(
        ['MEPC.352(78)','IMO · MEPC example','해사 용어집'])]
    db.ship_records=lambda ship:[
        {'id':'a','date':'2024-01-01','fuel':1,'distance':15},
        {'id':'b','date':'2026-09-22','fuel':4,'distance':30},
        {'id':'c','date':'2026-09-22','fuel':5,'distance':40},
        {'id':'d','date':'2026-09-23','fuel':8,'distance':20}]
    db.search=lambda *args:pytest.fail('This question does not require document retrieval')
    return SimpleNamespace(db=db,user={'id':'crew','role':'operator'},body={'question':q})


@pytest.mark.parametrize('q,n',[
    ('문서 중에서 MEPC 관련 문서는 어떤 것들이 있어?',2),
    ('문서함에서 MEPC로 시작하는 파일 좀 보여줘',1),
    ('등록된 것 중 제목에 MEPC가 들어간 문서 목록 좀',2),
    ('ZZZ 관련 문서는 몇 개야?',0)])
def test_permission_filtered_title_list_without_index(q,n):
    a=question_router.answer(context(q))
    assert a['catalog']['term'] in ('MEPC','ZZZ')
    assert len(a['catalog']['items'])==n and a['status']=='completed'


@pytest.mark.parametrize('q',['HAE 01의 모든 운항 기록을 합한다면, 총 운항 거리는?',
    'HAE01이 지금껏 다닌 거리가 몇 해리야?', 'HAE 01의 누적 항해 거리는?'])
def test_all_records_include_multiple_years(q):
    a=question_router.answer(context(q))
    assert a['task']=='operation_total'
    assert all(x in a['notice'] for x in ['2024-01-01','2026-09-23','4건','105 nm'])


def test_empty_operation_scope_has_neutral_status():
    ctx=context('HAE 01의 전체 기록 누적 거리는?')
    ctx.db.ship_records=lambda _: []
    a=question_router.answer(ctx)
    assert a['status']=='completed' and not a['warnings'] and '기록이 없습니다' in a['notice']


@pytest.mark.parametrize('q,value',[
    ('연료를 가장 많이 쓴 날 1개만',9),
    ('연료 사용량 상위 1건만',8),
    ('연료를 가장 많이 쓴 날 1일만',9)])
def test_rank_unit_and_implicit_year(monkeypatch,q,value):
    monkeypatch.setattr(question_intent,'local_today',lambda:date(2026,11,23))
    a=question_router.answer(context('HAE 01의 9월 22~28일 운항 기록에서 '+q+' 영어 표로 보여줘'))
    r=a['recordSelection']
    assert a['language']=='en' and r['scope']['start']=='2026-09-22'
    assert r['rows'][0]['cells'][1]==value


def test_capability_then_create_keeps_explicit_notes_only():
    ctx=context('입항 보고서도 만들 수 있어?')
    a=question_router.answer(ctx)
    assert a['catalog']=={'kind':'report_forms','form':'arrival'}
    parent=str(uuid4())
    ctx.db.answers[parent]={**a,'id':parent}
    ctx.db.owners[parent]=ctx.user['id']
    ctx.body={'question':'그럼 부산항으로 하나 만들어 줘. 특이사항에 “펌프 교체 완료”라고 넣어 줘.',
              'conversationId':parent,'context':{'previousQueryId':parent}}
    draft=question_router.answer(ctx)['reportDraft']
    assert draft['kind']=='arrival' and draft['values']['port']=='부산항'
    assert draft['note']=='펌프 교체 완료' and 'question' not in draft


def test_model_selected_catalog_survives_index_outage(monkeypatch):
    ctx=context('show me materials about ballast')
    monkeypatch.setattr(question_router.config,'llm_settings',lambda:SETTINGS)
    call=registry.Call(*registry.parse_call('list_workspace_items',{'kind':'documents','term':'ballast'}))
    monkeypatch.setattr(question_router.tool_planner,'plan',lambda *a,**kw:[call])
    def offline(*a):raise ApiError(503,'SEARCH_UNAVAILABLE','offline')
    ctx.db.search=offline
    assert question_router.answer(ctx)['catalog']['items']==[]
    monkeypatch.setattr(question_router.tool_planner,'plan',lambda *a,**kw:[])
    with pytest.raises(ApiError,match='offline'):question_router.answer(ctx)


def test_registered_title_lookup_and_history_permissions(monkeypatch):
    import os
    from fastapi.testclient import TestClient
    from api import main
    from rag_postgres_support import configure_api, isolated_workspace, login
    from test_rag_postgres import payload

    dsn=os.getenv('HAEDAP_TEST_DATABASE_URL')
    if not dsn:pytest.skip('isolated PostgreSQL required')
    with isolated_workspace(dsn) as (store,workspace):
        configure_api(monkeypatch,workspace)
        data=payload()
        data['document']['title']='MEPC demo catalogue'
        doc=store.save_document(data)['id']
        client=TestClient(main.app,base_url='http://localhost:5173')
        headers=login(client,'crew')
        question={'question':'MEPC로 시작하는 문서 목록을 보여줘.'}
        response=client.post('/api/ask',headers=headers,json=question)
        assert response.status_code==200,response.text
        answer=response.json()
        answer=answer.get('answer',answer)
        items=answer['catalog']['items']
        assert {'id':doc,'title':'MEPC demo catalogue'} in items
        assert all(item['title'].startswith('MEPC') for item in items)
        from psycopg.types.json import Jsonb
        store.run('INSERT INTO document_meta(id,body) VALUES(%s,%s) ON CONFLICT(id) DO UPDATE SET body=EXCLUDED.body',
                  (doc,Jsonb({'scope':'admin','status':'active'})))
        response=client.get('/api/conversations/'+answer.get('conversationId',answer['id']))
        assert response.status_code==200
        held=response.json()
        assert held['turns'][0]['unavailable']
        assert 'MEPC demo catalogue' not in str(held)
        after=client.post('/api/ask',headers=headers,json=question).json()
        assert after.get('answer',after)['catalog']['items']==[item for item in items if item['id']!=doc]


def test_semantic_metric_hint_cannot_widen_an_unspecified_period(monkeypatch):
    ctx=context('HAE 01이 지금껏 바다에서 얼마나 이동했어?')
    ctx.db.search=lambda *args:[]
    monkeypatch.setattr(question_router.config,'llm_settings',lambda:SETTINGS)
    call=registry.Call(*registry.parse_call('summarize_operations',
        {'ship_mentions':['HAE 01'],'period_text':'지금껏','all_records_metric':'distance'}))
    monkeypatch.setattr(question_router.tool_planner,'plan',lambda *a,**kw:[call])
    assert '105 nm' in question_router.answer(ctx)['notice']
    ctx.body['question']='HAE 01이 바다에서 얼마나 이동했어?'
    assert question_router.answer(ctx)['status']=='needs_input'
