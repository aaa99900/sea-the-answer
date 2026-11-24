"""Canonical model-call and workflow input schemas; no API or DB imports."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

DATASETS = ('ais', 'mrv', 'dwt', 'noon', 'operations', 'documents', 'ports')


Mention = Annotated[str, Field(min_length=1, max_length=100)]


PeriodText = Annotated[str, Field(max_length=100)]


class Args(BaseModel):
    model_config = ConfigDict(extra='forbid')


class DatasetStatusArgs(Args):
    datasets: list[Literal[DATASETS]] = Field(min_length=1, max_length=7,
        description='확인할 자료 종류. 질문이 자료 전체를 물으면 모두 넣는다.')
    ship_mentions: list[Mention] = Field(default_factory=list, max_length=1,
        description='질문에 적힌 선박 이름이나 IMO 표기 그대로. 없으면 빈 배열.')
    period_text: PeriodText = Field(default='', description='질문에 적힌 기간 표현 그대로(예: 2024년). 계산하지 않는다.')


class WorkspaceListArgs(Args):
    kind: Literal['documents','report_forms','saved_reports','help_overview','help_chat','help_documents','help_operations','help_reports']
    term: str = Field(default='',max_length=120,description='문서 제목 검색어. 질문에서 그대로 복사.')
    match: Literal['contains','prefix'] = 'contains'


class VesselListArgs(Args):
    source: Literal['auto', 'app', 'mrv'] = Field(default='auto',
        description='앱 등록 선박을 명시하면 app, MRV 보고 선박을 명시하면 mrv. 출처가 없으면 auto.')
    limit: int = Field(default=10, strict=True, ge=1, le=50,
        description='요청한 선박 수. 숫자를 지정하지 않으면 10. 최대 50.')


class AisStatusArgs(Args):
    ship_mentions: list[Mention] = Field(default_factory=list, max_length=1,
        description='질문에 적힌 선박 이름이나 IMO 표기 그대로. 없으면 빈 배열.')


class OperationsArgs(Args):
    rank_by: Literal['','distance','fuel','co2','speed'] = Field(default='',description='상·하위 기록이나 날을 요구할 때의 정렬 지표.')
    rank_order: Literal['highest','lowest'] = 'highest'
    listing: bool = Field(default=False,description='개별 저장 운항 기록 목록 요청. 통계·합계·비교는 false.')

    all_records_metric: Literal['','distance','fuel','co2'] = Field(default='',
        description='전체 저장 기록의 누계만 요청한 경우의 지표. period_text에는 전체 기간을 뜻하는 원문을 복사한다. 날짜 미지정만으로 선택하지 않는다.')
    ship_mentions: list[Mention] = Field(default_factory=list, max_length=2,
        description='질문에 적힌 선박 이름이나 IMO 표기 그대로, 최대 2개.')
    period_text: PeriodText = Field(default='', description='질문에 적힌 기간 표현 그대로(예: 지난달, 2025년 1월과 2월).')
    display: Literal['text', 'table', 'chart'] = Field(default='text', description='표나 차트를 요청했을 때만 table 또는 chart.')


class PositionArgs(Args):
    ship_mentions: list[Mention] = Field(default_factory=list, max_length=1,
        description='질문에 적힌 선박 이름이나 IMO 표기 그대로. 없으면 빈 배열.')


class MrvArgs(Args):
    ship_mentions: list[Mention] = Field(default_factory=list, max_length=2,
        description='질문에 적힌 선박 이름이나 IMO 표기 그대로, 최대 2개.')
    period_text: PeriodText = Field(default='', description='질문에 적힌 보고 연도 표현 그대로(예: 작년, 2024년).')
    accept_reference: bool = Field(default=False,
        description='previous가 참고값 동의를 물었고(missing에 reference_ack) 사용자가 동의하는 답을 했을 때만 true. 그 밖에는 생략.')


class CombinedArgs(Args):
    ship_mentions: list[Mention] = Field(default_factory=list, max_length=2,
        description='질문에 적힌 선박 이름이나 IMO 표기 그대로, 최대 2개.')
    period_text: PeriodText = Field(default='', description='질문에 적힌 기간·연도 표현 그대로.')
    accept_reference: bool = Field(default=False,
        description='previous가 참고값 동의를 물었고(missing에 reference_ack) 사용자가 동의하는 답을 했을 때만 true. 그 밖에는 생략.')


Dimension = Literal['length', 'beam', 'draught']


class PortFilter(Args):
    dimension: Dimension
    op: Literal['>=', '<=', '>', '<', '=']
    value_m: float = Field(gt=0, le=1000)


class PortSort(Args):
    dimension: Dimension
    direction: Literal['asc', 'desc']


class PortArgs(Args):
    ship_mention: str = Field(default='', max_length=100, description='질문에 적힌 선박 표기 그대로. 없으면 빈 문자열.')
    port_mentions: list[Mention] = Field(default_factory=list, max_length=5,
        description='질문에 적힌 항구 이름 그대로. 없으면 빈 배열(제공 항구 전체).')
    berth_mention: str = Field(default='', max_length=40, description='질문에 적힌 선석 번호 그대로. 없으면 빈 문자열.')
    filters: list[PortFilter] = Field(default_factory=list, max_length=3,
        description='공개 선석 제한값(m) 조건. 질문에 명시된 조건만.')
    sort: PortSort | None = Field(default=None, description='제한값 정렬을 요청했을 때만.')
    status_filter: Literal['published_reference_exceeded', 'insufficient_data', 'partial_reference_check'] | None = None


class SelectedDocumentArgs(Args):
    document_mentions: list[Mention] = Field(min_length=1, max_length=5, description='질문에 적힌 문서 제목 그대로.')


class EmissionsArgs(Args):
    fuel_t: float = Field(ge=0, le=1e7)
    factor: float = Field(gt=0, le=10, description='tCO2/t 연료')
    dwt: float = Field(gt=0, le=1e7)
    distance_nm: float = Field(gt=0, le=1e7)


UtcTime = Annotated[str, Field(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$')]


Offset = Annotated[int, Field(ge=-720, le=840, multiple_of=15)]


class VoyageTimeArgs(Args):
    start: UtcTime
    end: UtcTime
    start_offset_min: Offset = 0
    end_offset_min: Offset = 0


class ClarifyArgs(Args):
    missing: list[Literal['task', 'ships', 'periods', 'years', 'documents', 'ports']] = Field(min_length=1, max_length=6)


class NoArgs(Args):
    pass


class DeclineArgs(Args):
    reason: Literal['realtime_position', 'weather', 'forecast', 'data_change', 'entry_approval', 'off_topic']


SkillID = Literal[
    "mrv-analysis",
    "selected-document-answer",
    "operation-summary",
    "report-draft",
    "checklist",
    "qa-evaluation",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Context(Strict):
    ship: str = Field(default="", max_length=100)
    # Keep JSON date input explicit and validate only for workflows using it.
    start: str = Field(default="", alias="from", max_length=10)
    end: str = Field(default="", alias="to", max_length=10)


class SkillRequest(Strict):
    skill: SkillID
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    context: Context = Field(default_factory=Context)
    year: int | None = Field(default=None, ge=1900, le=2100)
    use_model: bool = False
    answer_id: str = Field(default="", max_length=100)
    template: Literal["noon", "mrv"] = "mrv"
