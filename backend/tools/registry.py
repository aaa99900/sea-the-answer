"""Canonical tool definitions and catalogue projections (ADR 0024).

Only read-only tools that run behind the ordinary user permission checks are
registered. Arguments are suggestions from the model: they are validated here
and resolved against registered ships, documents and ports by the dispatcher.
"""
from dataclasses import dataclass
import json
from typing import Literal

from pydantic import ValidationError

from .schemas import (
    Args, DatasetStatusArgs, AisStatusArgs, OperationsArgs, PositionArgs,
    MrvArgs, CombinedArgs, PortArgs, SelectedDocumentArgs, EmissionsArgs,
    VoyageTimeArgs, ClarifyArgs, NoArgs, DeclineArgs, VesselListArgs,
)


class ToolCallError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class HttpTool:
    """Existing calculator API vocabulary; generated from the same registration."""
    description: str
    inputs: dict[str, str]
    aliases: dict[str, str]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[Args]
    kind: Literal['data', 'control']
    action: str = ''
    http: HttpTool | None = None


@dataclass(frozen=True)
class Call:
    tool: Tool
    args: Args


DOCUMENTS_ONLY = 'answer_from_documents'
TOOLS = {tool.name: tool for tool in (
    Tool(DOCUMENTS_ONLY, '용어 정의·규정·기준·절차 설명처럼 검색된 해사 문서만으로 답할 질문일 때 쓴다. 데이터 조회·계산이 필요 없을 때.',
         NoArgs, 'control'),
    Tool('get_dataset_status', '서버에 등록된 해사 자료(AIS·MRV·DWT·Noon·운항기록·문서·항만)의 유무·건수·출처·수집일을 확인한다. '
         'IMO 번호로 특정 선박의 MRV·DWT 자료 유무도 확인한다.',
         DatasetStatusArgs, 'data'),
    Tool('list_vessels', '등록된 선박 목록이나 IMO 번호 예시를 조회한다. 실제 저장된 선박명·IMO·선종·DWT를 보여준다. '
         '"등록된 IMO 번호 10개 예시"처럼 번호가 질문에 없어도 목록을 조회한다.', VesselListArgs, 'data'),
    Tool('get_ais_catalog_status', '연결된 AIS 수집본의 관측 수와 특정 선박의 관측 여부를 확인한다.', AisStatusArgs, 'data'),
    Tool('summarize_operations', '등록 선박의 기간별 일별 운항기록(연료·CO2·거리)을 합계·비교한다.', OperationsArgs, 'data', action='operations_summary'),
    Tool('get_last_recorded_position', '등록 선박의 기록 위치·기록 시각·실제/가상 자료 구분을 알려준다. '
         '질문에 날짜가 있으면 서버가 그 날짜의 위치만 조회하고, 날짜가 없으면 마지막 완료 기록을 조회한다. '
         '현재 위치 추정·실시간 추적은 아니다.', PositionArgs, 'data'),
    Tool('calculate_mrv_reference', 'MRV 보고 자료로 연도별 참고 탄소집약도를 계산한다(여러 연도 비교 포함). '
         '탄소집약도·MRV 참고값만 물을 때 쓴다. 질문에 있는 IMO 번호로 공개 원자료를 조회할 수 있다. 공식 CII 등급이 아니다.',
         MrvArgs, 'data', action='mrv_reference'),
    Tool('calculate_operations_and_mrv', '일별 운항 실적(연료·CO2·거리 합계)과 MRV 참고 탄소집약도를 함께 계산한다. '
         '질문이 운항 실적과 탄소집약도를 둘 다 명시적으로 요청할 때만 쓴다.', CombinedArgs, 'data', action='combined'),
    Tool('compare_port_conditions', '선박 제원과 항구 선석의 공개 제한값(길이·폭·흘수)을 비교한다. 입항 허가 판정이 아니다.',
         PortArgs, 'data'),
    Tool('ask_selected_documents', '사용자가 문서 제목을 대며 "그 문서만 근거로" 답하라고 할 때, 그 문서 안에서만 근거를 찾아 답한다.',
         SelectedDocumentArgs, 'data', action='selected_document'),
    Tool('calculate_emissions', '질문에 주어진 연료량·배출계수·DWT·거리로 배출량과 단순 집약도를 계산한다.', EmissionsArgs, 'data',
         http=HttpTool('입력한 연료와 배출계수로 배출량 및 단순 집약도를 계산합니다.',
                       {'fuel': 't, 0..1e7', 'factor': 'tCO2/t fuel, >0..10', 'dwt': 't, >0..1e7', 'distance': 'nm, >0..1e7'},
                       {'fuel': 'fuel_t', 'factor': 'factor', 'dwt': 'dwt', 'distance': 'distance_nm'})),
    Tool('voyage_time', '질문에 주어진 UTC 시각과 선내 시차로 항해 시간을 계산한다.', VoyageTimeArgs, 'data',
         http=HttpTool('UTC 시각과 오프셋을 사용해 항해 시간을 계산합니다.',
                       {'start': 'ISO 8601 UTC (...Z)', 'end': 'ISO 8601 UTC (...Z)',
                        'before': 'UTC offset minutes', 'after': 'UTC offset minutes'},
                       {'start': 'start', 'end': 'end', 'before': 'start_offset_min', 'after': 'end_offset_min'})),
    Tool('request_clarification', '어떤 작업이나 대상(선박·기간·문서·항구)인지 불명확해 되물어야 할 때 쓴다.', ClarifyArgs, 'control'),
    Tool('decline_request', '실시간 연속 추적·기상·예측·자료 변경·입항 승인·해사 업무와 무관한 요청일 때 쓴다.', DeclineArgs, 'control'),
)}


