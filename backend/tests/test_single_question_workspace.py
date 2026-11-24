"""Single-turn questions and report upgrades on an isolated, populated workspace."""
import os
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api import config, main, question_intent
from api.report_examples import MARKER, install_report_examples
from rag_postgres_support import configure_api, isolated_workspace, login


def test_workspace_questions_and_examples(monkeypatch):
    dsn = os.getenv('HAEDAP_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('isolated PostgreSQL required')
    monkeypatch.setattr(question_intent,'local_today',lambda:date(2026,11,23))
    with isolated_workspace(dsn) as (store, factory):
        configure_api(monkeypatch,factory)
        client=TestClient(main.app,base_url='http://localhost:5173')
        headers=login(client,'admin')
        assert client.post('/api/operations/example',headers=headers,json={}).status_code==200
        def ask(q):
            response=client.post('/api/ask',headers=headers,json={'question':q})
            assert response.status_code==200,response.text
            return response.json()
        registered=store.operations()
        all_rows=ask('이 프로그램에 저장되어 있는 운항 기록을 알려 줘.')
        assert '21건 중 20건' in all_rows['notice'] and not all_rows['evidence']
        for q in ['이 프로그램에 저장되어 있는 MEPC 문서 중 84번에 해당하는 것만 알려 줘.',
                  'MEPC 제84차 자료 제목 목록']:
            titles=[r['title'] for r in ask(q)['catalog']['items']]
            assert len(titles)==5 and all('84' in t for t in titles)
        assert len(ask('MEPC 84차 부속문서 제목만 보여줘')['catalog']['items'])==3
        for topic in ('통합 질문','문서'):
            assert topic in ask(topic+' 탭을 어떻게 사용할 수 있는지 알려 줘.')['helpLines'][0]
        assert '제목을 검색' in ask('문서 탭을 어떻게 쓸 수 있어?')['helpLines'][0]
        assert len(ask('이 프로그램의 전체 기능을 알려 줘.')['helpLines'])>=4
        for q in ('운항 기록 중에서 HAE 01의 9월 24일부터 27일의 기록을 알려 줘.',
                  'HAE01 9월 24일부터 나흘치 운항 일지를 보여줘'):
            rows=ask(q)['recordSelection']['rows']
            assert [r['cells'][0] for r in rows]==[f'2026-09-{d}' for d in range(24,28)]
        for q in ('운항 기록 중에서 HAE 02의 전체 기록의 이동거리 합을 계산해 줘.',
                  'HAE02가 지금까지 총 몇 마일 다녔어?'):
            total=sum(r['distance'] for r in registered if r['ship']=='hae02')
            assert f'{total:,} nm' in ask(q)['notice']
        top=sorted((r for r in registered if r['ship']=='hae03'),key=lambda r:(-r['fuel']*r['factor'],r['date'],r['id']))[:3]
        for q in ('운항 기록 중에서 HAE 03의 전체 기록 중에서 가장 CO2 배출량이 많았던 기록 3개를 리스트로 보여 줘.',
                  'HAE03 전체 기록 중 탄소 배출이 많았던 세 건을 영어 목록으로 보여 줘'):
            ans=ask(q)
            assert [r['id'] for r in ans['recordSelection']['rows']]==[r['id'] for r in top]
            assert ans['recordSelection']['format']=='list'
            if '영어' in q:
                assert ans['language']=='en'
        user=store.one("SELECT id,role FROM users WHERE username='crew'")
        admin=store.one("SELECT id,role FROM users WHERE username='admin'")
        # Simulate the previous release's three generated examples and a crew-edited copy.
        inputs={'from':'2026-09-22','to':'2026-09-28','template':'noon'}
        old=[store.generate_report(admin,dict(inputs,ship=s['id'])) for s in store.ships()]
        other=store.generate_report(user,dict(inputs,ship='hae01'))
        custom=store.save_report(user,{**other,'text':other['text']+'\n내 메모'})
        store.run('DELETE FROM settings WHERE key=%s',(MARKER,))
        for _ in range(2):
            install_report_examples(store,config.BACKEND_DIR/'knowledge')
        visible=store.reports(user)
        assert {r['body']['formType'] for r in visible if r['status']=='example'}=={'daily','voyage','fuel','arrival','departure'}
        assert len(visible)==6 and custom['id'] in {r['id'] for r in visible}
        assert not {r['id'] for r in old} & {r['id'] for r in store.reports(admin)}
        for r in old:
            assert store.report(r['id'])['text']==r['text']
