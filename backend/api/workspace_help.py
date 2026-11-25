"""Navigation help grounded in the current workspace screens."""
import re

GUIDES = {
    'chat': (
        '통합 질문에서 질문을 입력하고 전송하세요. 문서 제목이나 선박·기간을 적고, 목록·합계·순위와 답변 언어를 지정할 수 있습니다. 예: “HAE 02의 전체 기록에서 총 이동거리를 알려 줘.”',
        'Open Integrated Question, enter a question and send it. Name a document or specify a vessel, dates, list, total, ranking and answer language. For example: “What was the total distance for HAE 02 across all records?”'),
    'documents': (
        '문서 탭에서 제목을 검색하고 해당 문서를 열면 등록 정보와 문단을 확인할 수 있습니다. 원본 PDF가 등록된 문서는 PDF도 열 수 있습니다.',
        'Open Documents, search by title and open a document to inspect its details and passages. You can view the original PDF when available.'),
    'operations': (
        '운항 정보에서 선박과 기간을 선택해 개별 기록과 운항 지표를 확인하세요. 통합 질문에서도 같은 기록의 거리·연료·배출량을 조회할 수 있습니다.',
        'Open Operations and select a vessel and dates to view records and operating metrics. Integrated Question can also look up distance, fuel and emissions.'),
    'reports': (
        '보고서 탭의 보고서 양식 확인에서 빈 양식 5종을 볼 수 있습니다. 보고서 생성에서 양식과 사용할 기록을 선택하고 작성한 뒤 저장하거나 PDF로 다운로드하세요. 작성 중인 초안은 이어 작성하기로 엽니다.',
        'Open Reports. View report forms opens the five blank forms. Choose Create report, select a form and any records, then edit, save or download the PDF. Resume draft reopens work in progress.'),
}
TOPICS = {
    'chat': r'통합\s*질문|질문\s*(?:탭|화면|메뉴)|채팅|integrated question|chat (?:tab|screen)',
    'documents': r'문서\s*(?:탭|메뉴|화면|함)|(?:올려|등록|저장|업로드).{0,14}(?:PDF|문서)|(?:PDF|문서).{0,18}(?:어디서|어디에서|등록|업로드)|documents? (?:tab|screen)',
    'operations': r'운항\s*정보|operations? (?:tab|screen)',
    'reports': r'보고서\s*(?:탭|메뉴|화면)|reports? (?:tab|screen)',
}


def help_topic(q):
    usage = re.search(r'사용법|사용.{0,4}방법|이용법|뭐\s*하(?:는|면)|무엇을\s*할\s*수|어떻게.{0,16}(?:쓰|써|쓸|사용|활용|이용|열|찾|보)|어디(?:서|에서|로).{0,12}(?:보|봐|열|찾|등록)|(?:쓰|보|등록하)는\s*(?:법|방법)|how (?:to|do|can)|where (?:can|do)|사용.{0,6}있',q,re.I)
    if usage and not re.search(r'인용|문서에\s*따르면|PDF.{0,8}(?:근거|내용)|규정|법령',q,re.I):
        for topic, pattern in TOPICS.items():
            if re.search(pattern,q,re.I):
                return topic
    if re.search(r'프로그램|시스템|서비스|사이트|이\s*앱|this (?:app|program|site)',q,re.I) and re.search(
            r'전체\s*기능|주요\s*기능|어떤\s*기능|기능.{0,10}(?:알려|소개|안내|설명)|뭘\s*할\s*수|무엇을\s*할\s*수|what can|features|capabilities',q,re.I):
        return 'overview'
    return None


def help_fields(ctx, topic, en):
    topics = GUIDES if topic == 'overview' else [topic]
    lines = [GUIDES[t][int(en)] for t in topics]
    if 'reports' in topics and ctx.user.get('role') not in ('admin','operator'):
        lines[list(topics).index('reports')] = ('Open Reports to view the five blank forms and available reports. An editor account is required to create a report.'
            if en else '보고서 탭에서 빈 양식 5종과 열람 가능한 보고서를 확인하세요. 보고서 작성에는 쓰기 권한이 필요합니다.')
    if 'documents' in topics:
        if ctx.user.get('role') == 'admin':
            lines.append('As an administrator, you can register and revise documents in Documents.' if en else
                         '관리자 계정에서는 문서 탭에서 새 문서를 등록하고 개정할 수 있습니다.')
        else:
            lines.append('Contact an administrator to register or revise a document.' if en else
                         '새 문서 등록과 개정은 관리자에게 요청하세요.')
    if ctx.user.get('role') == 'admin' and topic == 'overview':
        lines.append('In Admin you can manage accounts, reviews and backups.' if en else '관리에서는 계정, 승인 요청, 백업을 관리합니다.')
    return {'task':'workspace_help', 'status':'completed', 'helpLines':lines}
