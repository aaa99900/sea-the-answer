# 해,답 · 선원 업무 지원

규정 문서를 검색하고 근거를 확인한 뒤, 운항 수치를 계산하고 보고서 초안을 저장하는 웹 앱입니다.

**이 README가 프로젝트의 기본 실행·구현 안내서입니다.** 처음 참여한 사람도 순서대로 따라 할 수 있도록 유지합니다. 앞으로 기능·설정·실행 방법이 바뀌면 해당 설명과 맨 아래 변경 이력을 함께 업데이트합니다.

마지막 업데이트: **2026-10-08**

## 목차

- [1. 현재 구현 상태](#1-현재-구현-상태)
- [2. 처음 실행하기](#2-처음-실행하기)
- [3. 화면에서 기능 확인하기](#3-화면에서-기능-확인하기)
- [4. 구조와 파일 역할](#4-구조와-파일-역할)
- [5. 검색할 문서 추가하기](#5-검색할-문서-추가하기)
- [6. AI 답변 생성 연결하기](#6-ai-답변-생성-연결하기)
- [7. DB 저장과 백업](#7-db-저장과-백업)
- [8. 기능 구현·수정 순서](#8-기능-구현수정-순서)
- [9. API 직접 호출하기](#9-api-직접-호출하기)
- [10. 테스트하기](#10-테스트하기)
- [11. 문제 해결](#11-문제-해결)
- [12. 다음 작업과 문서 관리](#12-다음-작업과-문서-관리)
- [13. 변경 이력](#13-변경-이력)

## 1. 현재 구현 상태

진행 순서는 **설계 → UI 프로토타입 → RAG/DB/Tool → 통합 → 평가**입니다. 현재는 **RAG/DB/Tool의 로컬 MVP와 주요 화면 연결까지 구현한 상태**입니다. MVP는 핵심 흐름을 확인할 수 있는 첫 구현을 뜻합니다.

| 단계 | 현재 상태 | 남은 내용 |
|---|---|---|
| 설계 | 화면과 주요 사용 흐름 구체화 | 실제 데이터·운영 환경의 상세 설계 |
| UI 프로토타입 | 대시보드, 지도, 검색, 계산, 보고서, 모바일 화면 구현 | 사용자 피드백 반영 |
| RAG/DB/Tool | JSON·텍스트 PDF 수집, 페이지 보존, PostgreSQL 전문 검색·저장, 계산 API 구현. 기존 SQLite FTS5/BM25도 선택 가능 | OCR, 문서 확충, 실제 모델 호출 검증, 검색 고도화 |
| 통합 | 검색·근거·보고서·계산 연결, 같은 네트워크용 LAN 실행 | 실제 선박 DB·AIS·기상 연결 |
| 평가 | 기능 테스트와 브라우저 동작 확인 | 검색 정확도·AI 답변 품질·성능 평가 |

현재 검색은 **키워드 기반**이며 임베딩·벡터 검색은 아직 없습니다. 기본 상태에서는 **검색된 문단을 그대로 표시**합니다. 외부 모델 연동 코드는 있지만 실제 호출은 아직 검증하지 않았습니다. 운항 수치는 가상 데이터이며 공식 CII 등급은 산정하지 않습니다.

## 2. 처음 실행하기

### 준비물

| 준비물 | 설명 |
|---|---|
| 프로젝트 폴더 전체 | 화면 파일뿐 아니라 `backend/`, `knowledge/`, 서버 파일도 함께 받아야 합니다. |
| 서버를 실행할 PC | Windows는 실행 파일을 제공하며, macOS/Linux는 Node 명령으로 실행합니다. |
| 접속할 기기의 웹 브라우저 | 서버 PC뿐 아니라 같은 네트워크의 PC·휴대폰·태블릿에서도 사용할 수 있습니다. 접속만 하는 기기에는 Node나 프로젝트 설치가 필요 없습니다. |
| Node.js 22.13 이상과 npm | PostgreSQL 연결용 `pg` 패키지를 설치해야 합니다. Windows 실행 도구는 호환되는 VS Code 런타임도 찾지만, 처음 `npm ci`에는 npm이 필요합니다. |
| PostgreSQL 12 이상 서버 | 로컬 PC 또는 접속 가능한 서버에 전용 사용자와 빈 데이터베이스가 필요합니다. 생성된 검색 열을 사용합니다. |
| API 키·인터넷 | 외부 AI 사용 시 필요합니다. 지도 배경·공식 원문 링크도 인터넷을 사용합니다. |

기본 검색·DB·계산에는 외부 AI API 키가 필요하지 않습니다. 다만 **`npm ci`와 PostgreSQL 서버 설정은 필요**합니다. DB는 데이터를 보관하는 장치이며, PostgreSQL은 별도로 실행되는 DB 서버입니다. 이 PC의 예전 SQLite 파일은 자동으로 PostgreSQL에 옮겨지지 않습니다.

PDF를 새로 수집할 때만 **Python 3.9 이상 + `requirements-pdf.txt`의 pypdf**가 추가로 필요합니다. 이미 등록된 PDF 검색에는 Python이 필요하지 않습니다.

### 1단계: PostgreSQL과 패키지 준비

아래 명령은 모두 **프로젝트 폴더를 연 PowerShell 터미널**에서 실행합니다. PostgreSQL을 설치하고 실행한 다음 SQL Shell (`psql`)에서 관리자 `postgres` 사용자로 접속해 다음 두 문장을 실행하세요. 예시 암호는 실제로 사용할 새 암호로 **두 곳 모두** 바꿉니다. 기존 DB가 있다면 새 전용 DB를 만들고, 기존 데이터를 지우지 마세요.

```sql
CREATE ROLE haedap LOGIN PASSWORD 'REPLACE_WITH_YOUR_PASSWORD';
CREATE DATABASE haedap OWNER haedap;
```

Node.js 22.13 이상을 설치하고 프로젝트 루트에서 패키지를 설치합니다. `npm ci`는 `package-lock.json`에 고정된 패키지를 설치하며, 기존 `node_modules` 내용은 교체합니다. 문서·보고서 DB나 PDF 원본은 건드리지 않습니다.

```powershell
node --version
npm ci
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

마지막 명령은 `.env`가 없을 때만 예시를 복사하며 기존 파일을 보존합니다. `.env`의 `DATABASE_URL`에서 `REPLACE_WITH_YOUR_PASSWORD`를 방금 설정한 암호로 바꿉니다. 암호에 `@`, `:`, `/`, `#` 같은 특수문자가 있으면 URL 인코딩이 필요하므로 처음에는 영문·숫자 암호를 사용하는 편이 쉽습니다. `.env`는 Git에서 제외되며 공유하거나 커밋하지 않습니다.

### 2단계: 서버 실행하기

1. 프로젝트 폴더에서 **`start.cmd`를 더블클릭**합니다.
2. 실행 창에 `HAEDAP: http://127.0.0.1:5173`이 나오면 창을 열어 둡니다.
3. 브라우저에서 **http://127.0.0.1:5173**을 엽니다.
4. 화면 위에 **문서 검색 연결됨**이 표시되면 준비가 끝났습니다.
5. 종료하려면 실행 창에서 **Ctrl+C**를 누릅니다.

다른 기기에서도 접속하려면 `start.cmd` 대신 **`start-lan.cmd`를 더블클릭**합니다. 두 실행 파일은 같은 서버·DB를 사용하며 접속 허용 범위만 다릅니다. 한 번에 필요한 실행 파일 하나만 켜세요.

첫 실행 시 **지정한 PostgreSQL 데이터베이스**에 테이블을 만들고, 비어 있으면 초기 문서 4개를 등록합니다. 기존 데이터가 있으면 유지합니다. DB 연결에 실패하면 서버가 시작되지 않으므로 실행 창의 오류와 아래 문제 해결 표를 확인하세요. `index.html`을 더블클릭하는 대신 서버 주소로 접속하세요.

### 터미널에서 실행하기: Windows

이 문서의 명령은 모두 **프로젝트 폴더를 연 PowerShell 터미널**에서 실행합니다. VS Code에서 프로젝트 폴더를 연 뒤 **터미널 → 새 터미널**을 선택하세요. `Get-Location`으로 현재 폴더를 확인할 수 있습니다.

```powershell
.\start.cmd
```

이 명령은 더블클릭과 동일한 실행 경로입니다. Windows 런처는 VS Code 런타임도 찾지만, 위 `npm ci`를 먼저 완료해야 합니다.

같은 네트워크의 다른 기기에도 열려면 다음을 실행합니다.

```powershell
.\start-lan.cmd
```

PowerShell 스크립트를 직접 호출해도 같은 방식으로 동작합니다.

```powershell
# 이 PC에서만 사용
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1

# 같은 네트워크의 다른 기기에서도 사용
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Lan
```

기본 포트가 사용 중이면 다른 번호로 실행합니다. 이 경우 접속 주소도 `http://127.0.0.1:5174`로 바뀝니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Port 5174
```

LAN 모드의 포트도 `powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Lan -Port 5174`로 지정합니다. 포트 우선순위는 실행 시 지정값 → `PORT` 환경변수 또는 `.env` 값 → 기본 `5173`입니다.

실행 환경만 확인하려면 아래 명령을 사용합니다. 실제로 선택한 실행 파일과 Node 버전이 표시됩니다. 이 명령은 PostgreSQL 연결 여부까지 검사하지 않습니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Task check
```

Node나 VS Code를 별도 경로에 설치했다면 `-NodePath '실제 실행 파일 경로'`를 지정하거나 `HAEDAP_NODE` 환경변수에 경로를 넣습니다. 호환되지 않는 런타임은 건너뛰고 다음 설치 위치를 확인합니다.

### Node가 설치된 PC 또는 macOS/Linux에서 실행하기

터미널에서 프로젝트 폴더로 이동한 뒤 실행합니다. 아래 명령은 Node가 PATH에 등록된 환경에서 사용합니다. Windows에서 `node`를 찾을 수 없으면 위의 `start.cmd` 방식을 사용하세요.

```powershell
node --version
npm start
```

LAN 모드와 포트 변경도 가능합니다.

```sh
# 같은 네트워크에 공유
npm run start:lan

# 포트까지 지정
node server.mjs --lan --port 5174
```

Windows 실행 도구는 이 PC에서 검증했습니다. macOS/Linux용 Node 명령은 공통 서버 코드를 사용하지만 해당 운영체제 실기기 검증은 아직 하지 않았습니다.

### 다른 기기에서 접속하기

1. 서버 PC와 사용할 기기를 같은 공유기·신뢰하는 네트워크에 연결합니다. PC가 유선이고 휴대폰이 Wi-Fi여도 같은 네트워크면 가능합니다.
2. 서버 PC에서 **`start-lan.cmd`** 또는 `start.ps1 -Lan`으로 실행합니다.
3. 실행 창의 `LAN (Wi-Fi): http://...:5173` 같은 줄을 찾습니다.
4. 다른 기기의 브라우저에 **그 LAN 주소를 그대로 입력**합니다. `127.0.0.1`, `localhost`, `0.0.0.0`은 다른 기기에서 입력할 접속 주소가 아닙니다.
5. 화면의 **문서 검색 연결됨**을 확인하고 검색·계산을 사용합니다. 서버 PC의 실행 창은 열어 둡니다.

출력 예시입니다. `192.168.0.20`은 예시이므로 실제 실행 창에 표시된 주소를 사용하세요.

```text
HAEDAP: http://127.0.0.1:5173
Mode: LAN
LAN (Wi-Fi): http://192.168.0.20:5173
```

네트워크 주소가 여러 개면 접속할 기기와 같은 Wi-Fi/이더넷 쪽 주소를 선택합니다. Wi-Fi를 바꿨거나 IP 주소가 바뀌면 서버를 재시작해 새 주소를 확인합니다. LAN 모드는 실행 PC의 IPv4 주소와 연결된 서브넷만 허용하며 IPv6·공개 인터넷 배포는 이번 범위에 포함하지 않습니다.

**접속 기기들은 서버 PC의 문서·현재 보고서 초안 1개를 함께 사용합니다.** 기기별 독립 계정은 없고 동시 편집은 저장 버전 충돌로 확인합니다. 서버를 끄거나 PC가 절전 상태가 되면 접속이 끊깁니다.

### 다른 기기에서 연결되지 않을 때: Windows 방화벽

서버 PC에서 LAN 주소가 열리는데 다른 기기에서 열리지 않으면 방화벽과 공유기의 기기 간 통신 차단 여부를 확인합니다. Windows 방화벽 허용이 필요할 때는 **신뢰하는 개인/도메인 네트워크에서** 관리자 PowerShell을 열고 프로젝트 폴더로 이동해 다음을 실행합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-lan-firewall.ps1 -Port 5173
```

이 도구는 지정 TCP 포트를 **개인/도메인 프로필 + 로컬 서브넷**에만 허용합니다. 같은 이름의 규칙이 있으면 기존 설정을 유지하고 표시합니다. 서버 포트를 바꿨으면 방화벽 설정도 같은 번호를 사용합니다. 실행 도구가 방화벽을 자동으로 변경하지는 않습니다.

현재 네트워크 종류를 확인하는 명령입니다.

```powershell
Get-NetConnectionProfile | Select-Object Name, NetworkCategory
```

`Public`이면 위 규칙은 해당 네트워크를 열지 않습니다. 가정·사무실 등 직접 신뢰할 수 있는 네트워크에서 사용하세요. 학교·공공 Wi-Fi는 기기 간 통신 자체를 차단할 수 있습니다. **2026-09-28 현재 이 PC의 Wi-Fi는 `Public`으로 확인했으며 공용 네트워크 방화벽 설정은 변경하지 않았습니다.** 실제 다른 기기에서의 접속은 별도 확인이 필요합니다.

추가한 규칙을 제거하려면 관리자 PowerShell에서 실행합니다.

```powershell
Remove-NetFirewallRule -Name 'Haedap-LAN-TCP-5173'
```

방화벽 설정 범위는 [Microsoft의 New-NetFirewallRule 문서](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule)를 참고하세요.

### 다른 PC에서 서버 자체를 실행하려면

프로젝트 폴더와 Node.js 22.13 이상 또는 호환 VS Code가 필요합니다. Windows에서는 `start.cmd`, macOS/Linux에서는 `npm start`로 실행합니다. 새 환경에 `data/`가 없으면 초기 문서로 새 DB가 만들어집니다. 기존 DB까지 옮기려면 [DB 저장과 백업](#7-db-저장과-백업)을 따릅니다. `.env`의 API 키는 새 서버에서 별도로 설정하고, 단순히 브라우저로 접속할 기기에는 프로젝트나 키를 복사하지 않습니다.

## 3. 화면에서 기능 확인하기

| 순서 | 할 일 | 정상 동작 |
|---|---|---|
| 1 | **규정 검색**에서 `연료 황 함유량` 검색 | 관련 문단과 출처 표시 |
| 2 | 인용 번호 또는 **근거 문서** 선택 | 저장 문서의 내용·버전·출처 확인 |
| 3 | **보고서에 담기** 선택 | 내용과 근거가 초안에 추가됨 |
| 4 | 제목·내용 확인 후 **초안 저장** 선택 | DB 저장 안내 표시 |
| 5 | **DB 초안 불러오기** 선택 | 저장한 초안이 열림. 기존 편집 내용이 있으면 교체 확인 표시 |
| 6 | **CII · 배출량**에서 수치 변경 후 **다시 계산하기** 선택 | 서버 계산 결과와 실행 기록 저장 |
| 7 | `초콜릿 케이크 레시피` 검색 | 근거가 충분하지 않다는 안내 표시 |

계산 예시: 연료 `100`, 계수 `3`, DWT `1000`, 거리 `100`이면 **CO₂ 300 t**, **단순 집약도 3000 gCO₂/(DWT·nm)**입니다. 초기 표시값은 로컬 미리보기이며, 다시 계산하기를 누르면 서버 Tool을 호출합니다.

**실행 환경 설정**의 `문서 검색 + DB + 계산 도구`는 실제 백엔드를 사용합니다. 샘플 모드는 기존 준비된 응답·오류 상황을 체험하며 보고서를 브라우저에 저장합니다. 두 모드는 검색 동작과 저장 위치가 다릅니다.

## 4. 구조와 파일 역할

| 용어 | 이 프로젝트에서의 의미 |
|---|---|
| UI / 프런트엔드 | 브라우저 화면과 버튼 동작 |
| 백엔드 | 검색·저장·계산 요청을 처리하는 서버 |
| DB / PostgreSQL | 문서와 보고서 등을 서버에 지속적으로 저장하는 장치. 예전 SQLite 파일 방식도 선택 가능 |
| 청크 | 긴 문서를 검색하기 좋은 크기로 나눈 문단 |
| RAG | 관련 문서를 검색한 뒤 그 근거를 모델에 제공해 답변하게 하는 방식 |
| LLM | 근거를 읽고 자연어 답변을 작성하는 AI 모델 |
| Tool | 정해진 입력을 검증하고 계산하는 함수 |
| API | 화면이나 다른 프로그램이 서버 기능을 호출하는 통로 |

```text
문서 JSON/PDF → 수집 명령 → 형식 검사·페이지별 문단 분할 → PostgreSQL에 저장·검색 색인 생성

화면에서 질문 → /api/ask → 관련 문단 검색
                           ├─ 기본: 검색 문단 표시
                           └─ 선택: 외부 모델 답변 생성 → 인용 확인 → 표시
                                      ↓
                              보고서에 담기 → DB 저장

계산 화면 → /api/tools/calculate_emissions → 입력 검사 → 계산 → 실행 기록 저장
```

| 파일 | 역할 |
|---|---|
| [index.html](index.html) | 화면 시작점과 스크립트 로딩 |
| [app.js](app.js) | 메뉴, 검색·보고서 화면, 기존 샘플 모드 |
| [backend-ui.js](backend-ui.js) | 실제 API 호출, 근거 표시, DB 저장·불러오기 |
| [style.css](style.css) | 기본 화면 스타일 |
| [operations.js](operations.js), [operations.css](operations.css) | 지도·항해 시각·사용 환경 화면 |
| [server.mjs](server.mjs) | 서버 시작, 빈 DB 초기화, API와 화면 파일 제공 |
| [backend/api.mjs](backend/api.mjs) | API 경로와 요청 검사 |
| [backend/network.mjs](backend/network.mjs) | 로컬/LAN 실행 옵션, 접속 주소·서브넷 검사 |
| [backend/knowledge.mjs](backend/knowledge.mjs) | 문서 형식 검사, 문단 분할, 검색어 처리 |
| [backend/db.mjs](backend/db.mjs), [backend/postgres.mjs](backend/postgres.mjs), [backend/sqlite.mjs](backend/sqlite.mjs) | DB 선택, PostgreSQL 저장·전문 검색, 선택적 기존 SQLite 저장·FTS5/BM25 검색 |
| [backend/rag.mjs](backend/rag.mjs) | 검색과 모델 생성 연결, 인용 검사, 실패 처리 |
| [backend/tools.mjs](backend/tools.mjs) | 배출량·항해 시각 계산 |
| [backend/validation.mjs](backend/validation.mjs) | 공통 입력 검사와 오류 형식 |
| [knowledge/seed.json](knowledge/seed.json) | 초기 문서 4개 |
| [scripts/ingest.mjs](scripts/ingest.mjs) | 문서를 수집하는 명령 |
| [scripts/migrate-sqlite-to-postgres.mjs](scripts/migrate-sqlite-to-postgres.mjs) | 기존 SQLite 문서·청크·보고서·기록을 빈 PostgreSQL DB로 복사 |
| [scripts/ingest-pdf.mjs](scripts/ingest-pdf.mjs), [scripts/extract-pdf.py](scripts/extract-pdf.py) | PDF 1~3개 수집 명령과 Python 페이지별 텍스트 추출기 |
| [backend/pdf.mjs](backend/pdf.mjs), [requirements-pdf.txt](requirements-pdf.txt) | PDF 페이지를 기존 문서 형식으로 변환, 선택적 추출 의존성 |
| [tests/pdf.test.mjs](tests/pdf.test.mjs) | 페이지 보존, 기존 DB 이전, PDF 추출·검색, 화면 출처 표시 검증 |
| [tests/backend.test.mjs](tests/backend.test.mjs), [tests/server.test.mjs](tests/server.test.mjs) | 백엔드·HTTP 테스트 |
| [tests/postgres.test.mjs](tests/postgres.test.mjs) | PostgreSQL 호환 엔진에서 DB·API·기존 DB 복사 검증 |
| [tests/network.test.mjs](tests/network.test.mjs), [tests/launcher.test.mjs](tests/launcher.test.mjs) | 네트워크 허용 범위와 CMD·PowerShell·LAN 실행 검증 |
| [scripts/browser-smoke.mjs](scripts/browser-smoke.mjs) | 실제 Chrome 검증 |
| [.env.example](.env.example) | 선택적 서버 설정 예시 |
| [start.ps1](start.ps1), [start.cmd](start.cmd), [start-lan.cmd](start-lan.cmd) | Windows 로컬·LAN 실행·테스트·수집 도구 |
| [setup-lan-firewall.ps1](setup-lan-firewall.ps1) | 선택적 개인/도메인 네트워크 방화벽 설정 |

`fonts/`와 `vendor/leaflet/`에는 글꼴과 지도 라이브러리가 있습니다. `styles.css`는 이전 파일이며 현재 화면에서는 사용하지 않습니다. `.backup/`, `.replica/`, `.verification/`는 작업·검증 자료로, 새로 받은 프로젝트에는 없을 수 있습니다.

## 5. 검색할 문서 추가하기

기존 수집기는 **JSON 문서 배열**을 받습니다. 아래 JSON 절차를 그대로 사용할 수 있으며, 텍스트 PDF는 이 절 끝의 **PDF 수집** 절차로 등록합니다. URL 자동 수집과 이미지 OCR은 아직 없습니다.

### 1단계: 문서 파일 만들기

`knowledge/my-documents.json` 파일을 만들고 다음 내용을 UTF-8로 저장합니다. 검색 연습용 가상 문서 예시입니다.

```json
[
  {
    "id": "sample-contact-guide",
    "title": "교육용 연락처 확인 안내 (가상)",
    "kind": "sample",
    "reference": "TRAINING-CONTACT-01 · 1절",
    "version": "1.0",
    "reviewedAt": "2026-09-28",
    "language": "ko",
    "sections": [
      {
        "heading": "교육용 연락처 확인",
        "text": "교육용 연락처는 담당자가 제공한 목록에서 확인합니다. 이 내용은 검색 연습을 위한 가상 문서이며 실제 비상 연락 절차가 아닙니다."
      }
    ]
  }
]
```

| 항목 | 작성 방법 |
|---|---|
| `id` | 고정 문서 이름. 영문 소문자·숫자·하이픈만 사용하고 개정 시에도 유지 |
| `title` | 화면에 보일 문서 제목 |
| `kind` | 공식 안내 요약 `official-summary`, 선내 문서 `onboard`, 가상 자료 `sample`. PDF 수집기는 `pdf`를 지정 |
| `reference` | 문서 번호·규정 조항 등 사람이 확인할 출처 위치 |
| `version` | 작성·개정 버전 |
| `reviewedAt` | 실제 확인일. `YYYY-MM-DD` 형식 |
| `language` | 한국어 `ko`, 영어 `en` |
| `url` | 원문 HTTPS 주소. `official-summary`에서는 필수, 나머지에서는 선택 |
| `sections` | 절 제목 `heading`과 본문 `text`의 목록. 선택적 `page`는 1~5000 정수이며 `pdf`에서는 필수 |

분류 이름만으로 공식성이 검증되지는 않습니다. 등록자가 원문과 요약의 정확성을 확인해야 합니다.

### 2단계: DB에 등록하기

서버를 켜 둔 경우 별도 터미널에서 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Task ingest -Document .\knowledge\my-documents.json
```

결과의 `created`는 새 문서 등록, `updated`는 같은 ID의 새 버전 등록, `unchanged`는 내용이 같아 기존 문서를 유지했다는 뜻입니다.

### 3단계: 검색 확인하기

앱에서 `교육용 연락처`를 검색합니다. 새 문서와 근거가 표시되면 완료입니다. 화면 위 문서 개수 표시까지 갱신하려면 새로고침합니다.

개정할 때는 같은 `id`를 유지하고 본문·`version`·`reviewedAt`을 수정해 재수집합니다. 새 버전만 검색하고 이전 버전은 기존 보고서 인용을 위해 보존합니다.

**파일 수정만으로 기존 DB는 바뀌지 않습니다.** `knowledge/seed.json`을 수정했을 때도 수집 명령을 다시 실행합니다. 초기 문서는 빈 DB에만 자동 등록됩니다.

### PDF 수집: 페이지 추출 → 기존 청크 → PostgreSQL 검색

프로젝트 루트에서 실행합니다. Python을 설치한 뒤 다음 명령으로 PDF용 의존성을 준비하세요. Windows에서 `python` 대신 `py`를 사용한다면 `py -m pip install -r requirements-pdf.txt`로 설치하고, `py -c "import sys; print(sys.executable)"`로 나온 경로를 `HAEDAP_PYTHON`에 지정합니다.

```powershell
python -m pip install -r requirements-pdf.txt
# python 명령이 없는 경우 실제 실행 파일의 경로 지정
# $env:HAEDAP_PYTHON = 'C:\Python312\python.exe'
```

PDF 원본을 `data/pdfs/ABS`, `DNV`, `KR`, `MEPC`, `MSC`, `LR` 중 해당 폴더에 보관합니다. `data/` 전체가 Git 제외 대상이므로 원본과 DB는 커밋되지 않습니다. 수집기는 하위 폴더를 자동 순회하지 않고 **지정한 PDF 1~3개만** 처리합니다. 다음 예제 파일이 없다면 실제 파일명으로 바꾸세요.

```powershell
# Node가 PATH에 없어도 기존 Windows 런처로 PDF 1개 수집
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Task ingest-pdf -Document "data/pdfs/ABS/MVR Part-5D-Offshore-Support-Vessels-for-Specialized-Services-jul-2026.pdf"

# Node/npm을 설치한 환경에서는 아래 명령도 가능
npm run ingest:pdf -- "data/pdfs/ABS/MVR Part-5D-Offshore-Support-Vessels-for-Specialized-Services-jul-2026.pdf"
# 여러 개: npm run ingest:pdf -- "data/pdfs/ABS/one.pdf" "data/pdfs/DNV/two.pdf"
```

기본 대상은 `.env`의 `DATABASE_URL`이 지정한 PostgreSQL DB입니다. 수집 명령과 서버가 **같은 DB 연결 주소**를 사용해야 검색에 보입니다. 다른 DB에서 시험하려면 별도 빈 PostgreSQL DB를 만들고 두 프로세스에 같은 `DATABASE_URL`을 설정하세요. 기존 SQLite 자료를 계속 사용하거나 이전하려면 아래 [DB 저장과 백업](#7-db-저장과-백업)을 먼저 확인하세요.

성공 출력의 `created` / `updated` / `unchanged`와 함께 `pages`, `textPages`, `emptyPages`, `characters`를 확인합니다. 새 수집에는 `chunks` 개수도 표시됩니다. 동일 경로·동일 내용·동일 메타데이터의 재수집은 중복을 만들지 않습니다. 같은 경로의 수정본은 새 개정으로 저장하고 이전 인용을 보존합니다. 파일을 옮기거나 이름을 바꾸면 새 문서 ID가 됩니다.

수집 후 서버를 켜고 규정 검색에서 PDF 본문의 단어(위 ABS 예: `offshore support vessels`)를 검색합니다. **전체 문서** 또는 **선내 문서** 필터를 사용하세요. `IMO 공식 안내` 필터는 기존 요약 문서만 검색합니다. 결과의 근거 위치에 **파일명 · PDF p.번호**가 표시되고 보고서에 담을 때도 페이지가 포함됩니다. `/api/search`와 `/api/ask`의 `evidence`에는 `document_id`, `title`, `page`, `heading`, `text`가 있습니다. `document_id`는 개정별 ID이고 제목은 `documents.title`과 연결하여 반환합니다.

- `page`는 표지 포함 **1부터 시작하는 PDF 물리 페이지**입니다. 인쇄 쪽수와 다를 수 있습니다. 페이지가 없는 기존 JSON 청크는 DB/API에서 `null`입니다.
- 페이지의 첫 번째 텍스트 줄을 임시 `heading`으로 사용합니다. 규정의 조항 계층을 자동 해석하지 않습니다. 청크는 페이지 경계를 넘지 않고 기존 최대 900자 분할·토큰화를 사용합니다. PostgreSQL은 `tsvector`/`ts_rank_cd`, 선택적 SQLite는 FTS5/BM25로 검색합니다.
- PDF 메타데이터는 파일명, 상대 경로, 파일 SHA-256 버전, 파일 수정일을 사용합니다. 기존 `reviewedAt` 필드에 들어가는 PDF 파일 수정일은 사람의 검토일이나 승인 증명이 아닙니다.
- PDF당 128 MiB, 5,000페이지, 추출 본문 20,000,000자, 변환 절 10,000개, 추출 시간 180초로 제한합니다. 일반 JSON의 100절·100,000자 제한은 유지합니다.
- 빈/이미지 페이지는 번호를 보존하면서 검색에서 제외하고 `emptyPages`로 알립니다. 전체가 이미지인 PDF는 OCR 필요 오류로 종료합니다. 암호화 PDF는 지원하지 않습니다.
- 표·수식·다단 편집의 읽기 순서나 의미를 재구성하지 않습니다. 원문 PDF를 웹으로 제공하거나 외부 서비스에 업로드하지 않습니다. ChromaDB·임베딩·벡터·하이브리드 검색은 구현하지 않았습니다.

## 6. AI 답변 생성 연결하기

설정하지 않아도 문서 검색·DB 저장·계산은 동작합니다.

1. `.env.example`을 복사해 **`.env`**라는 이름으로 저장합니다. 이미 `.env`가 있으면 덮어쓰지 말고 내용을 수정합니다. `.env.txt`가 되지 않도록 확인하세요.
2. 아래 값을 채웁니다. 모델에는 사용할 수 있는 Responses API·Structured Outputs 지원 모델의 실제 ID를 넣습니다.

```dotenv
DATABASE_URL=postgresql://haedap:REPLACE_WITH_YOUR_PASSWORD@127.0.0.1:5432/haedap
OPENAI_API_KEY=발급받은_실제_API_키
OPENAI_MODEL=사용할_실제_모델_ID
```

3. 서버를 종료했다가 다시 실행하고 브라우저를 새로고침합니다.
4. **실행 환경 설정 → 검색 근거로 AI 답변 생성**을 켭니다. 실행 방식은 `문서 검색 + DB + 계산 도구`로 둡니다.
5. 질문을 검색하고 AI 초안 또는 실패 시 근거 문단 전환 안내를 확인합니다.

AI 옵션을 켜면 질문과 검색 문단이 외부 모델로 전송됩니다. 키는 서버에서만 사용하고 `.env`는 Git 저장 대상에서 제외합니다. 호출 실패·잘못된 인용이 감지되면 검색 문단으로 전환합니다. 인용문의 존재 검사와 답변 전체의 정확성 평가는 별개입니다.

현재 모델 검증은 모의 응답으로 진행했습니다. 실제 호출·비용·답변 품질은 추가 확인이 필요합니다. 요청 형식은 [OpenAI Structured Outputs 문서](https://developers.openai.com/api/docs/guides/structured-outputs)를 참고하세요.

## 7. DB 저장과 백업

기본 저장 위치는 **`.env`의 `DATABASE_URL`이 가리키는 PostgreSQL DB**입니다. DB 주소·계정·암호를 바꾸면 서버와 수집 명령을 다시 시작하세요. 기존 SQLite 파일은 자동으로 이동하거나 삭제하지 않습니다.

| 내용 | 테이블 |
|---|---|
| 문서와 개정 이력 | `documents` |
| 분할한 문단과 검색 색인 | PostgreSQL: `chunks`의 `search_vector`와 GIN 색인. SQLite: `chunks`, `chunks_fts` |
| 보고서 초안 | `reports` |
| Tool 입력·출력·계산 버전 | `tool_runs` |
| 질문·검색 근거·응답 | `queries` |

현재 UI는 **현재 초안 1개**를 저장·불러옵니다. 계정·권한 관리나 보고서 목록은 아직 없습니다. 여러 창의 편집은 버전 충돌로 감지하며, DB 초안을 다시 불러와 해결합니다. 기존 브라우저 초안을 DB 내용으로 자동 덮어쓰지 않습니다.

두 DB 방식 모두 `chunks.page`에 PDF 페이지 번호를 저장합니다. `title`은 `documents`에 한 번 저장하고 검색 응답에 연결합니다. 기존 SQLite v1 파일은 SQLite 모드로 열 때 v2로 자동 이전하며 기존 청크 페이지는 `NULL`로 남습니다.

PostgreSQL 전체 백업은 `pg_dump`를 사용합니다. 다음 명령은 프로젝트 폴더에서 실행하는 예시이며 `haedap` DB의 백업 파일을 만듭니다. **같은 파일명으로 다시 실행하면 기존 백업을 덮을 수 있으므로** 매번 다른 파일명을 사용하세요. 암호 입력은 `pg_dump`가 요청합니다. 복원은 기존 데이터를 덮을 수 있으므로 이 문서의 자동 명령에 포함하지 않았습니다. 실제 복원 전에는 현재 DB를 별도로 백업하고 대상 DB를 확인하세요.

```powershell
pg_dump -h 127.0.0.1 -U haedap -d haedap -Fc -f .\haedap-backup.dump
```

기존 `data/haedap.sqlite`가 있다면 다음 중 하나를 선택할 수 있습니다.

- **기존 파일로 계속 실행:** `.env`에 `HAEDAP_DB_BACKEND=sqlite`와 `HAEDAP_DB_PATH=data/haedap.sqlite`를 지정합니다. 이 모드는 기존 FTS5/BM25 검색을 유지합니다. 서버를 끄고 DB 파일을 백업하세요. 실행 중에는 `-wal`, `-shm` 파일이 있을 수 있으므로 DB 파일 하나만 복사하지 마세요.
- **PostgreSQL로 복사:** 먼저 서버를 종료하고 SQLite 파일을 백업합니다. **비어 있는 전용 PostgreSQL DB**를 준비하고 `.env`에 `DATABASE_URL`을 설정한 뒤 다음 명령을 실행합니다. 스크립트는 원본 SQLite를 읽기 전용으로 열어 문서·청크·페이지·보고서·계산/질문 기록을 복사하며, 대상에 데이터가 있으면 중단합니다. 원본 파일은 그대로 둡니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Task migrate-postgres -Document data/haedap.sqlite
# Node/npm이 PATH에 있다면: npm run migrate:postgres -- data/haedap.sqlite
```

복사 완료 후 `.env`에서 `HAEDAP_DB_BACKEND=sqlite`를 지우거나 주석 처리하고 서버를 다시 시작해 `/api/health`, 문서 검색, 기존 보고서를 확인하세요. 이미 PostgreSQL에 초기 문서 4개를 시드했다면 이 복사 스크립트는 덮어쓰지 않으며, 별도의 새 빈 DB를 마련해야 합니다.

화면의 **초안 백업 (.json)**은 현재 보고서만 내보내는 기능으로 전체 DB 백업과 다릅니다. `data/`와 `.env`는 Git 저장 대상에서 제외되므로 코드를 push해도 DB 내용·PDF 원본·암호는 함께 이동하지 않습니다.

## 8. 기능 구현·수정 순서

### 검색 기능 수정

1. `backend/knowledge.mjs`의 `validateDocument`, `prepareDocument`, `tokens`에서 문서 형식·분할·검색어 처리를 확인합니다.
2. `backend/db.mjs`의 분기와 `backend/postgres.mjs`의 `importDocuments`, `retrieve`에서 수집·검색을 확인합니다. SQLite 모드 수정 시 `backend/sqlite.mjs`도 확인합니다.
3. 현재 검색은 단어·한국어 2글자 조각·한영 용어 사전을 적용합니다. PostgreSQL은 `tsvector`와 `ts_rank_cd`를, SQLite는 FTS5/BM25를 사용합니다. 검색 순위가 두 DB에서 완전히 같지는 않습니다. 의미 기반 검색을 추가하려면 임베딩 생성·저장·검색을 별도로 구현합니다.
4. 검색어 처리나 청크 구조를 바꾸면 기존 색인도 갱신합니다. 현재는 분할 버전 문자열을 올리고 문서를 재수집해 새 리비전을 만드는 방식을 사용할 수 있습니다. 이전 인용은 보존합니다.
5. 한영 질문·관련 없는 질문·문서 필터를 테스트합니다.

### 새 계산 Tool 추가

1. `backend/tools.mjs`에 계산 함수를 추가합니다. 입력 단위·허용 범위를 검증하고 결과 단위·계산 버전·가정을 반환합니다.
2. 같은 파일의 `toolDefinitions`와 `runTool`의 허용 함수 목록에 등록합니다. 반환값의 `version`은 실행 기록 저장에 필요합니다.
3. 등록한 Tool은 `POST /api/tools/도구이름`으로 호출할 수 있습니다.
4. 화면에서 사용하려면 `backend-ui.js`에 API 호출을 추가하고 `app.js`의 버튼·폼과 연결합니다.
5. 정상값과 해당 계산의 경계 조건을 테스트합니다.

기존 `calculate_emissions`는 배출량·단순 집약도를, `voyage_time`은 UTC 경과시간·선내 시계 표시 차이를 계산합니다. 시각 Tool은 API로 제공되며 기존 지도·시각 화면은 로컬 계산을 유지합니다. 자연어에서 계산 숫자를 추출하는 기능은 없습니다.

### DB·API·화면 연결 수정

1. 저장 기능은 `backend/db.mjs`, 요청 경로는 `backend/api.mjs`에서 수정합니다.
2. 기존 DB를 고려합니다. `CREATE TABLE IF NOT EXISTS`만 바꿔서는 이미 생성된 테이블이 변경되지 않습니다. 스키마 변경에는 기존 데이터를 보존하는 마이그레이션을 추가해야 합니다.
3. SQL에 입력값을 직접 문자열로 붙이지 않고 매개변수를 바인딩합니다. 기존 버전 충돌 검사를 유지합니다.
4. `backend-ui.js`에서 API를 호출하고 `app.js`에 로딩·성공·오류·근거 없음 상태를 연결합니다.
5. 서버 코드 수정 뒤에는 서버를 재시작합니다. 자동 재시작 기능은 없습니다. 화면 코드 수정 후에는 브라우저를 새로고침합니다.

### AI 답변 처리 수정

`backend/rag.mjs`의 `answerQuestion`이 검색·선택적 계산·답변 생성·기록을 묶습니다. `generateGrounded`는 모델 호출과 청크 ID·인용문 검사를 담당합니다. 설정 누락, 호출 실패, 근거 부족을 구분하는 흐름을 유지하세요.

수정 후에는 관련 테스트와 README를 함께 갱신합니다. 추가 구현 설명은 [백엔드 상세 문서](docs/BACKEND.md)를 참고하세요.

## 9. API 직접 호출하기

서버를 켜 둔 뒤 **별도의 PowerShell 터미널**에 순서대로 입력합니다. 다른 포트로 실행했다면 `$base`를 바꿉니다.

```powershell
# 1. 서버 상태 확인과 요청 토큰 받기
$base = 'http://127.0.0.1:5173'
$health = Invoke-RestMethod -Uri "$base/api/health"
$health
$headers = @{ 'X-Haedap-Token' = $health.csrfToken }

# 2. 문서 검색
$askBody = @{ question = '연료 황 함유량'; mode = 'extractive' } | ConvertTo-Json
Invoke-RestMethod -Uri "$base/api/ask" -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($askBody))

# 3. 배출량 계산
$toolBody = @{ fuel = 100; factor = 3; dwt = 1000; distance = 100 } | ConvertTo-Json
Invoke-RestMethod -Uri "$base/api/tools/calculate_emissions" -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($toolBody))
```

첫 응답의 `ok`가 `True`이면 연결된 상태입니다. 검색 응답의 `evidence`는 근거 문단, `statements`는 표시 내용입니다. 계산의 `result.emission`은 `300`입니다. 서버를 재시작했다면 첫 단계에서 토큰을 다시 받습니다.

| 메서드·경로 | 용도 | 주요 입력 |
|---|---|---|
| `GET /api/health` | 연결 상태·모델 설정 여부·토큰 | 없음 |
| `GET /api/documents` | 문서 버전과 청크 | 없음 |
| `POST /api/search` | 근거만 검색 | `question`, `filter`: `all` / `imo` / `manual` |
| `POST /api/ask` | 검색·선택적 생성·계산 | `question`, `filter`, `mode`: `extractive` / `llm`, `language`: `ko` / `en`, 선택적 `calculation` |
| `GET /api/reports/current` | 초안 불러오기 | 없음 |
| `POST /api/reports/current` | 초안 저장 | `title`, `type`, `text`, `sources`, `version` |
| `GET /api/tools` | Tool 목록 | 없음 |
| `POST /api/tools/calculate_emissions` | 배출량 계산 | `fuel`, `factor`, `dwt`, `distance` |
| `POST /api/tools/voyage_time` | 시각 계산 | `start`, `end`, `before`, `after` |

`sources`는 문서 ID 배열입니다. 새 보고서의 `version`은 `0`, 이후에는 불러온 최신 버전을 전달합니다. `type`은 `규정 검토`, `일일 운항`, `배출량 검토`, `종합 검토` 중 하나입니다. `calculation`은 배출량 Tool과 같은 입력 객체입니다. 시각 Tool에는 `2026-09-18T00:00:00Z` 형식의 UTC 시각과 분 단위 선내 오프셋을 전달합니다.

기본 실행은 **이 PC 전용**, `--lan` 실행은 **같은 네트워크의 기기용**입니다. LAN 주소로 API를 호출할 때는 위 예제의 `$base`도 실행 창의 주소로 바꿉니다. POST에는 JSON과 요청 토큰이 필요하고 요청 크기는 1MB로 제한됩니다. LAN에서도 동일 출처 검사와 비공개 파일 차단을 유지합니다. 요청 토큰은 로그인 기능이 아니며 사용자별 권한·공개 인터넷 배포는 별도 구현 범위입니다.

## 10. 테스트하기

### 백엔드·HTTP 테스트

`npm ci`를 마친 뒤 실행 도구로 테스트할 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Task test
```

Node가 인식된다면 `npm test`도 가능합니다. 테스트는 실제 사용 DB와 별도의 임시 DB를 사용합니다. PostgreSQL 테스트는 패키지에 포함된 PostgreSQL 호환 엔진(PGlite)과 연결 프로토콜로 문서 수집·검색·저장·API·SQLite 자료 복사를 검증하므로 별도 DB 서버 없이 실행됩니다. 독립적으로 설치한 PostgreSQL 서버에 대한 실연동은 아직 검증하지 않았습니다. 기존 SQLite·네트워크·런처 테스트도 유지합니다. Windows 런처 로그는 `.verification/launcher-*/`에 보관합니다.

**2026-10-08 검증: 26개 통과, 실패·건너뜀 0개.** 실제 ABS PDF 1개(387페이지, 1,110청크)를 지정한 전체 테스트입니다. SQLite FTS5/BM25, PostgreSQL 호환 엔진의 검색·API·자료 복사, Windows 로컬/LAN 실행을 포함합니다. 독립 PostgreSQL 서버 연결과 브라우저 수동 검토는 이번 변경에서 수행하지 않았습니다.

**2026-09-28 확인 결과: 15개 통과, 실패 0개.** CMD·PowerShell에서 서버 시작 및 이 PC의 실제 LAN 주소를 통한 API 호출까지 확인했습니다. 독립된 휴대폰·다른 PC에서의 연결은 아직 직접 검증하지 않았습니다. Windows 런처 테스트는 다른 운영체제에서는 건너뜁니다.

### PDF 자동 검증

전체 테스트 명령은 기존과 같습니다. Python/pypdf가 없으면 추출기 테스트 1개를 건너뛰며, 페이지 변환·DB 이전·검색·UI 표시 테스트는 계속 실행합니다. 실제 PDF 검증은 파일 하나를 명시했을 때만 수행합니다.

```powershell
# 위에서 Python 의존성을 설치한 뒤 프로젝트 루트에서 실행
$env:HAEDAP_TEST_PDF = (Resolve-Path "data/pdfs/ABS/MVR Part-5D-Offshore-Support-Vessels-for-Specialized-Services-jul-2026.pdf").Path
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Task test
Remove-Item Env:HAEDAP_TEST_PDF
```

PDF 테스트는 임시 DB를 사용하고 종료 시 정리합니다. 작은 3페이지 PDF 테스트 자료 1개와 명시한 실제 PDF 1개만 사용하며, 빈 페이지 번호, 재수집, 구버전 DB 보존, 기존 JSON 공존, 문서명·페이지 표시를 확인합니다. PDF 내용이 바뀌거나 다른 파일을 선택하면 검증용 질문 `offshore support vessels`도 해당 문서에 맞춰야 합니다.

**2026-10-01 검증: 기존 15개 + PDF 관련 6개 = 21개 통과, 실패·건너뜀 0개.** Python 3.12.10 / pypdf 6.19.0과 VS Code의 Node v24.20.0을 사용했습니다. 실제 대상은 ABS Part 5D PDF 1개(387페이지, 804,656자, 1,110청크)이며 다른 6개 원본은 수집하지 않았습니다. 별도 `.verification/pdf-cli-*/test.sqlite`에서 기존 JSON CLI → PDF CLI 등록도 확인했습니다. PDF 검색의 문서명·페이지 표시와 보고서 전달은 자동 UI 테스트로 검증했고, 기존 Chrome 점검도 11개 통과했습니다. PDF 페이지 표시의 수동 브라우저 검토나 전체 문서의 추출 정확도 평가는 수행하지 않았습니다. 처음 샌드박스 실행의 Windows 자식 프로세스 정리 제한을 해소한 뒤 전체 테스트를 통과했습니다.

이번 환경에 준비한 Python은 Git에서 제외되는 `.verification/pdf-runtime/python.exe`에 있습니다. 이 PC에서는 `$env:HAEDAP_PYTHON = (Resolve-Path '.verification/pdf-runtime/python.exe').Path`로 사용할 수 있습니다. 새로 받은 프로젝트에는 이 검증 런타임이 없으므로 위 Python 설치 절차를 따르세요.

### 실제 Chrome 검증

Chrome이 설치돼 있고 Node가 인식된다면 다음을 실행합니다.

```powershell
node scripts/browser-smoke.mjs
```

실제 LAN 주소로 화면·API 연결을 확인하려면 `node scripts/browser-smoke.mjs --lan`을 사용합니다. 이 검증도 같은 PC의 브라우저에서 실행하므로 다른 기기의 방화벽 통과 여부를 대신 확인하지는 않습니다.

Node 대신 현재 사용자 경로에 설치된 VS Code를 사용하는 경우입니다. 다른 곳에 설치했다면 실행 파일 경로를 바꿉니다.

```powershell
$env:ELECTRON_RUN_AS_NODE = '1'
& "$env:LOCALAPPDATA\Programs\Microsoft VS Code\Code.exe" scripts/browser-smoke.mjs | Out-Host
```

기본 Chrome 경로는 `C:/Program Files/Google/Chrome/Application/chrome.exe`입니다. 다르면 실행 전에 `$env:CHROME_PATH`에 실제 경로를 지정합니다.

별도의 테스트 서버·DB와 숨김 브라우저로 검색 → 근거 보기 → 보고서 저장·불러오기, 계산, 새 문서 반영, 모바일 화면을 확인합니다. 결과는 `.verification/backend-browser-*/results.json`, 화면은 같은 폴더의 `report-mobile.png`에 저장됩니다.

**2026-09-28 확인 결과: 로컬 주소와 실제 Wi-Fi 주소 각각 11개 점검 통과, JavaScript 예외 없음.** 같은 PC의 Chrome에서 두 접속 경로를 확인한 결과입니다. 독립된 다른 기기 연결, 실제 모델의 답변 정확도·운항 적합성 평가 결과는 아닙니다.

## 11. 문제 해결

| 증상 | 확인·해결 방법 |
|---|---|
| `node`·`npm`을 찾을 수 없음 | Node.js 22.13 이상과 npm을 설치한 뒤 새 터미널에서 `node --version`, `npm --version`, `npm ci`를 실행합니다. `start.cmd`가 VS Code 런타임을 찾아도 패키지는 먼저 설치해야 합니다. |
| `Cannot find package 'pg'` | 프로젝트 루트에서 `npm ci`를 실행하고 다시 시작합니다. |
| `DATABASE_URL is required` | `.env.example`을 `.env`로 복사하고 `DATABASE_URL`의 사용자·암호·주소·DB 이름을 실제 값으로 바꿉니다. |
| PostgreSQL 연결 거부·인증 실패 | PostgreSQL 서버 실행 여부, 포트 5432, 전용 DB와 사용자, `.env` 암호를 확인합니다. DB를 만든 뒤 서버를 다시 시작합니다. |
| `node:sqlite`를 찾을 수 없음 | SQLite 호환 모드·기존 DB 복사·테스트에는 Node.js 22.13 이상이 필요합니다. |
| `Port 5173 is in use` | 기존 실행 창을 확인하거나 `-Port 5174`로 실행하고 접속 주소도 변경합니다. |
| 백엔드 연결 실패 | 서버 실행 여부와 주소를 확인합니다. HTML 파일 직접 열기는 사용하지 않습니다. |
| 이 PC에서는 열리지만 다른 기기는 실패 | `start-lan.cmd` 실행 여부, 실행 창의 LAN 주소, 같은 네트워크 연결, 방화벽 프로필·포트, 공유기의 기기 격리를 순서대로 확인합니다. |
| LAN 실행 후 주소가 표시되지 않음 | Wi-Fi/유선 IPv4 연결을 확인하고 서버를 재시작합니다. |
| LAN에서 403 응답 | 실행 창에 표시된 IP·포트로 접속합니다. 네트워크 변경 후에는 서버를 재시작합니다. |
| 재시작 후 요청 토큰 오류 | 화면을 새로고침하거나 `/api/health`에서 토큰을 다시 받습니다. |
| 문서 수정이 반영되지 않음 | 수정 후 ingest 명령을 실행했는지, 서버와 수집 명령이 같은 `DATABASE_URL`(또는 SQLite 경로)을 사용하는지 확인합니다. |
| 수집 시 JSON 오류 | 큰따옴표·쉼표·최상위 배열·필수 항목·UTF-8 저장을 확인합니다. JSON에는 주석을 넣지 않습니다. |
| PDF 수집 시 Python/pypdf 오류 | `python -m pip install -r requirements-pdf.txt` 실행 후 `HAEDAP_PYTHON`이 같은 Python을 가리키는지 확인합니다. |
| PDF 추출 텍스트가 없음 | 이미지/스캔 PDF는 OCR이 필요합니다. 현재 OCR은 미구현입니다. 일부 빈 페이지는 `emptyPages`에서 확인합니다. |
| PDF는 등록됐지만 검색되지 않음 | 전체/선내 문서 필터, 본문에 실제 존재하는 단어, 서버·수집기의 DB 연결 설정이 같은지 확인합니다. |
| 검색 근거가 없음 | 등록 본문과 필터를 확인하고 핵심 용어로 검색합니다. 현재는 의미 기반 검색이 아닙니다. |
| AI 옵션 비활성화 | 키와 모델 ID를 모두 설정한 뒤 서버 재시작·화면 새로고침을 합니다. |
| AI 대신 근거 문단 표시 | 기본 모드이거나 모델 실패 후 전환입니다. 설정·연결·모델 사용 권한을 확인합니다. |
| 보고서 버전 충돌 | 필요한 편집 내용을 먼저 파일로 보관하고 DB 초안을 불러와 변경 내용을 반영합니다. |
| 샘플 모드 초안이 DB에 없음 | 샘플 모드는 브라우저 저장입니다. 실제 문서 검색 모드에서 저장합니다. |
| 지도 배경만 나오지 않음 | 인터넷·지도 스위치·저사양 모드를 확인합니다. 지도와 로컬 검색은 별개입니다. |
| 코드 수정이 반영되지 않음 | 서버 코드는 서버 재시작, 화면 코드는 브라우저 새로고침이 필요합니다. |

## 12. 다음 작업과 문서 관리

다음 작업은 승인 문서 확충·개정 관리, 실제 모델 연결과 품질 평가, 검색 평가용 질문·정답 근거 작성, 실제 선박 DB·AIS·기상 통합입니다. 텍스트 PDF 수집은 구현됐으며 OCR·표 구조 복원은 남아 있습니다. 필요에 따라 벡터 검색, 계정·권한, 다중 보고서, 배포·복구 체계를 추가합니다.

**앞으로 작업이 끝날 때마다 이 README를 함께 업데이트합니다.** 변경 이력뿐 아니라 사용자가 따라 할 본문도 수정합니다.

| 바뀐 내용 | 함께 수정할 항목 |
|---|---|
| 기능·완료 범위 | 현재 구현 상태, 화면 확인, 다음 작업 |
| 설치·실행·설정 | 처음 실행하기, AI 설정, 문제 해결 |
| 파일·API | 구조, 구현 방법, API 예제 |
| 문서 형식·DB | 문서 추가, 백업, 기존 데이터 이전 절차 |
| 테스트 | 실행 명령, 날짜, 실제 결과·미검증 범위 |
| 모든 변경 | 마지막 업데이트 날짜와 변경 이력 |

지속적인 작업 지침은 [AGENTS.md](AGENTS.md)에 남겨 두었습니다. 상세 문서를 추가해도 처음 실행하고 기본 기능을 수정하는 데 필요한 절차는 README에 유지합니다. 코드와 문서가 다르면 실제 구현을 확인해 갱신합니다.

## 13. 변경 이력

| 날짜 | 변경 내용 | 검증·남은 사항 |
|---|---|---|
| 2026-10-08 | 기본 DB를 PostgreSQL로 전환, 전문 검색과 PDF 페이지·보고서 저장, SQLite 읽기 전용 복사 도구 및 선택적 FTS5/BM25 호환 모드 추가 | 실제 PDF 1개 포함 전체 26개 테스트 통과. 독립 PostgreSQL 서버 실연동은 미검증 |
| 2026-10-01 | 최소 PDF ingest 추가: 페이지별 추출 → 기존 청크 → SQLite FTS5/BM25, 페이지 열 마이그레이션, 검색·보고서 출처 표시와 실행 안내 | 기존 포함 21개 테스트·기존 Chrome 11개 통과. 실제 PDF 1개 387페이지/1,110청크 확인. OCR·추출 품질 평가·벡터 검색 미구현 |
| 2026-09-28 | 런타임 자동 탐색 보강, 로컬·LAN 실행 파일과 서버 옵션, 접속 주소 출력, 연결 서브넷 검사, 선택적 방화벽 설정 및 다른 기기 실행 안내 추가 | 자동 테스트 15개, 로컬·LAN 브라우저 각 11개 통과. 독립된 다른 기기 연결·공용 Wi-Fi 통과는 미검증 |
| 2026-09-28 | README를 실행·사용·수집·설정·DB·구현·API·테스트·문제 해결 안내로 확장. 지속 업데이트 지침 추가 | 경로·예제와 현재 코드 대조. 문서 정리로 외부 모델 검증이 추가된 것은 아님 |
| 2026-09-28 | SQLite DB, 문서 수집·검색, 선택적 모델 생성, 계산 Tool, 주요 UI 연결 구현 | 백엔드 10개·브라우저 11개 통과. 실제 모델·운항 데이터·품질 평가는 남음 |
| 2026-09-21 | 원본 데모의 화면·자산을 로컬 복제하고 실행 도구 구성 | 이후 백엔드 연결을 위해 화면 코드 수정 |

초기 화면 원본: [해,답 데모](https://haedap-maritime-demo.gptjipiti1014.chatgpt.site). 공식 안내 요약의 출처와 세부 구현 범위는 [백엔드 상세 문서](docs/BACKEND.md)에 정리돼 있습니다.
