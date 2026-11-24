"""Resolve explicit calculator edits from owned, persisted inputs, never model guesses."""
from dataclasses import dataclass
import math
import re
from uuid import UUID

from pydantic import ValidationError

from api.ship_context import starts_new_scope
from . import registry
from .schemas import EmissionsArgs


NUMBER = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?'
LABELS = {
    'fuel': r'연료(?:\s*(?:사용량|소모량|사용|소모|량))?|fuel(?:\s+(?:used|consumption))?',
    'factor': r'배출\s*계수|emission\s+factor|factor',
    'dwt': r'DWT|재화\s*중량(?:\s*톤수)?',
    'distance': r'항해\s*거리|운항\s*거리|거리|distance(?:_nm)?',
}
CHANGE = re.compile(r'바꾸|바꿔|변경|대신|수정|늘리|줄이|줄여|낮추|높이|라면|이면|그럼|그러면|만\s*' + NUMBER +
                    r'|\b(?:change|replace|instead|what\s+if|recalculate)\b', re.I)
REFERENCE = re.compile(r'(?:아까|앞서|이전|직전|방금|그때|앞의|위의|그)\s*(?:그\s*)?(?:배출량\s*)?계산|'
                       r'(?:아까|앞서|이전|직전|방금).{0,25}(?:연료|배출|집약도)|'
                       r'다시\s*계산|\b(?:previous|earlier|last|same)\s+(?:emissions?\s+)?calculation\b', re.I)
DEFINITION = re.compile(r'정의|무슨\s*뜻|의미|설명|규정|왜|\b(?:define|definition|explain|meaning)\b', re.I)
NEGATED = re.compile(r'(?:바꾸|바꿔|변경|수정|계산).{0,8}(?:지\s*마|하지\s*마|하지\s*않|하지\s*말)|'
                     r'\b(?:do\s+not|don.t|never)\s+(?:change|replace|recalculate)', re.I)
FIELD_MAP = {'fuel': 'fuel_t', 'factor': 'factor', 'dwt': 'dwt', 'distance': 'distance_nm'}
MAX_HISTORY = 50


@dataclass(frozen=True)
class Followup:
    call: registry.Call | None = None
    source: str = ''
    inputs: dict | None = None
    changed: tuple = ()
    error: str = ''


def replacements(question):
    """Read only labelled numeric replacements in the existing calculator's units."""
    values = {}
    spans = []
    for field, label in LABELS.items():
        pattern = (r'(?<![\w])(?:' + label + r')\s*(?:만|만은|을|를|은|는|이|가)?\s*'
                   r'(?:(?:[:=]|을|를)\s*)?(' + NUMBER + r')')
        # Korean particles often have no preceding whitespace ("그럼연료만").
        if field != 'dwt':
            pattern = pattern.replace(r'(?<![\w])', r'(?<![A-Za-z])')
        for match in re.finditer(pattern, question, re.I):
            value = float(match[1].replace(',', ''))
            tail = question[match.end():].lstrip()
            if re.match(r'%|퍼센트', tail):
                raise ValueError('비율 대신 변경 후의 연료·배출계수·DWT·거리 값을 지정해 주세요.')
            if re.match(r'만|천|백|억|kg\b|km\b|킬로|리터|lit[er]+|lbs?\b|miles?\b', tail, re.I):
                raise ValueError('단위는 연료·DWT는 t, 거리는 nm, 배출계수는 tCO₂/t로 지정해 주세요.')
            allowed = {'fuel': r'(?:t|tonnes?|tons?)(?![A-Za-z])|톤',
                       'dwt': r'(?:t|tonnes?|tons?)(?![A-Za-z])|톤',
                       'distance': r'(?:nm|nmi)(?![A-Za-z])|해리',
                       'factor': r'(?:tCO[₂2]/t|tCO[₂2]\s*/\s*t)'}[field]
            unit = re.match('(?:' + allowed + ')', tail, re.I)
            rest = tail[unit.end():].lstrip() if unit else tail
            if re.match(r'이상|이하|초과|미만|정도|쯤|부터|까지|[~±]|(?:at\s+(?:least|most)|over|under|between)\b', rest, re.I):
                raise ValueError('범위나 경계값 대신 변경 후의 정확한 계산값 하나를 지정해 주세요.')
            if re.match(r'(?:만큼\s*)?(?:늘리|늘려|줄이|줄여|낮추|높이|증가|감소)', rest):
                raise ValueError('증감량 대신 변경 후의 계산값을 지정해 주세요.')
            if rest and rest[0].isalpha() and not re.match(
                    r'(?:으로|로|이라면|라면|이면|일\s*때|만|에|은|는|을|를|이|가)(?![A-Za-z])|'
                    r'(?:instead|and|or|to|for|with)\b', rest, re.I):
                raise ValueError('변경할 계산값의 단위를 확인해 주세요.')
            if not math.isfinite(value) or field in values and values[field] != value:
                raise ValueError('각 계산 항목에 유효한 값 하나씩 지정해 주세요.')
            values[field] = value
            unit_end = match.end() + len(question[match.end():]) - len(tail) + (unit.end() if unit else 0)
            spans.append((match.start(), unit_end))
    remainder = question
    for start, end in sorted(spans, reverse=True):
        remainder = remainder[:start] + ' ' * (end - start) + remainder[end:]
    remainder = re.sub(r'(?<![A-Za-z])CO[₂2](?![A-Za-z0-9])', '', remainder, flags=re.I)
    if values and re.search(NUMBER, remainder):
        raise ValueError('변경할 계산 항목마다 값 하나씩 지정해 주세요. 여러 조건은 한 번에 하나씩 계산할 수 있습니다.')
    return values


