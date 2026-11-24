"""Calculator continuation through the public router; model replies are fixtures.

Arithmetic and saved query ownership are exercised here. These tests make no
claim about an external model's ability to choose a tool.
"""
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from api import question_router as router
from api.store.tools import ToolStore
from tools import registry
from test_tool_selection import SETTINGS, Store


INITIAL = '연료 100t, 배출계수 3.114, DWT 30000t, 거리 2000nm로 배출량과 참고 집약도를 계산해줘'
INPUT = {'fuel_t': 100, 'factor': 3.114, 'dwt': 30000, 'distance_nm': 2000}


class CalculationStore(Store, ToolStore):
    def __init__(self):
        super().__init__()
        self.calculations = []
        self.runs = {}
        self.plan_calls = []

    def answer(self, user, body, *, evidence=None):
        answer = super().answer(user, body, evidence=evidence)
        self.answers.pop(answer['id'])
        self.owners.pop(answer['id'])
        answer['id'] = str(uuid4())
        self.answers[answer['id']] = deepcopy(answer)
        self.owners[answer['id']] = user['id']
        return answer

    def run(self, sql, args=()):
        super().run(sql, args)
        if sql.startswith('INSERT INTO tool_runs '):
            self.runs[args[0]] = {'id': args[0], 'name': args[1],
                                  'input': deepcopy(args[3].obj), 'output': deepcopy(args[4].obj)}

    def one(self, sql, args=()):
        if 'tool_runs' in sql:
            return deepcopy(self.runs.get(args[0]))
        return super().one(sql, args)

    def _record_calculation(self, name, payload, output):
        self.calculations.append((name, deepcopy(payload)))
        return super()._record_calculation(name, payload, output)

    def all(self, sql, args=()):
        # Match the production ownership/conversation filter, never global latest.
        if 'query_owner' not in sql:
            return []
        anchor, actor, conversation = args[:3]
        if self.owners.get(anchor) != actor or anchor not in self.answers:
            return []
        if self.answers[anchor].get('conversationId', anchor) != conversation:
            return []
        result = []
        entries = list(self.answers.items())
        end = next(i for i, (identifier, _) in enumerate(entries) if identifier == anchor) + 1
        for identifier, answer in reversed(entries[:end]):
            if self.owners.get(identifier) != actor:
                continue
            if answer.get('conversationId', identifier) != conversation:
                continue
            result.append({'id': identifier, 'question': answer['question'], 'response': deepcopy(answer)})
        return result


@pytest.fixture
def conversation(monkeypatch):
    db = CalculationStore()
    plans = {INITIAL: [('calculate_emissions', INPUT)]}
    monkeypatch.setenv('HAEDAP_QUESTION_ROUTER', '')
    monkeypatch.setattr(router.config, 'llm_settings', lambda: SETTINGS)

    def plan(question, **kwargs):
        db.plan_calls.append(question)
        calls = plans.get(question, [('request_clarification', {'missing': ['task']})])
        return [registry.Call(*registry.parse_call(name, json.dumps(args))) for name, args in calls]

    monkeypatch.setattr(router.tool_planner, 'plan', plan)

    def ask(question, previous=None, *, actor='crew-1', conversation_id=None):
        body = {'question': question, 'task': 'auto', 'context': {}}
        if previous:
            body['context']['previousQueryId'] = previous['id']
            body['conversationId'] = conversation_id or previous.get('conversationId', previous['id'])
        elif conversation_id:
            body['conversationId'] = conversation_id
        answer = router.answer(SimpleNamespace(db=db, user={'id': actor, 'role': 'operator'}, body=body))
        # The HTTP handler attaches this after routing; use the same persisted form.
        answer['conversationId'] = body.get('conversationId', answer['id'])
        db.answers[answer['id']] = deepcopy(answer)
        return answer

    return db, plans, ask


def emission(answer):
    assert answer['status'] == 'completed', answer
    return next(run for run in answer['toolRuns'] if run['name'] == 'calculate_emissions')


@pytest.mark.parametrize('question', ['그럼 연료는 2026년 11월 합계로 보여줘', '그럼 거리만 2026년 11월로 바꿔서 조회해줘'])
def test_dated_operations_question_is_not_a_numeric_calculator_edit(conversation, question):
    db, plans, ask = conversation
    first = ask(INITIAL)
    plans[question] = []
    answer = ask(question, first)
    assert db.plan_calls == [INITIAL, question]
    assert len(db.calculations) == 1 and not answer.get('toolRuns')


def test_fuel_only_followup_reuses_factor_dwt_and_distance(conversation):
    db, _, ask = conversation
    first = ask(INITIAL)
    assert emission(first)['emission'] == pytest.approx(311.4)
    result = ask('연료만 200t로 바꾸면?', first)
    assert emission(result)['emission'] == pytest.approx(622.8)
    assert emission(result)['intensity'] == pytest.approx(10.38)
    assert db.calculations[-1] == ('calculate_emissions', {
        'fuel': 200, 'factor': 3.114, 'dwt': 30000, 'distance': 2000})
    assert db.plan_calls == [INITIAL]


