# HTTP API

- 상태: 구현됨 (1.4.0)
- 최종 확인: 2026-10-13 (`backend/api/` 대조)
- 관련: [`../architecture.md`](../architecture.md), [`../data-model.md`](../data-model.md), [`integrated-answer.md`](integrated-answer.md), [ADR 0016](../adr/0016-crew-admin-authentication.md)

## 1. 목적

화면(`frontend/src/lib/api.js`)과 팀 모듈이 사용하는 로컬 HTTP API의 계약입니다. 브라우저는 Next.js 공개 주소(`http://<host>:5173/api/...`)로 호출하고, Next.js가 `HAEDAP_API_ORIGIN`(기본 `http://127.0.0.1:8000`)으로 그대로 전달합니다. **API 구현을 Python 등으로 바꿔도 이 문서의 경로·형식·검사 규칙을 지키면 화면은 바뀌지 않습니다.**

### 전달 경로와 Host 규칙 (구현이 지켜야 할 것)

`GET /api/health`의 `llmConfigured`는 [모델 공급자 설정](llm-provider.md)이 유효한지 표시합니다. 로컬 호환 서버는 키 없이 활성화할 수 있고 health는 모델 서버를 호출하지 않습니다. true여도 서버 도달·인증·모델 적재 성공을 보장하지 않습니다. `POST /api/ask`의 기존 응답 필드·모델 실패 경고 코드는 유지합니다.

- API 서버(FastAPI)는 Next.js만 닿을 수 있는 곳에 둡니다. compose에서는 내부 네트워크의 `backend:8000`(호스트에 공개하지 않음), 직접 실행에서는 `127.0.0.1:8000`.
- 실제 호스트 = `X-Forwarded-Host`(Next.js 프록시가 설정) 또는 `Host`. 호스트 이름이 `127.0.0.1`·`localhost`·`HAEDAP_ALLOWED_HOSTS` 중 하나가 아니면 403 `HOST_DENIED`. 포트는 검사하지 않습니다.
- `Origin`이 있으면 `http://<실제 호스트>`(`HAEDAP_HTTPS=true`이면 `https://`)와 같아야 하고, `Sec-Fetch-Site`가 `cross-site`/`same-site`면 거부합니다(403 `ORIGIN_DENIED`).
- `X-Forwarded-For`는 로그인 시도 제한의 접속자 구분에만 씁니다(API가 내부 네트워크에만 있으므로 신뢰). 권한 판단에는 쓰지 않습니다.
- 앱 API는 `/api/{path}` 하나가 처리하고, 없는 경로는 404 `NOT_FOUND`. `MARITIME_DATA_API_TOKEN`이 있으면 `/api/maritime-data/*`가 먼저 매칭됩니다([해사 데이터 API](tools.md)).

## 2. 인증과 쓰기 보호

인증·계정 발급·비밀번호·세션·오류의 계약은 [authentication.md](authentication.md)에 정의합니다. `admin/operator/viewer` 개인 계정으로 로그인하며 업무 API는 익명 접근을 차단합니다. `health.publicAccess=false`; 초기 비밀번호 변경 전에는 업무를 사용할 수 없습니다.

- 모든 POST는 JSON + `X-Haedap-Token`(CSRF)이 필요합니다. 같은 출처·Host를 검사합니다.
- `X-Haedap-Identity`가 현재 세션 사용자와 다르면 401입니다. 서버가 저장된 역할로 권한을 결정합니다.
- 문서 범위는 검색 단계부터 원문 PDF·보고서 근거·질문 이력 재열람까지 검사합니다.
- 요청 크기: `/api/changes` 38MB, `/api/backups/import` 100MB, 그 외 POST 1MB. JSON이 아니면 415입니다.
- 기존 게스트 식별자와 소유 자료는 보존하지만 로그인 계정으로 자동 이전하지 않습니다.

## 3. 경로