def _visible(ctx, answer):
    sources = [*answer.get('evidence', []), *answer.get('relatedEvidence', [])]
    return all(ctx.db.can_read_document(ctx.user, e['document_id']) for e in sources
               if isinstance(e, dict) and e.get('document_id'))


def _prior_inputs(ctx, *, emissions_named=False):
    """Bound history to an owned parent in the requested conversation, including its root."""
    parent = (ctx.body.get('context') or {}).get('previousQueryId')
    conversation = ctx.body.get('conversationId')
    try:
        if not isinstance(parent, str) or str(UUID(parent)) != parent.lower() or not conversation:
            return None
    except ValueError:
        return None
    rows = ctx.db.all('''SELECT q.id, q.response FROM queries q
        JOIN query_owner o ON o.id=q.id
        JOIN queries anchor ON anchor.id=%s
        JOIN query_owner ao ON ao.id=anchor.id AND ao.owner=o.owner
        WHERE o.owner=%s AND COALESCE(q.response->>'conversationId',q.id)=%s
        AND COALESCE(anchor.response->>'conversationId',anchor.id)=%s
        AND (q.created_at,q.id)<=(anchor.created_at,anchor.id)
        ORDER BY q.created_at DESC,q.id DESC LIMIT 50''',
        (parent, ctx.user['id'], conversation, conversation))
    for row in rows[:MAX_HISTORY]:
        answer = row.get('response')
        if not isinstance(answer, dict):
            continue
        # Defense in depth for old/malformed saved answers as well as current SQL filtering.
        if answer.get('conversationId', row['id']) != conversation or not _visible(ctx, answer):
            return None
        if answer.get('status') == 'completed':
            calculators = [run for run in answer.get('toolRuns', []) if isinstance(run, dict)
                           and run.get('name') in ('calculate_emissions', 'voyage_time')]
            if calculators and not emissions_named and any(run['name'] != 'calculate_emissions' for run in calculators):
                return None
            runs = [run for run in answer.get('toolRuns', []) if isinstance(run, dict)
                    and run.get('name') == 'calculate_emissions' and isinstance(run.get('id'), str)]
            if len(runs) > 1:
                return None
            if len(runs) == 1:
                run = ctx.db.one('SELECT id,tool AS name,input FROM tool_runs WHERE id=%s', (runs[0]['id'],))
                if not run or run.get('name') != 'calculate_emissions' or not isinstance(run.get('input'), dict):
                    return None
                payload = run['input']
                try:
                    args = EmissionsArgs.model_validate({value: payload[key] for key, value in FIELD_MAP.items()})
                except (KeyError, TypeError, ValidationError):
                    return None
                return row['id'], {key: getattr(args, value) for key, value in FIELD_MAP.items()}
        if starts_new_scope(answer.get('question')):
            break
    return None


def resolve(ctx):
    """Return None for a new question, or an exact continuation/clarification.

    The existing model tool still handles complete new calculations. Only explicit
    edits/references get deterministic continuation, without relaxing its schema.
    """
    question = ctx.body['question']
    if starts_new_scope(question) or DEFINITION.search(question) or NEGATED.search(question):
        return None
    if re.search(r'(?:기록|자료|데이터|문서|보고서).{0,30}(?:수정|바꾸|바꿔|변경|등록|삭제)', question):
        return None
    explicit_reference = bool(REFERENCE.search(question))
    try:
        changed = replacements(question)
    except ValueError as exc:
        return Followup(error=str(exc)) if CHANGE.search(question) or explicit_reference else None
    if re.search(r'뭐야|무엇|\bwhat\s+is\b', question, re.I) and not (changed and CHANGE.search(question)):
        return None
    if not explicit_reference and (not changed or not CHANGE.search(question) or len(changed) == len(FIELD_MAP)):
        return None
    if not changed and CHANGE.search(question) and any(re.search(label, question, re.I) for label in LABELS.values()):
        return Followup(error='변경할 항목과 변경 후의 수치를 지정해 주세요. 예: 연료만 200t로 바꾸면?')
    if not changed and not explicit_reference:
        return None
    prior = _prior_inputs(ctx, emissions_named=bool(changed) or bool(re.search(r'배출|집약도|emission', question, re.I)))
    if prior is None:
        return Followup(error='같은 대화에서 이어받을 배출량 계산을 확인할 수 없습니다. 연료(t)·배출계수·DWT(t)·거리(nm)를 알려 주세요.')
    source, inputs = prior
    inputs.update(changed)
    try:
        tool, args = registry.parse_call('calculate_emissions', {value: inputs[key] for key, value in FIELD_MAP.items()})
    except registry.ToolCallError:
        return Followup(error='변경값을 확인해 주세요. 연료는 0 이상, 배출계수·DWT·거리는 0보다 커야 하며 지원 범위 안이어야 합니다.')
    return Followup(registry.Call(tool, args), source, inputs, tuple(changed))


def annotate(answer, followup):
    inputs = followup.inputs
    answer['calculationContext'] = {'sourceQueryId': followup.source, 'tool': 'calculate_emissions',
                                    'inputs': inputs, 'changedFields': list(followup.changed),
                                    'reusedFields': [key for key in FIELD_MAP if key not in followup.changed]}
    answer['notice'] = ('같은 대화의 이전 계산에서 명시한 값만 바꿔 다시 계산했습니다. '
                        if followup.changed else '같은 대화의 이전 계산 조건으로 다시 계산했습니다. ') + (
        f"연료 {inputs['fuel']:g} t · 배출계수 {inputs['factor']:g} tCO₂/t · DWT {inputs['dwt']:g} t · 거리 {inputs['distance']:g} nm. 공식 CII 등급이 아닙니다.")