def _inline(schema):
    """Inline $defs and drop titles: small models handle flat schemas more reliably."""
    definitions = schema.pop('$defs', {})

    def resolve(node):
        if isinstance(node, dict):
            if '$ref' in node:
                return resolve(dict(definitions[node['$ref'].rsplit('/', 1)[1]]))
            return {k: resolve(v) for k, v in node.items() if k != 'title'}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node
    return resolve(schema)


def parameters(tool):
    return _inline(tool.args.model_json_schema())


def model_tools():
    return [{'type': 'function', 'function': {'name': t.name, 'description': t.description, 'parameters': parameters(t)}}
            for t in TOOLS.values()]


def catalog():
    return [{'name': t.name, 'description': t.description, 'kind': t.kind, 'parameters': parameters(t)}
            for t in TOOLS.values()]


def http_catalog():
    """Preserve /api/tools.tools without maintaining another set of definitions."""
    return [{'name': t.name, 'description': t.http.description, 'input': dict(t.http.inputs)}
            for t in TOOLS.values() if t.http is not None]


def http_payload(call):
    """Project validated model arguments to the existing calculator payload."""
    if call.tool.http is None:
        raise ToolCallError('MODEL_UNKNOWN_TOOL')
    return {target: getattr(call.args, source) for target, source in call.tool.http.aliases.items()}


def parse_call(name, arguments):
    tool = TOOLS.get(name) if isinstance(name, str) else None
    if tool is None:
        raise ToolCallError('MODEL_UNKNOWN_TOOL')
    if isinstance(arguments, str):
        if len(arguments.encode()) > 4096:
            raise ToolCallError('MODEL_ARGUMENTS_TOO_LARGE')
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except (ValueError, RecursionError):
            raise ToolCallError('MODEL_INVALID_ARGUMENTS') from None
    if not isinstance(arguments, dict):
        raise ToolCallError('MODEL_INVALID_ARGUMENTS')
    # Some models write an absent optional value as the text "None"/"null"; treat it as omitted.
    arguments = {k: v for k, v in arguments.items() if v is not None and v not in ('None', 'null', 'NULL', 'Null')}
    try:
        return tool, tool.args.model_validate(arguments)
    except ValidationError:
        raise ToolCallError('MODEL_INVALID_ARGUMENTS') from None


WORKFLOW_DEFINITIONS = {
    "mrv-analysis": (
        "MRV 참고 탄소집약도 분석",
        "선택 선박의 MRV와 공개 DWT 후보로 참고값을 계산합니다.",
    ),
    "selected-document-answer": (
        "선택 문서 기반 답변",
        "선택한 문서 안에서만 질문의 근거를 찾습니다.",
    ),
    "operation-summary": (
        "운항 실적 요약",
        "앱 일별 운항기록의 연료·배출량·거리를 요약합니다.",
    ),
    "report-draft": (
        "보고서 초안 작성",
        "운항자료와 선택 문서로 검토용 초안을 만듭니다. 저장은 별도입니다.",
    ),
    "checklist": (
        "점검 체크리스트 생성",
        "선택 문서의 근거로 확인 항목 초안을 만듭니다.",
    ),
    "qa-evaluation": (
        "질의·응답 평가",
        "내 저장 응답의 인용·범위·참고값 계약을 검사합니다.",
    ),
}
WORKFLOW_VERSION = "HAEDAP-SKILLS-1.0"


def workflow_catalog():
    return {
        "version": WORKFLOW_VERSION,
        "skills": [
            {
                "id": k,
                "name": v[0],
                "description": v[1],
                "optional_model": k
                in {"selected-document-answer", "checklist", "report-draft"},
                "version": WORKFLOW_VERSION,
            }
            for k, v in WORKFLOW_DEFINITIONS.items()
        ],
    }
