"""Opt-in HTTP/PostgreSQL calculator continuations; planner/search are fixtures.

These exercise actual auth, conversation ownership, query/tool input persistence
and rollback. They do not measure real model routing or answer quality.
"""
import json

from fastapi.testclient import TestClient
import pytest

from api import config, main, question_router
from rag_postgres_support import login
from test_workflow_skills import database
from tools import registry


FIRST = '연료 100t, 배출계수 3.114, DWT 30000t, 거리 2000nm로 배출량과 참고 집약도를 계산해줘'
FOLLOW = '연료만 200t로 바꾸면?'
RESUME = '아까 배출량 계산에서 연료만 200t로 바꾸면?'
UNRELATED = '황산화물 규제가 무엇인가요?'
INPUT = {'fuel': 100, 'factor': 3.114, 'dwt': 30000, 'distance': 2000}


@pytest.fixture
def calculations(database, monkeypatch):
    monkeypatch.delenv('HAEDAP_QUESTION_ROUTER', raising=False)
    monkeypatch.setattr(config, 'llm_settings', lambda:
        config.LLMSettings('http://fixture.invalid/v1', 'fixture-model', ''))
    monkeypatch.setattr(type(database), 'search', lambda *a, **k: [])
    calls = []

    def plan(question, **kwargs):
        calls.append(question)
        if question == FIRST:
            return [registry.Call(*registry.parse_call('calculate_emissions', {
                'fuel_t': INPUT['fuel'], 'factor': INPUT['factor'],
                'dwt': INPUT['dwt'], 'distance_nm': INPUT['distance'],
            }))]
        if question == UNRELATED:
            return []
        raise AssertionError('A calculator revision must use stored inputs, not guessed model arguments')

    monkeypatch.setattr(question_router.tool_planner, 'plan', plan)
    client = TestClient(main.app, base_url='http://localhost:5173')
    return client, login(client, 'crew'), calls


def post(client, headers, question, parent=None, *, conversation=None, expected=200):
    body = {'question': question, 'task': 'auto', 'context': {}}
    if parent:
        body['conversationId'] = conversation or parent.get('conversationId', parent['id'])
        body['context']['previousQueryId'] = parent['id']
    response = client.post('/api/ask', headers=headers, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def counts(database):
    return tuple(database.one('SELECT count(*) AS n FROM ' + table)['n']
                 for table in ('queries', 'tool_runs'))


def assert_recalculation(database, answer, first):
    run = answer['toolRuns'][0]
    assert run['name'] == 'calculate_emissions'
    assert run['emission'] == pytest.approx(622.8)
    assert run['intensity'] == pytest.approx(10.38)
    assert run['officialCiiRating'] is None
    assert run['id'] != first['toolRuns'][0]['id']
    stored = database.one('SELECT input FROM tool_runs WHERE id=%s', (run['id'],))['input']
    assert stored == {**INPUT, 'fuel': 200}
    original = database.one('SELECT input FROM tool_runs WHERE id=%s',
                            (first['toolRuns'][0]['id'],))['input']
    assert original == INPUT
    owner = database.one('SELECT owner FROM query_owner WHERE id=%s', (answer['id'],))['owner']
    assert owner == database.one("SELECT id FROM users WHERE username='crew'")['id']


def test_real_sql_replaces_only_fuel_and_preserves_original_run(database, calculations):
    client, headers, planned = calculations
    first = post(client, headers, FIRST)
    second = post(client, headers, FOLLOW, first)
    assert_recalculation(database, second, first)
    assert planned == [FIRST]
    turns = client.get('/api/conversations/' + first['id']).json()['turns']
    assert len(turns) == 2
    assert turns[1]['answer']['toolRuns'][0]['emission'] == pytest.approx(622.8)


def test_real_sql_finds_earlier_calculation_after_an_unrelated_turn(database, calculations):
    client, headers, planned = calculations
    first = post(client, headers, FIRST)
    unrelated = post(client, headers, UNRELATED, first)
    second = post(client, headers, RESUME, unrelated)
    assert_recalculation(database, second, first)
    assert second['conversationId'] == first['id']
    assert planned == [FIRST, UNRELATED]


def test_real_sql_never_borrows_a_calculation_from_another_conversation(database, calculations):
    client, headers, _ = calculations
    first = post(client, headers, FIRST)
    other_conversation = post(client, headers, UNRELATED)
    before = database.one('SELECT count(*) AS n FROM tool_runs')['n']
    answer = post(client, headers, RESUME, first, conversation=other_conversation['id'])
    assert answer['status'] == 'needs_input'
    assert not answer['toolRuns']
    assert first['toolRuns'][0]['id'] not in json.dumps(answer)
    assert database.one('SELECT count(*) AS n FROM tool_runs')['n'] == before


def test_real_http_rejects_other_owners_conversation_and_parent(database, calculations):
    client, headers, _ = calculations
    first = post(client, headers, FIRST)
    admin = TestClient(main.app, base_url='http://localhost:5173')
    admin_headers = login(admin, 'admin')
    before = counts(database)
    post(admin, admin_headers, RESUME, first, expected=404)
    assert counts(database) == before
    own = post(admin, admin_headers, UNRELATED)
    answer = post(admin, admin_headers, RESUME, first, conversation=own['id'])
    assert answer['status'] == 'needs_input' and not answer['toolRuns']
    assert first['toolRuns'][0]['id'] not in json.dumps(answer)
    assert database.one('SELECT count(*) AS n FROM tool_runs')['n'] == before[1]


def test_real_sql_rolls_back_recalculation_if_account_is_revoked(database, calculations, monkeypatch):
    client, headers, _ = calculations
    first = post(client, headers, FIRST)
    before = counts(database)
    original = type(database).calculate_emissions
    crew = database.one("SELECT id FROM users WHERE username='crew'")['id']

    def revoked(workspace, payload):
        result = original(workspace, payload)
        workspace.run('UPDATE users SET active=false WHERE id=%s', (crew,))
        return result

    monkeypatch.setattr(type(database), 'calculate_emissions', revoked)
    post(client, headers, FOLLOW, first, expected=401)
    assert counts(database) == before
