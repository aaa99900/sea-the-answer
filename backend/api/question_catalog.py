"""Read-only workspace listings. Search index availability is irrelevant here."""
import re

from .question_requests import report_kind


def mepc_filter(q):
    """Extract formal identifiers separately from any surrounding Korean words."""
    if not re.search(r'MEPC', q, re.I):
        return None
    formal = re.search(r'MEPC\s*(?:\.\s*\d+\s*\(\s*\d+\s*\)|\d+\s*/\s*\d+(?:\s*/\s*Add\.?\s*\d+)?)', q, re.I)
    if formal:
        return 'identifier', re.sub(r'\s+', '', formal[0]).casefold()
    session = re.search(r'(?:제\s*)?(\d{1,3})\s*(?:차|번|회기)|MEPC\s*(\d{1,3})(?!\d)', q, re.I)
    if session:
        return 'session', session[1] or session[2]
    return None


def match_mepc(row, selector, q):
    mode, value = selector
    title = (row.get('reference','') + ' ' + row['title']).casefold()
    if mode == 'identifier':
        hit = re.search(re.escape(value) + r'(?!\d)', re.sub(r'\s+', '', title))
    else:
        hit = re.search(r'\bmepc\s*(?:' + value + r'\s*/|\.\s*\d+\s*\(\s*' + value + r'\s*\))', title)
    if re.search(r'(?:결의서|결의문|결의안|resolutions?)(?:만|\s*only)|only\s+resolutions?',q,re.I):
        return bool(hit and re.search(r'\bmepc\s*\.\s*\d+\s*\(',title))
    if re.search(r'부속|부록|addend|annex',q,re.I) and not re.search(r'포함|including',q,re.I):
        return bool(hit and re.search(r'/\s*add|부속|부록',title))
    return bool(hit)


def catalog_intent(question):
    q = question.strip()
    if re.search(r'보고서|리포트|양식|초안|reports?|templates?', q, re.I):
        if re.search(r'(?:내가(?:\s*전에)?|내|전에|지난번에?)\s*(?:작성한|만든|저장한|보고서|초안)|my\s+(?:saved\s+)?(?:reports|drafts)', q, re.I) and not re.search(r'만들어|작성해|수정해|삭제해', q):
            return 'saved_reports', '', 'contains'
        if not re.search(r'차이|작성법|어떻게|필수\s*항목|how (?:to|do)', q, re.I) and re.search(
            r'(?:만들|작성할|생성할|뽑을|쓸)\s*수\s*있|(?:보고서|양식).{0,14}(?:종류|지원|가능)|(?:가능한|지원하는)\s*(?:보고서|양식)|'
            r'(?:어떤|무슨)\s*(?:보고서|양식).{0,20}(?:있|지원|가능)|available.{0,20}(?:report|template)|what reports|can (?:i|we|you) (?:create|generate|draft)', q, re.I):
            return 'report_forms', '', 'contains'
    mepc = mepc_filter(q)
    wants_titles = re.search(r'목록|제목|리스트|어떤|무슨|뭐|해당|것만|자료만|문서만|나열|열거|몇\s*개|찾아|list|which|titles?|저장|등록|부속문서', q, re.I)
    wants_content = re.search(r'요약|설명|인용|근거로|내용|의무|규정은|규정이|어떻게|summari[sz]e|explain',q,re.I)
    if mepc and wants_titles and not wants_content:
        return 'documents','MEPC','contains'
    if not re.search(r'문서|파일|documents?|files?', q, re.I):
        return None
    if re.search(r'설명|요약|무슨\s*내용|인용|근거로|explain|summari[sz]e', q, re.I):
        return None
    if not re.search(r'목록|리스트|어떤\s*(?:것|문서|파일)|뭐\s*(?:가|있)|몇\s*(?:개|건)|시작하|들어간|포함된|list|how many|which (?:files|documents)', q, re.I):
        return None
    mode = 'prefix' if re.search(r'시작|start(?:s|ing)? with|prefix', q, re.I) else 'contains'
    patterns = [r'["“「\']([^"”」\']+)["”」\']', r'([\w.()/·-]+?)(?:으?로\s*시작|[이가]?\s*(?:들어간|포함된)|\s*관련\s*(?:문서|파일))',
                r'\b([A-Z]{2,}(?:[./]\d+(?:\(\d+\))?)?)\b']
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return 'documents', match[1].strip(), mode
    if re.fullmatch(r'(?:등록된?\s*|전체\s*|모든\s*|저장된\s*)?(?:문서|파일)\s*(?:목록|리스트)(?:을|를)?\s*(?:좀\s*)?(?:보여\s*줘|알려\s*줘)?[?.! ]*', q):
        return 'documents', '', mode
    return None  # The model can supply a literal title fragment for other wording.


def catalog_fields(ctx, kind, term='', mode='contains'):
    q = ctx.body['question']
    en = ctx.body.get('language') == 'en' or (ctx.body.get('language','auto') == 'auto' and not re.search('[가-힣]',q))
    if kind.startswith('help_'):
        from .workspace_help import help_fields
        return help_fields(ctx, kind.removeprefix('help_'), en)
    if kind == 'report_forms':
        return {'task':'workspace_catalog', 'status':'completed', 'catalog':{'kind':kind, 'form':report_kind(q)}}
    if kind == 'saved_reports':
        rows = [r for r in ctx.db.reports(ctx.user) if r['owner'] == ctx.user['id']]
    else:
        inferred=catalog_intent(q)
        if inferred and inferred[0]=='documents':
            _,term,mode=inferred
        rows = ctx.db.document_titles(ctx.user)
        term = term.strip()
        if term.casefold() not in q.casefold():
            return {'task':'clarification','status':'needs_input','notice':'Which title should I look for?' if en else '제목에서 찾을 검색어를 알려 주세요.'}
        key = term.casefold()
        selector = mepc_filter(q)
        if selector:
            rows = [r for r in rows if match_mepc(r, selector, q)]
            term = 'MEPC ' + selector[1] if selector[0]=='session' else selector[1].upper()
        else:
            rows = [r for r in rows if (r['title'].casefold().startswith(key) if mode == 'prefix' else key in r['title'].casefold())]
    items = [{'id':r['id'],'title':r['title']} for r in rows]
    noun = ('reports' if en else '내 보고서') if kind == 'saved_reports' else ('documents' if en else '등록 문서')
    notice = f'{noun} · {len(items)}' + ('' if en else '건')
    if not items:
        notice=('0 matching documents.' if en else '일치하는 등록 문서가 없습니다 (0건).') if kind=='documents' else ('No saved reports.' if en else '저장한 보고서가 없습니다.')
    if term:
        notice += ' · ' + term
    return {'task':'workspace_catalog','status':'completed','notice':notice,'catalog':{'kind':kind,'items':items,'term':term}}