| 메서드 · 경로 | 권한 | 동작 |
|---|---|---|
| GET `/api/health` | 모두 | 상태·사용자·CSRF 토큰 |
| POST `/api/auth/login` · `/api/auth/logout` | 모두 | 개인 계정 로그인·로그아웃 |
| POST `/api/auth/password` | 로그인 계정 | 본인 비밀번호 변경·세션 재발급 |
| GET `/api/documents` | 로그인 계정 | 허용 문서 목록·메타데이터·페이지별 본문 |
| GET `/api/documents/:id/pdf` | 로그인 계정(범위 검사) | 허용된 저장 원본 PDF |
| GET `/api/operations` | 로그인 계정 | 선박과 일별 운항 기록 |
| POST `/api/operations/validate` | 관리자 | CSV 행 검증 `{rows:[...]}` |
| POST `/api/operations/example` | 관리자 | 빈 작업공간에 가상 예시 등록 |
| POST `/api/changes` | 관리자 | `{kind, payload}` 변경 즉시 반영. 일반 사용자는 403 |
| GET `/api/changes` | 관리자 | 변경·승인 목록 (최근 200) |
| POST `/api/changes/review` | 관리자 | `{id, decision:"approve"|"reject", note}` |
| GET/POST `/api/users` | 관리자 | 계정 목록·생성·수정 |
| POST `/api/ask` | 로그인 계정 | 통합 답변 → [`integrated-answer.md`](integrated-answer.md) |
| POST `/api/search` | 로그인 계정 | 열람 범위가 적용된 검색 결과 |
| GET `/api/history` | 로그인 계정(본인) | 당시 질문·답변·근거 (최근 100) |
| GET `/api/logs` | 관리자 | 감사 로그 최근 500건 |
| GET/POST `/api/reports` | 조회: 로그인 계정 / 저장: 선원·관리자 | 보고서 목록·저장. 새 초안은 새 UUID |
| GET `/api/reports/:id` | 열람 권한 | 개별 보고서 |
| GET/POST `/api/reports/current` | 열람 권한 | 이전 공용 초안 ID 호환 경로 |
| POST `/api/reports/generate` | 선원·관리자 | `{template:"noon"|"mrv", ship, from, to}` |
| POST `/api/reports/submit` | 소유자·관리자 | `{id, version}` 검토 요청 |
| POST `/api/tools/calculate_emissions` | 로그인 계정 | `{fuel, factor, dwt, distance}` |
| POST `/api/tools/voyage_time` | 로그인 계정 | `{start, end, before, after}` UTC 시간 계산 |
| GET/POST `/api/backups` | 관리자 | 백업 목록 / 생성 |
| GET `/api/backups/:id` | 관리자 | 백업 파일 다운로드 |
| POST `/api/backups/import` | 관리자 | 백업 JSON 형식·체크섬 검증 후 목록에 추가 |
| POST `/api/backups/restore` | 관리자 | `{id, confirm:"복구"}`. 복구 전 자동 보관·재로그인 |
| POST `/api/backups/settings` | 관리자 | `{autoBackup:"daily"|"off"}` |

앱 JSON 백업·복구의 대상은 기존 앱 16개 테이블입니다. 해사 스키마 전체는 포함하지 않습니다. 같은 DB의 `maritime_data.vessels.ship_id`가 있으면 복구 직전 현재 연결을 보관하고, 앱 선박 교체 후 동일한 정체성이 확인되는 연결만 복원합니다. 실제 선박은 원본 7자리 IMO와 복구한 비샘플 앱 선박의 IMO가 같아야 하고, IMO가 없는 합성 선박은 이전 명시 연결의 이름·선종·DWT·IMO·sample 구분이 유지되어야 합니다. ID만 같고 식별정보가 달라진 선박은 연결하지 않습니다.

복구 응답은 `ok`, `safetyBackup`을 유지하며, 연결 컬럼이 있는 경우 `maritimeLinks={linkedBefore,restored,cleared,missingShips,identityMismatch}`를 추가합니다. 해제된 연결이 있으면 `warnings`도 반환하고 같은 건수를 감사 로그에 남깁니다. 이 응답은 현재 연결 보존 결과이며 과거 해사 데이터·연결을 복구하는 별도 백업을 대체하지 않습니다.

### 변경 `kind`

`document.save`, `document.delete`, `ship.save`, `operation.save`, `operation.import`, `operation.delete`.

- 관리자만 가능하며 한 트랜잭션에서 즉시 반영합니다. 이력 호환을 위해 `changes.status='approved'`로 기록하지만 승인 대기는 없습니다.
- 낡은 버전으로 변경하면 **409 `VERSION_CONFLICT`**. CSV 여러 행은 한 트랜잭션.
- `ship.save`에서 해사 원본과 연결된 선박의 정체성을 바꾸면 **409 `MARITIME_SHIP_IDENTITY_CONFLICT`**. 실제 선박은 원본과 동일한 IMO 및 비샘플 구분을 유지해야 하며 이름·DWT 변경은 허용합니다. 합성 선박은 기존 이름·선종·DWT·IMO·sample 구분을 유지해야 합니다. 필요한 식별정보 수정은 관리자가 연결을 수동 검토·해제한 뒤 수행하고 다시 연결합니다. 이 검사는 원본 데이터나 매핑을 자동 변경하지 않으며 연결이 없는 선박에는 기존 수정 규칙을 적용합니다.
- 보고서 검토 요청과 이전 버전의 대기 항목은 `POST /api/changes/review`로 처리합니다.

## 4. 문서 등록 payload (`document.save`)

```json
{
  "document": {
    "id": "manual-001",
    "title": "시험 매뉴얼",
    "kind": "onboard",
    "version": "1",
    "reviewedAt": "2026-09-30",
    "reference": "제1조",
    "language": "ko",
    "sections": [{"page": 7, "heading": "제1조", "text": "검토할 실제 원문을 입력합니다."}]
  },
  "expectedId": "",
  "meta": {
    "scope": "all",
    "status": "active",
    "issuer": "발행기관",
    "issuedAt": "2026-01-01",
    "revisedAt": "2026-09-01",
    "applicability": "적용 대상과 조건"
  }
}
```

