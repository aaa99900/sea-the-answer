"""Run one validated model tool call with the existing executors (ADR 0024).

Model arguments are wording, not identifiers: ships, documents and ports are
resolved here against registered records, dates by the existing date parser.
"""
import json
import re
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import ValidationError

from api import dataset_status, navigation_query, question_intent as intent, question_workflows as flow
from api.validation import utc_now
from .workflows import projected_record as projected
from .registry import http_payload
from api.ship_identity import resolve_ship_name
from api.ship_context import calendar_defaults, previous_answer, previous_position
from .position_records import select_record, as_of, end_of_day
from . import vessel_list

CLARIFY = {'task': '확인할 작업', 'ships': '선박', 'periods': '기간', 'years': '보고 연도', 'documents': '문서', 'ports': '항구'}
DECLINE = {
    'realtime_position': '실시간 연속 추적은 지원하지 않습니다. 운항기록에 저장된 마지막 위치는 선박 이름과 함께 물어 확인할 수 있습니다.',
    'weather': '기상·해상 상태 정보는 제공하지 않습니다.',
    'forecast': '미래 수치 예측은 제공하지 않습니다. 기록된 실적의 합계·비교는 확인할 수 있습니다.',
    'data_change': '질문으로 자료를 등록·수정·삭제할 수 없습니다. 해당 관리 화면을 사용해 주세요.',
    'entry_approval': '실제 입항 가능·불가 판정은 제공하지 않습니다. 공개 선석 제한값과의 참고 비교는 확인할 수 있습니다.',
    'off_topic': '해사 업무와 관련된 질문만 지원합니다.',
}


class ArgumentError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def compact(value):
    return re.sub(r'\s+', '', str(value or '').casefold())


def mentions(call):
    args = call.args
    values = []
    for field in ('ship_mentions', 'port_mentions', 'document_mentions'):
        values += list(getattr(args, field, []) or [])
    for field in ('ship_mention', 'berth_mention'):
        values.append(getattr(args, field, '') or '')
    return [v for v in values if v.strip()]


def source_text(question, summary=None):
    return compact(question) + compact(json.dumps(summary or {}, ensure_ascii=False))


def check_mentions(call, question, summary=None):
    """Every ship, port, berth or document name the model passes must be wording the user actually used."""
    source = source_text(question, summary)
    if any(compact(value) not in source for value in mentions(call)):
        raise ArgumentError('MODEL_ARGUMENT_NOT_IN_QUESTION')


def period_source(call, question, summary=None):
    """Return (text for the existing date parser, origin).

    The model's period wording is used only when the user actually wrote it. A paraphrase
    (e.g. "지난달" -> "마지막 달") falls back to parsing the original question.
    """
    text = (getattr(call.args, 'period_text', '') or '').strip()
    # A new explicit date always overrides dates remembered by the model.
    if re.search(r'\d{4}-\d{2}-\d{2}|\d+\s*[년월일]|오늘|어제|그제|지난|이번|올해|작년|전날',question):
        return question, 'question'
    if not text:
        return '', 'none'
    if compact(text) in source_text(question, summary):
        return text, 'model'
    return question, 'question'


def resolve_ship(mention, question, ships):
    """Complete a shortened ship name only when exactly one registered ship's full name is in the question.

    Observed 2026-11-12: "가상 선박 해답 2호 · 왕복 시나리오" came back as "가상 선박 해답 2호".
    """
    try:
        resolved = resolve_ship_name(mention, ships)
    except ValueError:
        # Let the existing executor request disambiguation, rather than choosing a ship.
        return mention
    if resolved is not None:
        return resolved
    value = compact(mention)
    if not value or any(compact(s['name']) == value or compact(s.get('imo')) == value.removeprefix('imo')
                        for s in ships):
        return mention
    found = [s for s in ships if value in compact(s['name']) and compact(s['name']) in compact(question)]
    return found[0]['name'] if len(found) == 1 else mention


def save(ctx, fields):
    q = ctx.body['question']
    language = ctx.body.get('language', 'auto')
    if language == 'auto':
        language = 'ko' if re.search(r'[가-힣]', q) else 'en'
    answer = {'id': str(uuid4()), 'question': q, 'task': 'tool', 'language': language, 'generation': 'tool',
              'status': 'completed', 'notice': '', 'statements': [], 'evidence': [], 'toolRuns': [], 'warnings': [],
              'reportSuggested': False, **fields}
    ctx.db.run('INSERT INTO queries VALUES(%s,%s,%s,%s)', (answer['id'], q, Jsonb(answer), utc_now()))
    ctx.db.run('INSERT INTO query_owner VALUES(%s,%s)', (answer['id'], ctx.user['id']))
    ctx.db.audit(ctx.user, 'query', '질의', answer['id'], {'question': q, 'task': answer['task']})
    return answer


