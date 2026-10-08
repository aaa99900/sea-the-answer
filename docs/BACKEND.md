# RAG / DB / Tool 구현

처음 실행하거나 구현 흐름을 따라가려면 [README](../README.md)를 먼저 보세요. README를 기본 실행·구현 안내서로 유지하며, 이 문서는 백엔드의 세부 동작과 제한 사항을 설명합니다.

현재 구현은 한 PC에서 실행하는 백엔드입니다. 기본 모드는 해당 PC에서 사용하며 LAN 모드에서는 같은 네트워크의 기기가 브라우저로 접속해 문서·DB를 공유합니다. 기본 DB는 PostgreSQL이며 Node.js 22.13 이상, `npm ci`, 실행 중인 PostgreSQL 12 이상 서버와 `.env`의 `DATABASE_URL`이 필요합니다. 외부 AI API 키는 기본 기능에 필요하지 않습니다. 기존 SQLite는 명시적으로 선택하는 호환 모드입니다.

마지막 업데이트: 2026-10-08. PDF 신규 수집에만 Python 3.9+와 `requirements-pdf.txt`의 pypdf 6.19.0이 필요합니다. 기존 JSON 수집과 이미 저장된 문서 검색에는 Python이 필요하지 않습니다.

## 실행 및 검증

먼저 README의 PostgreSQL 사용자·빈 DB 생성, `.env` 설정과 `npm ci`를 마칩니다. 아래 명령은 프로젝트 루트에서 실행합니다.

```powershell
.\start.cmd
# http://127.0.0.1:5173

# 다른 기기 접속은 위 로컬 서버를 종료한 뒤 실행
.\start-lan.cmd
# 실행 창의 LAN 주소로 접속

powershell -ExecutionPolicy Bypass -File .\start.ps1 -Task test
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Task ingest -Document .\knowledge\seed.json
```

Node가 PATH에 있으면 `npm start`, `npm run start:lan`, `npm test`, `npm run ingest -- knowledge/seed.json`도 가능합니다. 포트 지정은 `node server.mjs --lan --port 5174` 또는 `start.ps1 -Lan -Port 5174`로 합니다. 실제 Chrome 검증은 `node scripts/browser-smoke.mjs`로 실행하며 `--lan`을 붙이면 LAN 주소로 점검합니다. 기본 Chrome 경로가 다르면 `CHROME_PATH` 환경변수를 설정하세요. 결과와 모바일 화면은 `.verification/backend-browser-*/`에 저장합니다. Windows 런처 로그는 `.verification/launcher-*/`에 저장합니다.

## 문서 수집 → 검색 → 답변

1. `knowledge/seed.json`의 초기 문서 4개를 빈 DB에 수집합니다. IMO 공식 웹 안내를 확인해 작성한 한국어 요약 2개와 명시적으로 표시한 가상 문서 2개입니다. 공식 규정 전문을 수집한 상태는 아닙니다.
2. 절·문장 경계로 본문을 최대 900자 청크로 나눕니다. 문서 ID·버전·확인일·출처 URL·조항·절 제목과 콘텐츠 해시를 보존합니다. 소수점은 분할하지 않습니다. PDF는 페이지마다 별도 절을 만들므로 청크가 페이지 경계를 넘지 않습니다.
3. 기본 PostgreSQL은 `tsvector` GIN 색인과 `ts_rank_cd` 순위로 검색합니다. 선택적 SQLite 모드는 기존 FTS5/BM25를 유지합니다. 양쪽 모두 한국어 단어·2글자 조각과 작은 한·영 용어 사전을 사용하지만 순위가 같지는 않습니다. **현재 검색은 어휘 기반이며 임베딩·벡터 검색은 구현하지 않았습니다.**
4. 기본 모드는 검색된 문단을 그대로 보여줍니다. 질문 전체를 해결한 생성 답변이라고 표시하지 않습니다. 근거가 없으면 답변을 보류합니다. 문서 필터는 검색 단계에 적용합니다.
5. 외부 모델을 설정하고 화면에서 선택하면 검색 문단을 근거로 답변을 생성합니다. 문장마다 존재하는 청크 ID와 해당 청크에 실제 존재하는 인용문을 검사합니다. 모델 오류·잘못된 인용·불완전한 출력에는 근거 문단으로 전환하고 전환 사실을 표시합니다.