| 필드 | 제약 |
|---|---|
| `document.id` | `^[a-z0-9][a-z0-9-]*$`, ≤80자 |
| `document.kind` | `onboard` · `official-summary` · `sample`. `official-summary`는 HTTPS `url` 필수 |
| `document.sections` | 1~1,500개, 절 본문 ≤20,000자, 전체 ≤2,000,000자, `page` 1~10,000 정수(선택) |
| `expectedId` | 새 문서는 `""`, 개정 시 현재 개정 ID. 다르면 409 |
| `expectedMetaRevision` | 개정·정보 수정 시 현재 `meta.revision`. 다르면 409 |
| `meta.scope` | `all` · `operator` · `admin` — 같은 논리 문서의 이전 개정본에도 적용 |
| `meta.status` | `active` · `retired` |
| `file` | 선택. `{name, base64}`, `%PDF-`로 시작, 25MB 이하 |

문서 삭제는 행을 지우지 않고 `status:'deleted'`로 검색·열람에서 제외합니다. 페이지 번호 없는 기존 자료는 `페이지 미지정`으로 표시합니다.

### Python 문서 전처리 계약 (2026-10-13 확정)

현재 등록은 `POST /api/changes`의 `kind: "document.save"`이다. PDF.js가 만든 페이지별 `sections`와 선택적 `file`을 받고, `backend/api/store/documents.py`의 `DocumentStore.save_document`가 저장한다. raw PDF만 보내는 새 업로드 API는 추가하지 않는다.

`backend/api/rag_preprocessing.py`의 `preprocess_sections(sections, max_chars=900)`은 DB·웹 프레임워크에 의존하지 않고 `{page, heading, text}` 목록을 반환한다. 저장 시 기존 개정 ID와 순서로 청크 ID를 만들며 제목은 `documents`와 조인하여 반환한다.

- 페이지와 입력 절을 넘겨 본문을 합치지 않는다. 물리 페이지 번호 또는 기존 NULL을 유지한다.
- 줄바꿈/비분리 공백을 정리하되 조항 번호·숫자·기호와 표의 내부 공백·줄은 보존한다. OCR·수식 복원·단어 하이픈 결합은 하지 않는다.
- 명시적인 Part/Chapter/Section 머리말과 ABS 규정 꼬리말이 3개 이상 서로 다른 페이지 가장자리에서 반복될 때만 제거한다. 제거한 머리말 중 가장 구체적인 절 제목은 `heading`에 보존한다. 본문 중간의 같은 문구와 조항 제목은 보존한다.
- 번호 있는 짧은 조항 제목과 TABLE/FIGURE 제목은 별도 블록을 시작하고 `heading`에 반영한다. 긴 블록은 문단→문장→줄→공백 경계 순으로 최대 길이 안에서 나눈다. 표 블록은 문장보다 줄 경계를 우선한다. 경계가 없는 긴 문자열만 강제 분할한다.
- 기존 문서 hash와 `unchanged` 판정을 유지한다. 이미 등록된 동일 문서/재활성화된 이전 개정본의 청크는 다시 쓰지 않는다. 변경된 청킹은 새 문서·새 내용의 개정부터 적용된다. 기존 청크를 바꾸는 재색인은 별도 작업이다.
- API 응답·PostgreSQL 테이블·열람 범위·인용 검증은 그대로 유지한다. 검색은 현재 Python의 단어 포함 점수 방식이다.

CLI 일괄 수집 명령은 제거되었습니다(Node 버전의 `npm run ingest`). 빈 DB의 첫 요청 때 `backend/knowledge/seed.json`(위 `document` 객체 배열)이 자동 등록됩니다.

## 5. 오류 형식

검증 실패는 `AppError(status, code, message)`로 던지고 다음 형식으로 응답합니다. 로그인한 사용자의 실패는 감사 로그(`category:'error'`)에도 남습니다.

```json
{"error": {"code": "VERSION_CONFLICT", "message": "운항 기록이 변경되었습니다. 다시 열어 주세요."}}
```

주요 코드: `LOGIN_FAILED`(401), `FORBIDDEN`(403), `NOT_FOUND`(404), `TOOL_NOT_FOUND`(404), `VERSION_CONFLICT`(409), `MARITIME_SHIP_IDENTITY_CONFLICT`(409), `SETUP_DISABLED`(410), `CONTENT_TYPE`(415), `ANOMALY`(운항 연료 급증 사유 누락). 메시지는 사용자에게 그대로 보여 줄 한국어 문장입니다.

해사 데이터 적재·연결 작업과 복구의 테이블 잠금이 충돌하면 최대 5초 대기 후 **409 BUSY**를 반환합니다. 복구 트랜잭션은 롤백되어 앱 데이터와 해사 연결을 변경하지 않으며, 작업이 끝난 후 복구를 다시 시도할 수 있습니다.

## 6. 한계

- 백업은 SHA-256 체크섬으로 우발적 손상만 검사하며, 서명 기반 진위 확인은 하지 않습니다. 가져오기는 형식 v2만 허용합니다.
- 목록 API는 페이징 없이 전체를 반환합니다(캡스톤 데모 규모).