@pytest.mark.parametrize('question', [
    '연료만 200t로 바꾸면 CO2는?',
    '연료만200t로바꾸면결과는뭐야?',
])
def test_result_question_suffix_keeps_an_explicit_fuel_replacement(conversation, question):
    db, _, ask = conversation
    first = ask(INITIAL)
    result = ask(question, first)
    assert emission(result)['emission'] == pytest.approx(622.8)
    assert emission(result)['intensity'] == pytest.approx(10.38)
    assert db.calculations[-1][1] == {'fuel': 200, 'factor': 3.114, 'dwt': 30000, 'distance': 2000}
    assert db.plan_calls == [INITIAL]


def test_reference_after_unrelated_turn_finds_calculation_in_same_conversation(conversation):
    db, plans, ask = conversation
    first = ask(INITIAL)
    plans['CII가 뭐야?'] = []
    unrelated = ask('CII가 뭐야?', first)
    assert unrelated['task'] == 'documents'
    result = ask('아까 그 계산에서 연료만 200t로 바꾸면?', unrelated)
    assert emission(result)['emission'] == pytest.approx(622.8)
    assert emission(result)['intensity'] == pytest.approx(10.38)
    assert len(db.calculations) == 2
    assert db.plan_calls == [INITIAL, 'CII가 뭐야?']


def test_chained_changes_retain_last_applied_values(conversation):
    db, _, ask = conversation
    first = ask(INITIAL)
    second = ask('연료만 200t로 바꾸면?', first)
    third = ask('그럼 거리는 1000nm로 바꿔줘', second)
    assert emission(third)['emission'] == pytest.approx(622.8)
    assert emission(third)['intensity'] == pytest.approx(20.76)
    assert db.calculations[-1][1]['fuel'] == 200
    assert db.calculations[-1][1]['distance'] == 1000


@pytest.mark.parametrize('question, field, value, co2, intensity', [
    ('배출계수만 3.2로 바꾸면?', 'factor', 3.2, 320, 320 / 60),
    ('배출계수만 3.2tCO2/t로 바꾸면?', 'factor', 3.2, 320, 320 / 60),
    ('배출계수만 3.2tCO₂/t로 바꾸면?', 'factor', 3.2, 320, 320 / 60),
    ('DWT만 60000t로 바꾸면?', 'dwt', 60000, 311.4, 2.595),
    ('거리만 1000nm로 바꾸면?', 'distance', 1000, 311.4, 10.38),
    ('연료만 0t로 바꾸면?', 'fuel', 0, 0, 0),
])
def test_explicit_field_patch_preserves_all_other_calculator_inputs(conversation, question, field, value, co2, intensity):
    db, _, ask = conversation
    first = ask(INITIAL)
    result = ask(question, first)
    assert emission(result)['emission'] == pytest.approx(co2)
    assert emission(result)['intensity'] == pytest.approx(intensity)
    expected = {'fuel': 100, 'factor': 3.114, 'dwt': 30000, 'distance': 2000}
    expected[field] = value
    assert db.calculations[-1][1] == expected


def test_explicit_new_calculation_uses_its_own_complete_inputs(conversation):
    db, plans, ask = conversation
    first = ask(INITIAL)
    question = '새 질문: 연료 5t, 배출계수 3, DWT 1000t, 거리 500nm 배출량 계산해줘'
    plans[question] = [('calculate_emissions', {'fuel_t': 5, 'factor': 3, 'dwt': 1000, 'distance_nm': 500})]
    result = ask(question, first)
    assert emission(result)['emission'] == 15
    assert emission(result)['intensity'] == 30
    assert db.calculations[-1][1] == {'fuel': 5, 'factor': 3, 'dwt': 1000, 'distance': 500}


@pytest.mark.parametrize('change', ['owner', 'conversation', 'invalid_parent', 'revoked_document'])
def test_followup_cannot_reuse_another_owner_or_conversation_or_unreadable_answer(conversation, change):
    db, _, ask = conversation
    first = ask(INITIAL)
    options = {}
    if change == 'owner':
        options['actor'] = 'other-user'
    elif change == 'conversation':
        options['conversation_id'] = '99999999-9999-4999-8999-999999999999'
    elif change == 'invalid_parent':
        first = {**first, 'id': 'not-a-uuid'}
    else:
        db.allowed.clear()
    answer = ask('연료만 200t로 바꾸면?', first, **options)
    assert answer['status'] != 'completed'
    assert len(db.calculations) == 1
    assert not answer.get('toolRuns')