def clarification(ctx, code, notice):
    return save(ctx, {'task': 'clarification', 'status': 'needs_input', 'notice': notice, 'warnings': [code]})


def continuation_request(ctx, tool, missing):
    question = ctx.body['question']
    prior = previous_answer(ctx)
    old = prior.get('continuation', {}) if prior else {}
    if prior and prior.get('status') == 'needs_input' and isinstance(old.get('question'), str):
        try:
            if resolve_ship_name(question.strip(' \t\n.!?。'), ctx.db.ships()):
                question = old['question']
        except ValueError:
            pass
    return {'question': question, 'tool': tool, 'missing': list(missing)}


def workflow(ctx, action, args, period=None):
    q = ctx.body['question']
    current = ctx.db.ships()
    prior = flow.previous(ctx, current) if (ctx.body.get('context') or {}).get('previousQueryId') else None
    parent = prior[0]['id'] if prior else None
    routing = {'method': 'model_tools', 'model_attempted': True}
    scope = flow.Scope(action=action)
    earlier = prior[1] if prior and prior[1].action == action else None
    try:
        if action == 'selected_document':
            documents = ctx.db.documents(ctx.user)
            ids = []
            for mention in args.document_mentions:
                found = [d['id'] for d in documents if compact(d['title']) == compact(mention)]
                if len(found) != 1:
                    return flow.save(ctx, scope, 'needs_input', '', ['document_ids'], routing, parent=parent)
                ids.append(found[0])
            scope.document_ids = list(dict.fromkeys(ids))
            scope.document_question = q
            return flow.execute(ctx, scope, routing, parent)
        text = (args.period_text if period is None else period).strip()
        year, month = calendar_defaults(earlier.periods, earlier.years) if earlier else (None, None)
        if not text and not earlier:
            previous = previous_answer(ctx)
            continuation = previous.get('continuation', {}) if previous else {}
            bare = q.strip(' \t\n.!?。')
            if (previous and previous.get('task') == 'clarification' and resolve_ship_name(bare, current)
                    and intent.classify(continuation.get('question', '')) == action):
                text = continuation['question']
        years, periods = intent.date_slots(text, today=intent.local_today(), default_year=year,
                                          default_month=month) if text else ([], [])
        # Remove explicitly excluded single dates; never silently include an excluded day.
        excluded = []
        for match in re.finditer(r'((?:\d{4}년\s*)?(?:\d{1,2}월\s*)?\d{1,2}일)[은는을를\s]*(?:제외|빼고|말고)', q):
            _, days = intent.date_slots(match[1], default_year=year, default_month=month)
            excluded.extend(p.start for p in days)
        if excluded:
            if any(p.start != p.end and any(p.start <= d <= p.end for d in excluded) for p in periods):
                raise ValueError('제외 날짜를 뺀 조회 날짜 범위를 최대 두 개로 알려 주세요.')
            periods = [p for p in periods if p.start not in excluded]
            if not periods:
                raise ValueError('제외 후 조회할 날짜가 없습니다. 조회할 날짜를 다시 알려 주세요.')
        if years:
            scope.years = years
        if periods:
            scope.periods = periods
        elif years and action in ('operations_summary', 'combined'):
            scope.periods = [intent.Period(start=f'{y}-01-01', end=f'{y}-12-31') for y in years]
        if not text and earlier:
            scope.years, scope.periods = earlier.years, earlier.periods
        if not flow.set_source_scope(scope, q):
            prior_imos = earlier.source_imos if earlier else []
            names = [resolve_ship(m, q, current) for m in args.ship_mentions
                     if compact(m).removeprefix('imo').lstrip(':#') not in prior_imos]
            ships = flow.explicit_ships(q, current)
            if not ships and names:
                ships = flow.explicit_ships(' '.join(names), current, names)
            if ships:
                scope.ships = [flow.snapshot(s) for s in ships]
            elif prior_imos:
                scope.source_imos = prior_imos
            elif earlier and earlier.ships:
                scope.ships = earlier.ships
            else:
                selected = (ctx.body.get('context') or {}).get('ship')
                scope.ships = [flow.snapshot(s) for s in current if s['id'] == selected]
        if action == 'operations_summary' and args.display != 'text':
            scope.presentation_question = q
        if action in ('mrv_reference', 'combined'):
            earlier = prior[1] if prior and prior[1].action in ('mrv_reference', 'combined') else None
            prompted = bool(earlier and prior[0]['workflow'].get('missing', [None])[:1] == ['reference_ack'])
            # An explicit reference request comes from the user, never from the model flag alone.
            explicit_reference = bool(scope.source_imos and flow.accepts_reference(q))
            scope.reference_ack = explicit_reference or bool(args.accept_reference and prompted) or bool(earlier and earlier.reference_ack)
        result = flow.execute(ctx, scope, routing, parent)
        if result.get('status') == 'needs_input':
            result['continuation'] = continuation_request(ctx, '',
                                                        result.get('workflow', {}).get('missing', []))
        return result
    except (ValueError, ValidationError) as exc:
        try:
            scope = flow.Scope.model_validate(scope.model_dump())
        except (ValueError, ValidationError):
            scope = flow.Scope(action=action)
        notice = str(exc)[:300] if not isinstance(exc, ValidationError) else '선박·기간·연도 입력 형식을 확인해 주세요.'
        if any(word in notice for word in ('day is out of range', 'month must be', 'year ')):
            notice = '존재하지 않는 날짜입니다. 연도·월·일을 확인해 주세요.'
        return flow.save(ctx, scope, 'needs_input', notice, flow.missing_fields(scope), routing, parent=parent)


