"""Read stored app and MRV vessel particulars for the chat list tool."""
from itertools import islice
import os
import re

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api import config
from api.ship_context import previous_answer
from .api import create_engine_for
from .port_reference import valid_imo
from .reference_intensity import capacity_problem, positive


SOURCE_LABELS = {'app': '앱 등록 선박', 'mrv': '실제 MRV 연간 보고'}


def requested_scope(ctx, args):
    question = ctx.body['question']
    count = re.search(r'(?<![0-9.])(-?[0-9]+)\s*(?:척|개|건|ships\b|vessels\b|examples\b)', question, re.I)
    limit = int(count[1]) if count else args.limit
    if not 1 <= limit <= 50:
        raise ValueError('선박 목록은 한 번에 1~50척을 요청할 수 있습니다.')

    imo_only = bool(re.search(r'(?<![A-Za-z0-9_])IMO\s*(?:(?:번호\s*)?(?:[0-9]+\s*개|목록|예시)|numbers\b)',
                              question, re.I))
    app = bool(re.search(r'앱\s*(?:에\s*|의\s*|에서\s*)?(?:등록|선박|목록)|운항\s*정보\s*(?:에|화면)|\bapp\b', question, re.I))
    mrv = bool(re.search(r'(?<![A-Za-z0-9_])MRV(?![A-Za-z0-9_])|엠알브이', question, re.I))
    if app and mrv:
        raise ValueError('앱 등록 목록과 MRV 목록 중 하나를 지정해 주세요.')
    if app or mrv:
        return ('app' if app else 'mrv'), limit, imo_only
    if args.source != 'auto':
        return args.source, limit, imo_only

    prior = previous_answer(ctx) or {}
    previous_list = (prior.get('vesselList') or {}).get('source')
    if previous_list in SOURCE_LABELS:
        return previous_list, limit, imo_only
    action = ((prior.get('workflow') or {}).get('scope') or {}).get('action')
    datasets = {item.get('dataset') for item in (prior.get('dataStatus') or {}).get('datasets', [])}
    mrv_context = action == 'mrv_reference' or bool(datasets and datasets <= {'mrv', 'dwt'})
    source = 'mrv' if imo_only or mrv_context else 'app'
    return source, limit, imo_only


def app_vessels(db, imo_only):
    seen = set()
    for ship in db.ships():
        imo = re.sub(r'^IMO\s*[:#]?\s*', '', str(ship.get('imo') or '').strip(), flags=re.I)
        imo = imo if valid_imo(imo) else None
        if imo_only:
            if imo is None or imo in seen:
                continue
            seen.add(imo)
        dwt = positive(ship.get('dwt'))
        yield {'name': ship.get('name'), 'imo': imo, 'ship_type': ship.get('type'), 'sample': bool(ship.get('sample')),
               'reporting_year': None, 'dwt_t': str(dwt) if dwt is not None else None,
               'dwt_source': 'app' if dwt is not None else None}


def mrv_vessels(engine, limit):
    query = text('''SELECT v.imo_number, r.vessel_name, r.ship_type, r.reporting_year, r.dwt_t,
                           c.candidate_dwt_t, c.capacity_status, c.source_json
        FROM maritime_data.vessels v
        JOIN LATERAL (
            SELECT vessel_name, ship_type, reporting_year, dwt_t
            FROM maritime_data.annual_reports
            WHERE vessel_id = v.vessel_id AND quality_status = 'VALID' AND report_type <> 'PARTIAL'
            ORDER BY reporting_year DESC, aggregate_eligible DESC, record_id LIMIT 1
        ) r ON true
        LEFT JOIN maritime_data.capacity_candidates c ON c.vessel_id = v.vessel_id AND c.imo_number = v.imo_number
        WHERE v.data_origin = 'REAL' AND v.vessel_id = 'REAL:IMO:' || v.imo_number
        ORDER BY (r.dwt_t > 0 OR (c.candidate_dwt_t > 0 AND c.capacity_status <> 'CONFLICT_OVER_5_PERCENT')) IS TRUE DESC,
                 v.vessel_id''')
    items = []
    with engine.connect() as connection, connection.begin():
        connection.execute(text('SET TRANSACTION READ ONLY'))
        connection.execute(text("SET LOCAL statement_timeout='5s'"))
        # Some legacy imports only verified the number format. Stream until the requested
        # number of checksum-valid identities is collected, without materializing the fleet.
        with connection.execution_options(yield_per=limit).execute(query) as result:
            for row in result.mappings():
                if not valid_imo(row['imo_number']):
                    continue
                dwt = positive(row['dwt_t'])
                source = 'mrv_report' if dwt is not None else None
                if dwt is None and row['capacity_status'] is not None and capacity_problem(row) is None:
                    dwt, source = row['candidate_dwt_t'], 'public_candidate'
                items.append({'name': row['vessel_name'], 'imo': row['imo_number'], 'ship_type': row['ship_type'],
                              'reporting_year': row['reporting_year'], 'dwt_t': str(dwt) if dwt is not None else None,
                              'dwt_source': source, 'sample': False})
                if len(items) == limit:
                    break
    return items


def answer(ctx, args):
    try:
        source, limit, imo_only = requested_scope(ctx, args)
    except ValueError as exc:
        return {'task': 'clarification', 'status': 'needs_input', 'notice': str(exc)}

    items = []
    status = 'completed'
    notice = ''
    if source == 'app':
        items = list(islice(app_vessels(ctx.db, imo_only), limit + 1))
    else:
        engine = None
        try:
            engine = create_engine_for(os.getenv('MARITIME_DATA_DATABASE_URL') or config.database_url())
            items = mrv_vessels(engine, limit + 1)
        except (SQLAlchemyError, ValueError):
            status = 'unavailable'
            notice = '현재 MRV 선박 자료에 연결할 수 없습니다.'
        finally:
            if engine is not None:
                engine.dispose()

    if status == 'completed' and not items:
        status = 'empty'
        notice = '선택한 자료에서 IMO 번호가 확인된 선박을 찾지 못했습니다.' if imo_only else '선택한 자료에서 표시할 선박을 찾지 못했습니다.'
    return {'task': 'vessel_list', 'status': status, 'notice': notice, 'vesselList': {
        'source': source, 'source_label': SOURCE_LABELS[source], 'limit': limit,
        'has_more': len(items) > limit, 'items': items[:limit]}}