@pytest.mark.parametrize('question', [
    '연료만 200t로 바꾸면?',
    '아까 그 계산에서 연료만 200t로 바꾸면?',
])
def test_missing_previous_calculation_requests_conditions_without_inventing_them(conversation, question):
    db, _, ask = conversation
    answer = ask(question)
    assert answer['status'] != 'completed'
    assert not db.calculations and not answer.get('toolRuns')


@pytest.mark.parametrize('question', [
    '새 질문: 연료만 200t로 바꾸면?',
    '이전 계산은 무시하고 연료만 200t로 바꿔줘',
    '연료만 -5t로 바꾸면?',
    '거리만 0nm로 바꾸면?',
    '배출계수만 0으로 바꾸면?',
    '연료만 200kg으로 바꾸면?',
    '거리만 1000km로 바꾸면?',
    '거리만 1000미터로 바꾸면?',
    '연료만 200갤런으로 바꾸면?',
    '연료를 200t 또는 300t로 바꾸면?',
    '연료만 200t로 바꾸지 마',
])
def test_new_scope_and_invalid_replacement_never_run_with_silently_reused_values(conversation, question):
    db, _, ask = conversation
    first = ask(INITIAL)
    answer = ask(question, first)
    assert answer['status'] != 'completed'
    assert len(db.calculations) == 1 and not answer.get('toolRuns')


@pytest.mark.parametrize('question', [
    '아까 그 계산에서 연료를 20% 줄이면?',
    '연료를 20t 줄이면?',
    '아까 그 계산에서 연료만 많이 바꾸면?',
    '연료만20t이하로줄이면?',
])
def test_relative_or_unnumbered_edit_requests_an_absolute_value_without_computing(conversation, question):
    db, _, ask = conversation
    first = ask(INITIAL)
    result = ask(question, first)
    assert result['status'] == 'needs_input'
    assert 'CALCULATION_CONTEXT_REQUIRED' in result['warnings']
    assert len(db.calculations) == 1 and not result.get('toolRuns')
    assert db.plan_calls == [INITIAL]


def test_generic_reference_does_not_jump_over_a_more_recent_different_calculator(conversation):
    db, plans, ask = conversation
    first = ask(INITIAL)
    question = '2026-11-01T00:00:00Z부터 2026-11-02T00:00:00Z까지 항해 시간을 계산해줘'
    plans[question] = [('voyage_time', {'start': '2026-11-01T00:00:00Z', 'end': '2026-11-02T00:00:00Z'})]
    newer = ask(question, first)
    assert newer['toolRuns'][0]['name'] == 'voyage_time'
    result = ask('아까 그 계산 다시 해줘', newer)
    assert result['status'] != 'completed'
    assert len(db.calculations) == 2 and not result.get('toolRuns')


def test_explicit_emissions_field_can_find_prior_emissions_across_a_voyage_calculation(conversation):
    db, plans, ask = conversation
    first = ask(INITIAL)
    question = '2026-11-01T00:00:00Z부터 2026-11-02T00:00:00Z까지 항해 시간을 계산해줘'
    plans[question] = [('voyage_time', {'start': '2026-11-01T00:00:00Z', 'end': '2026-11-02T00:00:00Z'})]
    newer = ask(question, first)
    result = ask('아까 배출량 계산에서 연료만 200t로 바꾸면?', newer)
    assert emission(result)['emission'] == pytest.approx(622.8)
    assert emission(result)['intensity'] == pytest.approx(10.38)
    assert len(db.calculations) == 3


def test_repeating_previous_calculation_without_replacement_uses_original_inputs(conversation):
    db, _, ask = conversation
    first = ask(INITIAL)
    result = ask('아까 그 계산 다시 해줘', first)
    assert emission(result)['emission'] == pytest.approx(311.4)
    assert emission(result)['intensity'] == pytest.approx(5.19)
    assert db.calculations[-1][1] == {'fuel': 100, 'factor': 3.114, 'dwt': 30000, 'distance': 2000}


def test_reference_is_anchored_before_later_queries_in_the_same_conversation(conversation):
    db, _, ask = conversation
    first = ask(INITIAL)
    later = ask('배출계수만 4로 바꾸면?', first)
    assert emission(later)['emission'] == 400
    result = ask('연료만 300t로 바꾸면?', first)
    assert emission(result)['emission'] == pytest.approx(934.2)
    assert db.calculations[-1][1]['factor'] == 3.114


def test_explicit_new_question_boundary_stops_old_calculation_lookup(conversation):
    db, plans, ask = conversation
    first = ask(INITIAL)
    question = '새 질문: CII가 뭐야?'
    plans[question] = []
    reset = ask(question, first)
    answer = ask('아까 그 계산에서 연료만 200t로 바꾸면?', reset)
    assert answer['status'] != 'completed'
    assert len(db.calculations) == 1 and not answer.get('toolRuns')