def utc_today():
    return datetime.now(timezone.utc).date().isoformat()


def last_position(ctx, args):
    q = ctx.body['question']
    current = ctx.db.ships()
    prior = previous_position(ctx, current)
    try:
        names = [resolve_ship(m, q, current) for m in args.ship_mentions]
        ships = flow.explicit_ships(q, current)
        if not ships and names:
            ships = flow.explicit_ships(' '.join(names), current, names)
    except ValueError as exc:
        return clarification(ctx, 'QUESTION_SCOPE_REQUIRED', str(exc)[:300])
    if not ships:
        selected = (ctx.body.get('context') or {}).get('ship')
        if not selected and prior:
            selected = prior['ship']['id']
        ships = [s for s in current if s['id'] == selected]
    if len(ships) != 1:
        return clarification(ctx, 'QUESTION_SCOPE_REQUIRED', '위치를 확인할 선박 이름을 한 척만 알려 주세요.')
    ship = ships[0]
    today = utc_today()
    requested = None
    try:
        if re.search(r'\d{1,2}\s*시|\d{1,2}:\d{2}|오전|오후|정오|자정',q):
            return clarification(ctx, 'POSITION_TIME_UNAVAILABLE', '현재 위치 자료는 UTC 일별 기록입니다. 정확한 시각의 위치는 확인할 수 없습니다. 조회할 날짜를 하루만 알려 주세요.')
        old_day = str(prior.get('date') or '') if prior else ''
        year, month = (int(old_day[:4]), int(old_day[5:7])) if old_day else (None, None)
        years, periods = intent.date_slots(q, today=intent.local_today(), default_year=year, default_month=month)
        if not periods and re.search(r'\d+[/.]\d+',q):
            return clarification(ctx, 'POSITION_DATE_REQUIRED', '조회 날짜를 연도·월·일로 알려 주세요. 예: 2026년 11월 9일')
        if len(periods) > 1 or (periods and periods[0].start != periods[0].end) or (years and not periods):
            return clarification(ctx, 'POSITION_DATE_REQUIRED', '위치를 확인할 날짜를 하루만 알려 주세요. 예: 2026년 11월 9일')
        if periods:
            requested = periods[0].start
        elif prior and prior['ship']['id'] == ship['id'] and re.search(r'방금|그\s*위치|기록된|기록\s*시각|실제\s*관측|시뮬레이션',q):
            requested = old_day
    except (ValueError, ValidationError):
        return clarification(ctx, 'POSITION_DATE_REQUIRED', '조회할 날짜의 연도·월·일을 확인해 주세요.')
    through = min(requested, today) if requested else today
    record = select_record(ctx.db.recent_positions(ship['id'], through), today=today, requested=requested)
    if record is None:
        return save(ctx, {'task': 'position', 'status': 'insufficient_evidence',
                          'notice': f"{ship['name']}의 " + (f'{requested} 날짜에 확인 가능한 위치 기록이 없습니다. 다른 날짜의 위치로 대신 답하지 않습니다.' if requested else '운항기록에 저장된 위치가 없습니다.')})
    day = str(record['date'])
    at = as_of(record)
    expected = projected(record)
    sample = bool(ship.get('sample') or record.get('sample'))
    basis = f'{day} 24:00 UTC 기록' if at else f'{day} 운항기록'
    label = f'{requested} 기록 위치' if requested else '마지막 기록 위치'
    notice = (('[예상 기록] ' if expected else '') + f"{ship['name']}의 {label}는 {record['position']}입니다. "
              f"{basis} 기준이며 실시간 추적이 아닙니다." + (' 시뮬레이션 예상값입니다.' if expected else ''))
    warnings = (['PROJECTED_OPERATIONS'] if expected else []) + (['SYNTHETIC_OR_SAMPLE_OPERATIONS'] if sample else [])
    position = {'ship': {k: ship.get(k, '') for k in ('id', 'name', 'imo', 'sample', 'version')}, 'recordId': record['id'],
                'version': record.get('version'), 'date': day, 'asOf': at, 'position': record['position'],
                'note': str(record.get('note') or ''), 'voyage': str(record.get('voyage') or ''),
                'projected': expected, 'sample': sample, 'selection': 'date' if requested else 'latest'}
    return save(ctx, {'task': 'position', 'notice': notice, 'warnings': warnings, 'position': position})