인용의 존재 검사는 문장의 의미가 근거에 완전히 부합함을 보장하지 않습니다. 검색 적합성, 복합 질문, 선박별 적용 조건, 최신 개정 여부, 답변 정확도에 대한 별도 평가가 필요합니다. 모델이 질문을 근거로 답할 수 없다고 판단하면 답변을 보류합니다.

공식 수집 근거(2026-09-28 확인):

- [IMO 2020 · sulphur 안내](https://www.imo.org/en/mediacentre/hottopics/pages/sulphur-2020.aspx)
- [IMO · EEXI/CII FAQ](https://www.imo.org/en/mediacentre/hottopics/pages/eexi-cii-faq.aspx)

## 문서 추가와 개정

`knowledge/seed.json`과 같은 구조의 JSON 배열을 작성한 뒤 ingest 명령으로 등록합니다. 문서 종류는 `official-summary`, `onboard`, `sample` 중 하나입니다. 공식 안내 요약에는 HTTPS 원문 URL을 지정해야 합니다. 등록자가 출처와 본문 정확성을 확인해야 하며, 분류 이름만으로 진위를 검증하지는 않습니다.

```json
[
  {
    "id": "vessel-approved-manual",
    "title": "선내 승인 문서 제목",
    "kind": "onboard",
    "reference": "문서 번호 / 절 번호",
    "version": "1.0",
    "reviewedAt": "2026-09-28",
    "language": "ko",
    "sections": [
      { "heading": "절 제목", "text": "확인한 본문을 여기에 넣습니다." }
    ]
  }
]
```

같은 ID·같은 내용의 재수집은 중복을 만들지 않습니다. 같은 ID의 내용이 바뀌면 새 버전만 검색하며 이전 버전은 남겨 기존 보고서의 인용을 유지합니다. 수집은 트랜잭션 단위로 처리합니다. 서버 재시작은 기존 문서를 초기 시드로 되돌리지 않습니다. 텍스트 PDF 수집은 아래 경로로 구현했으며 OCR, 웹 자동 크롤링, 자동 개정 감시는 다음 확장 범위입니다.

### PDF 페이지 수집

`scripts/ingest-pdf.mjs` → `backend/pdf.mjs` → `scripts/extract-pdf.py`(pypdf) → 기존 `importDocuments` / `prepareDocument` → PostgreSQL 전문 검색 순서입니다. SQLite를 명시적으로 선택하면 FTS5/BM25로 저장·검색합니다. 기존 JSON 수집기와 `rag.mjs`의 검색 흐름은 유지합니다.

프로젝트 루트에서 다음 명령을 사용합니다.

```powershell
python -m pip install -r requirements-pdf.txt
# 필요 시 python.exe의 실제 경로를 지정
# $env:HAEDAP_PYTHON = 'C:\Python312\python.exe'
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Task ingest-pdf -Document "data/pdfs/ABS/MVR Part-5D-Offshore-Support-Vessels-for-Specialized-Services-jul-2026.pdf"
# Node가 PATH에 있으면: npm run ingest:pdf -- "data/pdfs/ABS/file.pdf"
```

- 명시한 PDF 1~3개만 수집합니다. 경로는 실제 경로 기준 `data/pdfs` 안에 있어야 합니다. 해당 폴더 전체 자동 수집은 하지 않습니다.
- 원본별 최대 128 MiB, 5,000페이지, 본문 20,000,000자, 변환 절 10,000개, 추출 시간 180초입니다. PDF 페이지는 필요하면 20,000자 절로 나눈 뒤 기존 청크 분할을 적용합니다. 일반 JSON 제한은 그대로입니다.
- `kind: pdf`, `title: 파일명`, `reference: data/pdfs 기준 경로`, `version: 원본 SHA-256`을 사용합니다. 논리 ID는 상대 경로의 해시이므로 같은 경로의 변경본은 새 개정, 이동·이름 변경은 새 문서입니다. `reviewedAt`에는 PDF 파일 수정일이 들어가며 UI에 **파일 수정일**로 표시합니다. 실제 검토/승인을 뜻하지 않습니다.
- `sections[].page`는 표지 포함 1부터 시작하는 물리 페이지로, 인쇄 쪽수와 다를 수 있습니다. `heading`은 페이지 첫 줄을 사용하며 조항 계층을 분석하지 않습니다. 빈 페이지 번호도 유지하며 검색에서는 빈 페이지를 제외하고 경고합니다. 전체가 이미지이면 OCR 필요 오류입니다. 암호화 PDF는 거부합니다.
- 새 PostgreSQL DB의 `chunks.page`는 선택적 정수 필드입니다. 기존 SQLite v1 파일을 SQLite 모드에서 열면 v2로 이전하고 기존 JSON 해시·ID·FTS 색인·보고서를 보존하며 페이지는 `NULL`로 남깁니다. 청크의 문서명은 `documents.title`과 연결합니다.
- `/api/search`, `/api/ask`의 검색 청크에는 `document_id`, `title`, `page`, `heading`, `text`가 포함됩니다. `/api/documents`의 절에도 같은 정보를 반환합니다. 검색 화면과 보고서에 문서명·페이지를 표시합니다.
- PDF는 전체/선내 문서 필터에 포함됩니다. `imo` 필터의 공식 안내 요약과는 별도 분류입니다. PDF 원본 제공, OCR, 표/수식 복원, 임베딩·벡터·하이브리드 검색은 구현하지 않습니다.

기존 SQLite 자료는 자동 이전하지 않습니다. 원본을 백업한 뒤 빈 PostgreSQL DB에 `start.ps1 -Task migrate-postgres -Document data/haedap.sqlite`로 복사할 수 있습니다. 별도 검증은 다른 빈 PostgreSQL DB를 만들어 서버·수집기에 같은 `DATABASE_URL`을 지정합니다. 자세한 백업·실행·문제 해결 절차는 README에 있습니다. 수집 성공 출력은 전체/텍스트 페이지 수, 빈 페이지 번호, 글자 수와 등록 결과를 포함합니다.

추가 검증은 `HAEDAP_TEST_PDF`에 위 실제 PDF 1개 경로를 지정한 뒤 기존 `start.ps1 -Task test`를 실행합니다. 테스트는 임시 DB와 작은 3페이지 PDF 테스트 자료 1개를 사용하며, 실제 PDF도 명시한 1개만 읽습니다. Python이 없으면 추출기 테스트를 건너뛰지만 실제 PDF를 명시한 검증은 의존성이 없을 때 실패합니다.

## DB와 보고서

기본 DB는 `.env`의 `DATABASE_URL`이 가리키는 PostgreSQL입니다. `documents`, `chunks`(생성된 `search_vector` 및 GIN 색인), `reports`, `tool_runs`, `queries` 테이블을 사용합니다. 문서와 보고서뿐 아니라 질문, 검색 근거, 답변, 계산 입력·출력도 DB에 저장합니다. API 키는 DB·브라우저에 저장하지 않습니다. 선택적 SQLite는 `HAEDAP_DB_BACKEND=sqlite`와 `HAEDAP_DB_PATH`로 지정하며 기존 `chunks_fts`를 유지합니다.

보고서 화면에서 **초안 저장**을 누르면 현재 초안을 DB에 저장합니다. **DB 초안 불러오기**로 다시 열 수 있습니다. 기존 브라우저 초안을 자동 덮어쓰지 않습니다. 여러 창의 동시 편집은 버전 검사로 충돌을 알려주며, DB 초안을 다시 불러와 해결합니다. 서버 재시작 후에는 화면을 새로고침하세요. 샘플 모드에서는 기존 브라우저 저장 기능을 사용합니다.

이 단계는 현재 초안 1개를 위한 API입니다. LAN 접속 기기도 같은 초안을 공유하며 저장 버전으로 충돌을 감지합니다. 사용자 계정, 권한 구분, 다중 보고서 목록, 공개 인터넷 배포는 포함하지 않습니다. PostgreSQL은 `pg_dump`로 백업합니다. SQLite 호환 모드의 파일은 서버를 종료한 뒤 복사하세요. 실행 중 파일 복사는 WAL 상태를 누락할 수 있습니다.

## 계산 Tool

| 이름 | 입력 | 결과 |
|---|---|---|
| `calculate_emissions` | 연료 t, 환산계수 tCO₂/t, DWT, 거리 nm | CO₂ t, 단순 집약도 gCO₂/(DWT·nm), 계산 버전·가정 |
| `voyage_time` | UTC 시작·종료, 시작·종료 선내 오프셋(분) | 실제 경과시간, 선내 시계 표시 차이, 반개구간 표기 |

계산은 모델에게 맡기지 않고 검증된 숫자 입력을 함수에 전달합니다. 문자열 숫자, 음수, 0인 분모, 무한대, 잘못된 날짜를 거부합니다. **공식 CII 등급은 산정하지 않습니다.** 배출량 화면의 초기 표시와 기본값 변경은 로컬 미리보기이며, 다시 계산하기를 누르면 서버 Tool을 실행하고 기록합니다. 배출량을 함께 요청하는 검색에는 현재 계산 화면의 입력값이 사용됩니다. 자연어 숫자 추출은 구현하지 않았습니다. 항해 시각 Tool은 API로 제공하며 기존 지도·시각 화면은 로컬 계산을 유지합니다.

## 선택적 외부 모델

`.env.example`을 `.env`로 복사하고 다음을 설정합니다. 모델 이름은 사용 가능한 Responses/Structured Outputs 지원 모델을 직접 지정합니다.

```dotenv
DATABASE_URL=postgresql://haedap:REPLACE_WITH_YOUR_PASSWORD@127.0.0.1:5432/haedap
OPENAI_API_KEY=발급받은_키
OPENAI_MODEL=사용할_모델_ID
```

서버를 재시작한 뒤 **실행 환경 설정 → 검색 근거로 AI 답변 생성**을 켭니다. 이때 질문과 검색 문단이 OpenAI에 전송됩니다. 기본 모드와 외부망 차단 모드에서는 전송하지 않습니다. [Responses API의 Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)를 사용하고 `store: false`로 요청합니다. 이번 환경에는 API 키가 없어 실제 외부 모델 호출은 하지 않았으며, API 요청 형식·정상 응답·실패·잘못된 인용 처리는 모의 응답으로 검증했습니다.

## API

| 메서드·경로 | 용도 |
|---|---|
| `GET /api/health` | DB·검색 상태, 모델 설정 여부, 요청 토큰 |
| `GET /api/documents` | 현재·이전 문서 버전과 청크 |
| `POST /api/search` | `{ "question": "...", "filter": "all" }`로 근거 검색 |
| `POST /api/ask` | 검색·선택적 생성·선택적 계산·질문 기록 |
| `GET /api/reports/current` | 현재 DB 초안 |
| `POST /api/reports/current` | `{ title, type, text, sources, version }` 저장 |
| `GET /api/tools` | 허용된 Tool 목록·입력 설명 |
| `POST /api/tools/calculate_emissions` | `{ fuel, factor, dwt, distance }` |
| `POST /api/tools/voyage_time` | `{ start, end, before, after }` |

POST 요청은 `Content-Type: application/json`과 health가 돌려주는 `X-Haedap-Token` 헤더가 필요합니다. 기본 서버는 `127.0.0.1`, `--lan` 서버는 `0.0.0.0`에 바인딩합니다. LAN 모드도 서버의 실제 IPv4 주소·포트, 연결된 서브넷의 접속자, 동일 출처 요청만 허용합니다. 네트워크가 바뀌면 서버를 재시작합니다. 요청 본문은 1MB, 동시 POST는 4개로 제한합니다. DB, 환경파일, 백엔드 소스는 정적 파일로 제공하지 않습니다. 요청 토큰은 사용자 인증을 대신하지 않습니다. 다른 기기 접속과 선택적 Windows 방화벽 설정은 README의 실행 안내를 따릅니다.

## 이번 검증과 남은 단계

2026-10-08 기본 PostgreSQL 전환 후 실제 ABS PDF 1개를 포함한 전체 자동 테스트 26개가 통과했습니다(실패·건너뜀 0). PostgreSQL 호환 엔진 PGlite와 pg 연결 프로토콜로 DB·HTTP·SQLite 자료 복사를 검증했습니다. 기존 SQLite FTS5/BM25와 Windows 런처도 확인했습니다. 독립적으로 설치한 PostgreSQL 서버 실연동과 이번 변경의 수동 브라우저 검토는 수행하지 않았습니다.

2026-10-01 PDF 수집 변경 후 기존 15개와 새 PDF 관련 6개, 총 21개 테스트가 통과했습니다(실패·건너뜀 0). Python 3.12.10 / pypdf 6.19.0 / Node v24.20.0을 사용했습니다. 실제 대상은 ABS Part 5D PDF 1개로, 전체 387페이지에서 804,656자를 추출해 1,110청크를 저장하고 문서명·페이지 검색 및 재수집을 검증했습니다. 나머지 실제 PDF 6개는 처리하지 않았습니다. 작은 3페이지 테스트 PDF로 중간 빈 페이지의 번호도 확인했습니다. 별도 DB의 JSON CLI → PDF CLI 등록, 기존 Chrome 점검 11개도 통과했습니다. 페이지 표시와 보고서 전달은 자동 UI 테스트이며 수동 PDF 화면 검토·전체 추출 정확도 평가는 아닙니다. 샌드박스의 Windows 자식 프로세스 정리 제한으로 첫 시도가 중단되어 정상 권한으로 전체 테스트를 재실행했습니다.

2026-09-28 로컬/LAN 실행 변경 후 자동 테스트 15개, 로컬 주소와 실제 Wi-Fi 주소를 사용하는 Chrome 검증 각각 11개가 통과했습니다. 모두 이 PC에서 수행했으며, 독립된 다른 기기나 공용 Wi-Fi의 방화벽 통과 여부를 검증한 결과는 아닙니다.

자동 테스트는 수집 중복·개정 보존, 한국어/영어 검색과 필터, 미지원 질문, DB 재시작·저장 충돌, 계산 경계값, 날짜변경선, 모델 인용 검증·장애 전환, API 입력·출처 보호를 확인합니다. Chrome 검증은 검색 → 근거 열기 → 보고서 저장 → 새로고침·불러오기, 서버 계산, 근거 없음, 모바일 배치, 동적 문서 수집과 HTML 이스케이프를 확인합니다.

실제 선박 DB·AIS·기상 데이터, 승인 문서 전문, API 키를 사용하는 모델 품질 검증, 검색/답변 평가 데이터셋과 성능 측정은 아직 남아 있습니다. 현재 위치는 **RAG/DB/Tool의 로컬 MVP 구현 및 주요 UI 연결 완료**이며 운영용 통합·평가 완료는 아닙니다.
