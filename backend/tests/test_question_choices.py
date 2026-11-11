"""Current candidate IDs and form-free operation projections use existing boundaries."""
import pytest
from types import SimpleNamespace
from api import question_workflows as flow
from api.errors import ApiError
from test_question_workflows import DB,ask


def test_duplicate_ship_names_are_resolved_by_candidate_id_or_explicit_imo():
    db=DB();db.fleet[1]['name']=db.fleet[0]['name']
    first=ask(db,'해답호의 2025년 1월 연료 사용량 알려줘')
    assert first['workflow']['clarification']['field']=='ships' and not db.calls
    assert {s['id'] for s in first['workflow']['options']['ships']}=={'a','b'}
    chosen=ask(db,'해답호',{'previousQueryId':first['id']},{'ships':['b']})
    assert chosen['status']=='completed' and db.calls[-1]['ship']=='b'
    by_imo=ask(db,'해답호 IMO 7422881의 2025년 1월 연료 사용량 알려줘')
    assert [s['id'] for s in by_imo['workflow']['scope']['ships']]==['a']


def test_duplicate_document_candidates_keep_versions_and_original_question(monkeypatch):
    db=DB()
    db.documents=lambda user:[{'id':'doc-a','title':'기관 점검 문서','version':'1','reference':'초판'},
                              {'id':'doc-b','title':'기관 점검 문서','version':'2','reference':'개정판'},
                              {'id':'unrelated','title':'다른 문서','version':'1'}]
    seen=[]
    monkeypatch.setattr(flow.skills,'selected_evidence',lambda d,u,b:seen.append((b.question,b.document_ids)) or [])
    monkeypatch.setattr(flow.skills,'evidence_statements',lambda *a:([],'extractive'))
    original='선택한 문서에서 연료 전환 절차 알려줘'
    first=ask(db,original)
    ambiguous=ask(db,'기관 점검 문서',{'previousQueryId':first['id']})
    options=ambiguous['workflow']['options']['documents']
    assert [(d['id'],d['version']) for d in options]==[('doc-a','1'),('doc-b','2')]
    assert not seen
    final=ask(db,'기관 점검 문서',{'previousQueryId':ambiguous['id']},{'document_ids':['doc-b']})
    assert final['workflow']['scope']['document_ids']==['doc-b']
    assert seen==[(original,['doc-b'])]


def test_candidate_choice_rechecks_revoked_document_permission():
    db=DB();first=ask(db,'선택한 문서에서 점검 항목 알려줘')
    db.allowed.remove('doc-b')
    with pytest.raises(ApiError) as error:
        ask(db,'doc-b',{'previousQueryId':first['id']},{'document_ids':['doc-b']})
    assert error.value.status==403


def test_unknown_ship_candidate_is_not_substituted_with_first_ship():
    db=DB();first=ask(db,'우리 배 2025년 1월 연료 사용량 알려줘')
    with pytest.raises(ApiError) as error:
        ask(db,'후보 선택',{'previousQueryId':first['id']},{'ships':['missing']})
    assert error.value.status==400 and not db.calls


def test_ship_edited_after_candidate_display_requires_a_new_question():
    db=DB();first=ask(db,'우리 배 2025년 1월 연료 사용량 알려줘')
    db.fleet[0]['version']+=1
    with pytest.raises(ApiError) as error:
        ask(db,'해답호',{'previousQueryId':first['id']},{'ships':['a']})
    assert error.value.status==409 and not db.calls


def test_decline_ends_confirmation_and_a_later_yes_does_not_start_calculation():
    db=DB();first=ask(db,'해답호 2024년 공식 CII 계산해줘')
    assert first['workflow']['clarification']['field']=='reference_ack'
    declined=ask(db,'아니요',{'previousQueryId':first['id']},{'reference_ack':False})
    assert declined['workflow']['clarification'] is None and not declined['workflow']['results']
    assert ask(db,'네',{'previousQueryId':declined['id']}) is None
    assert not db.calls


@pytest.mark.parametrize('format_word,kind',[('막대그래프로','chart'),('표로','table')])
def test_operation_projections_use_same_single_read_as_totals(format_word,kind):
    db=DB();answer=ask(db,f'해답호 2025년 1월 일별 CO2 배출량을 {format_word} 보여줘')
    assert answer['status']=='completed' and answer['presentation']['type']==kind
    assert answer['operations']['ship']['id']=='a' and len(db.calls)==1
    assert answer['compliance']['status']=='unknown' and answer['compliance']['label']
    if kind=='chart':
        assert answer['presentation']['points'][0]['value']==pytest.approx(31.14)
    else:
        assert float(answer['presentation']['rows'][0]['cells'][2])==pytest.approx(31.14)


def test_chart_clarification_and_month_followup_preserve_metric_without_planner(monkeypatch):
    monkeypatch.setattr(flow.intent,'plan_with_model',lambda *a,**k:pytest.fail('Chart must not call model'))
    db=DB();first=ask(db,'일별 CO2 배출량을 막대그래프로 보여줘',mode='llm')
    assert first['workflow']['clarification']['field']=='ships' and not db.calls
    second=ask(db,'해답호',{'previousQueryId':first['id']})
    assert second['workflow']['clarification']['field']=='periods'
    third=ask(db,'2025년 1월',{'previousQueryId':second['id']})
    assert third['presentation']['chartType']=='bar' and third['presentation']['unit']=='tCO₂'
    fourth=ask(db,'2월은?',{'previousQueryId':third['id']})
    assert fourth['presentation']['points'][0]['label']=='2025-02-01'
    assert fourth['presentation']['points'][0]['value']==pytest.approx(46.71)


def test_chart_never_silently_chooses_first_of_multiple_ships():
    db=DB();first=ask(db,'해답호와 별빛호 2025년 1월 연료 사용량을 그래프로 비교해줘')
    assert first['workflow']['missing']==['ships'] and not db.calls
    second=ask(db,'별빛호',{'previousQueryId':first['id']},{'ships':['b']})
    assert second['presentation']['type']=='chart' and second['operations']['ship']['id']=='b'


def test_chart_auto_language_uses_the_original_request_during_date_clarification():
    db=DB();first=ask(db,'IMO 7422881 show fuel consumption as a bar chart')
    second=ask(db,'2025-01-01 ~ 2025-01-31',{'previousQueryId':first['id']})
    assert second['language']=='en' and second['presentation']['title']=='Fuel'


def test_chart_keeps_the_existing_criterion_document_permission_check():
    db=DB()
    body={'question':'해답호 2025년 1월 연료 사용량을 그래프로 보여줘','task':'auto',
          'criterion':{'confirmed':True,'documentId':'not-readable'}}
    with pytest.raises(ApiError) as error:
        flow.try_answer(SimpleNamespace(db=db,user={'id':'user-a'},body=body))
    assert error.value.status==403