def port_comparison(ctx, args):
    ship = resolve_ship(args.ship_mention, ctx.body['question'], ctx.db.ships()) if args.ship_mention else ''
    conditions = {'filters': [{'kind': f.dimension, 'op': f.op, 'value_m': '%g' % f.value_m} for f in args.filters],
                  'sort': {'kind': args.sort.dimension, 'direction': args.sort.direction} if args.sort else None,
                  'status': args.status_filter}
    ports = ' '.join([*args.port_mentions, *([f'선석 {args.berth_mention}'] if args.berth_mention else [])])
    return navigation_query.try_answer(ctx, planned={'ship_text': ship, 'ports_text': ports,
                                                    'conditions': conditions})


def run(ctx, call, period=None):
    name, args = call.tool.name, call.args
    if call.tool.action:
        return workflow(ctx, call.tool.action, args, period)
    if name == 'list_vessels':
        return save(ctx, vessel_list.answer(ctx, args))
    if name == 'get_dataset_status':
        names = [resolve_ship(m, ctx.body['question'], ctx.db.ships()) for m in args.ship_mentions]
        scope_text = ' '.join([args.period_text if period is None else period, *names]).strip()
        fields = dataset_status.answer(ctx, list(args.datasets), scope_text=scope_text)
        return save(ctx, {'task': 'data_status', **fields})
    if name == 'get_ais_catalog_status':
        names = [resolve_ship(m, ctx.body['question'], ctx.db.ships()) for m in args.ship_mentions]
        return navigation_query.catalog_status_answer(ctx, ctx.body['question'], scope_text=' '.join(names))
    if name == 'get_last_recorded_position':
        return last_position(ctx, args)
    if name == 'compare_port_conditions':
        return port_comparison(ctx, args)
    if name == 'calculate_emissions':
        result = ctx.db.calculate_emissions(http_payload(call))
        return save(ctx, {'toolRuns': [result], 'notice': '질문에 주어진 값으로 계산했습니다. 공식 CII 등급이 아닙니다.'})
    if name == 'voyage_time':
        result = ctx.db.voyage_time(http_payload(call))
        return save(ctx, {'toolRuns': [result], 'notice': '질문에 주어진 UTC 시각과 시차로 계산했습니다.'})
    if name == 'request_clarification':
        labels = '·'.join(CLARIFY[m] for m in args.missing)
        return save(ctx, {'task':'clarification','status':'needs_input','warnings':['QUESTION_SCOPE_REQUIRED'],
            'notice':f'질문을 처리하려면 {labels}을(를) 알려 주세요.',
            'continuation':continuation_request(ctx,name,args.missing)})
    if name == 'decline_request':
        return save(ctx, {'task': 'unsupported', 'status': 'unsupported', 'notice': DECLINE[args.reason],
                          'warnings': ['UNSUPPORTED_REQUEST']})
    raise ArgumentError('MODEL_UNKNOWN_TOOL')
