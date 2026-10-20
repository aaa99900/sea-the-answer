# OpenAI 호환 Chat Completions 전환

- 상태: 진행 중
- 구현·제출: 2026-10-14 검토 의견을 반영한 기능 PR #13과 별도 CI PR #14 제출 완료. 실제 동국 AI Chat·Ollama 연결 확인은 정보·환경 확보 후 후속 검증으로 남음.
- 작성: 정호영 · Codex 지원 · 2026-10-13
- 담당: 정호영
- 목표 일자: 2026-10-14 (팀장 지시의 “내일까지”, 2026-10-13 기준)
- 관련: [PR #8](https://github.com/dudco/sea-the-answer/pull/8), [LLM 공급자 명세 초안](../specs/llm-provider.md), [팀 모듈 연결 로드맵](2026-10-08-team-module-integration.md)

## 후속 작업 우선순위 — 2026-10-15 사용자 지정

2026-10-15~10-21 주간 계획과 이후 작업을 위한 기록이다. 기존 구현·검증 실적은 [변경 이력](../changelog.md)을 참고한다.

- [ ] **인증 우선**: 일반 선원 로그인과 관리자 로그인 기능을 정비한다. 현재의 로그인 없는 일반 조회·관리자 전용 변경 정책과 구분하며, 새 로그인 방식·역할별 권한 계약은 구현 전에 정리한다.
- [ ] 로컬 Ollama 실제 연동을 검증하고 운영 문서를 보완한다. 모의 호출 검증과 실제 모델의 답변 생성·유효 인용 확인을 구분한다.
- [ ] **CI 병합은 후순위**: 제출한 [CI PR #14](https://github.com/dudco/sea-the-answer/pull/14)는 나중에 병합한다. 앞선 보고 초안의 차주 병합 추진보다 인증 작업을 우선한다.

주간 보고에서 제시한 나머지 문제도 후속 과제로 보존한다. 아래는 사용자 보고 내용이며 이번 기록 작업에서 재검증하지 않았다.

- 검색 순위: 조사가 붙은 단어(예: “조종불능선이”), 흔한 단어와 핵심 단어의 동일 비중, 한영 혼합 질의 때문에 근거 순위가 부정확해지는 문제.
- 문서 목록·정보 질문: “어떤 문서가 등록되어 있어?”처럼 본문 검색으로 답하기 어려운 질문 처리 부족.
- 접근 정책: 기본 관리자 계정 의존과 일반 선원 인증 정비 필요. 해사 데이터 API의 사용자·역할별 접근 범위는 추가로 정해야 한다. 기존 서버 전용 Bearer 토큰 검사가 없는 것으로 해석하지 않는다.
- 탄소집약도는 참고값만 제공하며 공식 CII·등급 산정은 후속 범위다.

## 1. 배경과 목표

팀장 지시: #8에서 API 서버를 `backend/api/`로 옮겼으므로, OpenAI 전용 호출을 OpenAI 호환 Chat Completions 호출로 바꾸어 동국 AI Chat과 로컬 Ollama를 연결한다. LLM은 대규모 언어 모델을 뜻한다.

사전 준비 후 사용자의 구현·PR 작성 지시로 작업을 재개했다. #8은 2026-10-13 22:07(KST)에 머지됐고, 머지 커밋 `196ad73`을 pull한 뒤 `feature/openai-compatible-chat`에서 구현했다. 동국 AI Chat·Ollama의 실제 접속 검증은 환경 정보가 없어 후속 항목으로 남긴다.

아래 표는 **최초 준비 시점의 조사 기록**이다. 최종 #8 head는 `25453eb`, 머지본은 `196ad73`이며 `backend/tools/`·최상위 `scripts/` 분리까지 반영되어 있다.

| 확인 대상 | 2026-10-13 확인 결과 |
|---|---|
| 로컬 `main` | `13cedbd18910abdd81abf7303b897bc9ecc3e71a` |
| #8 | Open, `merged=false`, base는 위 `main`, head는 `f0610d0ff499362a9888e8b892569199d2792b26` |
| 현재 모델 호출 | `backend/pyapi/workspace_store.py`의 `grounded_statements()` → 고정 주소 `https://api.openai.com/v1/responses` |
| #8의 모델 호출 | `backend/api/store/answers.py`로 이동했지만 같은 Responses 호출·응답 파싱 유지 |
| #8의 설정 판정 | `backend/api/config.py:llm_configured()`와 `AnswerStore.answer()`가 각각 키·모델을 확인; 둘을 함께 고쳐야 함 |
| #8의 Docker 전달 | `compose.yaml`의 `x-backend-env`가 키·모델만 전달; 새로운 설정도 명시적으로 전달해야 함 |
| #8의 테스트 | 기본 e2e는 외부 모델을 끄고 실행하므로, e2e 통과만으로 LLM 연결 성공을 주장할 수 없음 |
| 동국 AI Chat 웹 접속 링크 | 사용자가 `https://aichat.dongguk.edu/dashboard/chat` 제공. API 기본 주소는 미확정이며 [명세의 확인 기록](../specs/llm-provider.md#접속-위치별-기본-url) 참고 |

머지 직전에 #8이 바뀌면 위 head를 최신으로 다시 대조한다. GitHub의 임시 `merge_commit_sha`만 보고 머지 완료로 판단하지 않는다.

## 2. 범위

- 포함: Chat Completions 공통 호출, 기본 URL·모델·인증 설정, `/api/health`의 `llmConfigured` 판정 통일, 인용 검증·발췌 전환, Docker 설정 전달, 단위 테스트·실접속 확인·문서 갱신.
- 제외: 검색·임베딩 교체, Tool Calling 도입, 공식 CII 산정, 프런트 UI 개편, DB 스키마 변경. 이 전환만으로 새 dbmate 마이그레이션이 필요하지는 않다.
- 공통 HTTP 클라이언트는 기존 `httpx`를 사용한다. 별도 공급자 SDK 설치를 전제로 하지 않는다.
- 요청·응답·설정의 원본은 [구현된 공급자 계약](../specs/llm-provider.md)이다. 이 계획에는 일정·작업 순서·검증 절차만 둔다.
- 2026-10-14 검토 범위: CI 워크플로는 별도 PR로 분리하고, 공통 설정을 `LLM_API_BASE_URL`·`LLM_RESPONSE_FORMAT`으로 바꾸며 공급자별 인증키를 URL 호스트에 따라 격리한다. 모델 이름 `OPENAI_MODEL`과 OpenAI 키 `OPENAI_API_KEY`는 유지한다.

## 3. 단계

### 2026-10-14 검토 반영 — PR #11 후속 제출

- [x] 팀장 검토 의견과 최신 `main`의 RAG 전처리 변경을 확인하고 기존 기능을 보존하는 범위를 정함.
- [x] LLM 공급자 명세에 공통 설정 이름과 URL 호스트별 키 선택 계약을 확정하고 ADR 0013을 작성.
- [x] `config.py`·`.env.example`·Compose·테스트의 설정 이름 및 공급자별 키를 함께 갱신.
- [x] CI 워크플로를 기능 변경에서 제거하고 별도 CI PR #14로 분리. 기능 문서의 현재 CI 연결 안내도 제거.
- [x] README·구조·사용 안내·색인과 기존 ADR 상태를 새 계약에 맞춰 갱신.
- [x] 모의 HTTP·API 94개, 로컬 전체 백엔드 189개 통과·60개 건너뜀 확인. 별도 원격 검증에서 PostgreSQL 포함 245개 통과·4개 건너뜀, 프런트 빌드·Compose·Docker e2e와 정리 성공. #11의 과거 검증과 구분.
- [x] [후속 기능 PR #13](https://github.com/dudco/sea-the-answer/pull/13)과 [별도 CI PR #14](https://github.com/dudco/sea-the-answer/pull/14)를 제출하고 실제 PR 번호·검증 한계를 기록.
- 완료 조건: OpenAI·동국 키가 서로 다른 호스트에 전송되지 않고 로컬 Ollama·기타 호환 서버에는 두 키 모두 전송하지 않으며, 기능 PR의 diff에 CI 워크플로가 없다.

### 1단계 — 사전 조사와 구현 명세 준비

- [x] #8의 상태·base·head와 새 코드 경로 확인.
- [x] 호출부·설정 판정·Compose·테스트 변경 지점 대조.
- [x] OpenAI·Ollama 공식 문서에서 Chat Completions 형식 확인.
- [x] 공급자 설정·실패 처리·테스트 기준을 명세 초안에 작성.
- [x] 사용자가 제공한 동국 AI Chat 웹 링크 기록. 웹 도구 접근·공개 검색에서 공식 API 안내를 확보하지 못한 한계와 후속 확인 방법을 명세에 반영.
- [ ] 동국 AI Chat의 API 기본 주소, 모델 ID, 인증 방식, 지원 옵션 확인. 실제 키는 Git·문서·채팅에 기록하지 않는다.
- 완료 조건: 동국 환경 정보가 없어도 공통 구현과 모의 테스트를 진행할 수 있도록 확정 요구와 미확정 값을 구분한다. 위 사전 문서 준비는 완료했다.

### 2단계 — #8 머지 확인과 최신 코드 확보

- [x] GitHub에서 #8의 `merged=true`, 머지 커밋과 최신 head 확인.
- [x] 준비 문서를 Git stash `c1c56bd`로 보존한 뒤 pull. 새 계획·명세를 복원하고 머지된 문서 본문과 수동 통합.
- [x] `git pull --ff-only origin main`으로 `196ad73` 확보.
- [x] 작업 브랜치 생성 후 최신 루트 `AGENTS.md`·README·문서를 다시 읽음.
- [x] #8과 겹치는 README·문서 색인·변경 이력은 새 구조를 보존하면서 준비 문서를 함께 반영.
- [x] 실행 도구 확인. 기존 PATH에 도구가 없어 `.verification/`에 uv·Python 3.13·Node 24를 준비하고 backend·frontend 의존성 설치. 시스템 설정·개인 `.env`는 보존. Docker는 없어 로컬 e2e 불가.
- 완료 조건: `backend/api/`, `compose.yaml`, `migrations/`, `e2e/`가 실제 로컬에 있고 작업 브랜치가 머지된 최신 `main`을 기반으로 한다.

아래 명령은 **#8 머지 후**, 준비 문서를 보존하고 작업 트리가 정리된 상태에서 저장소 최상위 PowerShell에서 실행한다.

```powershell
git status --short
git pull --ff-only origin main
git switch -c feature/openai-compatible-chat
docker version
docker compose version
```

기대 결과: 브랜치가 생성되고 Docker 클라이언트·서버와 Compose 버전이 표시된다. 명령을 찾지 못하면 도구 설치와 PATH를 먼저 확인한다. Docker 서버 연결 오류이면 Docker Desktop을 시작한다. 기존 `.env`와 DB는 그대로 보존한다.

### 3단계 — 최초 PR #11의 공통 호출과 설정 구현

- [x] 명세의 설정 이름·기본값·공급자별 필수 값을 구현 전에 확정하고 명세 상태 갱신.
- [x] `config.py`의 같은 설정 해석을 health와 답변 호출에서 사용.
- [x] `answers.py`의 Responses 전용 요청·파싱을 `backend/api/llm.py`의 Chat Completions로 교체.
- [x] 최초 #11에서 키 없는 로컬 Ollama를 허용. 2026-10-14 검토에서 Bearer 헤더는 URL 호스트에 맞는 공급자 키만 보내는 계약으로 변경.
- [x] 기본 요청은 공통 필드만 사용하며 JSON·인용 검증은 항상 적용.
- [x] `.env.example`·Compose에 새 설정 연결. 기본 e2e에는 실제 모델 설정 미전달.
- [x] `/api/ask` 응답·경고 코드 유지; 검색 권한·운항/CII 코드 변경 없음.
- 완료 조건: 모델 주소 변경만으로 요청 대상이 바뀌며, 응답이 잘못되어도 모델 오류 때문에 `/api/ask`가 500으로 끝나지 않고 발췌로 전환한다.

### 4단계 — 최초 PR #11의 단위·통합·브라우저 검증

- [x] `backend/tests/test_llm_provider.py` 추가: `httpx.MockTransport`로 70개 검증. 실제 외부 요청과 DB 없이 실행.
- [x] 실제 답변 오케스트레이션 + MemoryWorkspace로 `/api/health`·`/api/ask` 설정 판정·실패 전환 확인.
- [x] 백엔드 전체 147 통과·실 DB 58 건너뜀, 프런트 4 통과·빌드 성공. 로컬 uv가 만든 Python 환경으로 pytest 실행.
- [x] Linux CI에서 운영·개발·e2e Compose 구문 확인. `config -q` 사용.
- [x] Linux CI에서 별도 프로젝트 이름으로 Docker e2e 실행. 14단계 업무 흐름 1개 테스트 통과, 종료 코드 0과 정리 확인.
- [ ] 외부 호출은 별도로 동국 AI Chat·로컬 Ollama에서 실제 모델 답변의 `generation=llm`과 유효 인용을 확인. 200 응답만으로 성공 처리하지 않는다.
- 완료 조건: 모의 테스트와 실제 공급자 검증을 분리 기록하며, 미확보 환경·키 때문에 못 한 검증은 미검증으로 남긴다.

아래는 일반 환경의 재현 명령이다. 최초 #11에서는 별도 준비한 Python·Node로 단위 테스트·빌드를 실행하고 Linux CI로 Compose·e2e를 검증했다. 이는 2026-10-13 이전 변경의 검증 기록이며 현재 기능 변경의 통과를 뜻하지 않는다. 2026-10-14 검토에서 CI 워크플로를 별도 PR로 분리한다. 현재 수행 결과는 [변경 이력](../changelog.md)에 구분해 기록한다.

```powershell
# backend/에서
uv sync --locked
uv run pytest
```

```powershell
# frontend/에서
npm ci
npm test
npm run build
```

```powershell
# 저장소 최상위에서
docker compose config -q
docker compose -f compose.yaml -f compose.dev.yaml config -q
docker compose -p haedap-llm-check --profile e2e config -q
docker compose -p haedap-llm-check --profile e2e up --build --force-recreate --exit-code-from e2e e2e
# 종료 코드를 먼저 확인·기록한다. 0이면 성공이다.
$LASTEXITCODE
docker compose -p haedap-llm-check --profile e2e down
```

`-p haedap-llm-check`는 테스트를 별도 Compose 프로젝트로 실행해 기존 `haedap` 앱을 종료하지 않기 위한 이름이다. e2e DB는 임시 메모리 파일시스템을 사용하며 앱 DB와 분리된다. `--force-recreate`는 실행마다 빈 테스트 DB를 보장한다. `--attach-dependencies`는 일회성 마이그레이션 종료 때문에 테스트 전에 멈출 수 있으므로 쓰지 않는다. `down -v`로 기존 앱 데이터·백업을 지우는 절차는 이 작업에 필요하지 않다.

### 5단계 — 문서와 결과 정리

- [x] README에 실제 사용 가능한 설정 예시·명령 반영.
- [x] architecture·user-guide·integrated-answer의 모델 호출 설명·테스트 경로 갱신.
- [x] 명세·계획·ADR 0012 색인과 변경 이력 갱신. 실제 모델 검증은 미검증 표시.
- [x] 작업 diff 검토 후 [PR #11](https://github.com/dudco/sea-the-answer/pull/11) 초안 제출. 원본 직접 푸시 권한이 없어 `cxo-ca/sea-the-answer` fork 사용. 팀원 메시지·댓글·PR 머지는 수행하지 않음.
- 완료 조건: 실제 구현, 모의 검증, 공급자 실검증, 남은 한계가 구분된 결과를 제공한다.

## 4. 영향 받는 파일·문서

아래 소스 경로는 **#8 머지 후 기준**이다. 현재 로컬의 `backend/pyapi/`에 새 구현을 넣지 않는다.

| 경로 | 예정 변경 |
|---|---|
| `backend/api/config.py` | 공통 설정 해석·모델 사용 가능 판정 |
| `backend/api/store/answers.py`, 필요 시 `backend/api/llm.py` | Chat Completions 통신·출력 파싱·인용 검증·발췌 전환 |
| `backend/api/routes/system.py` | 공통 설정에 따른 health 상태 유지 확인 |
| `.env.example`, `compose.yaml` | 공급자 기본 URL·선택 옵션 전달, e2e 격리 유지 |
| `backend/tests/test_llm_provider.py`, `backend/tests/test_fastapi_api.py` | 통신·인용·설정·실패 회귀 테스트 |
| README·architecture·user-guide·integrated-answer·changelog | 실제 설정·구조·검증 기록 갱신 |

## 5. 위험과 대응

| 위험 | 대응 |
|---|---|
| Docker의 `localhost`를 PC의 Ollama로 착각 | [명세의 접속 위치별 설정](../specs/llm-provider.md#접속-위치별-기본-url) 사용; 호스트 바인딩·방화벽도 확인 |
| 공급자별 JSON 스키마·토큰 옵션 차이 | 기본은 공통 필드만 전송하고 검증은 앱에서 수행; 지원 옵션은 명시적으로 선택 |
| 로컬 모델 최초 적재가 25초를 초과 | 모델을 먼저 적재해 검증하고, 타임아웃 변경이 필요하면 Next.js의 60초 프록시 한도도 함께 검토 |
| 발췌 대체 결과를 모델 성공으로 오인 | `generation`, `warnings`, 인용을 함께 확인 |
| 문서와 현재 코드의 차이 | #8의 최신 README·architecture 보존. integrated-answer의 제거된 Node 테스트 경로를 정리하고 이번에 수행하지 않은 권한·기준 비교 전용 회귀는 미검증으로 표시 |

## 6. 열린 질문

- 동국 AI Chat의 웹 링크는 확보했다. 공식 API 안내, API 기본 주소(웹 채팅 화면 주소와 구분), 정확한 모델 ID, Bearer 인증 여부, JSON 출력 옵션 지원 여부는 추가 확인이 필요하다.
- 사용할 Ollama 모델과 다운로드·기동 상태, 직접 실행인지 Docker→호스트인지, 실제 하드웨어에서 응답 시간.
- 로컬 Docker는 없지만 현재 변경의 Compose·e2e는 별도 fork 검증 브랜치에서 통과했다. 실제 동국·Ollama 연결은 여전히 후속 검증이 필요하다. CI 워크플로는 기능 변경과 별도 PR #14로 제출했다.

## 7. 진행 기록

- 2026-10-13: #8의 미머지 상태와 고정 head를 확인하고 호출부·Compose·테스트를 읽음. 구현 순서·명세 초안·설정 제안·테스트 항목과 명령 준비. 실행 코드·개인 `.env`·DB는 수정하지 않음. 단위·e2e·실제 모델 호출은 수행하지 않음.
- 2026-10-13: 변경 문서 8개의 로컬 링크 85개·JSON 예제 2개와 `git diff --check` 확인. 모의 테스트 코드를 실행한 검증이 아니라 준비 문서의 경로·예제 대조다.
- 2026-10-13: 사용자가 동국 AI Chat 대시보드 링크를 제공. 페이지 본문·공식 API 안내를 확보하지 못해 웹 접속 주소와 모델 API 주소를 구분해 기록하고 미확정 항목·후속 확인 절차 갱신. 외부 모델 요청은 실행하지 않음.
- 2026-10-13: #8 머지 확인·pull·작업 브랜치 생성. Chat Completions 공통 통신·설정 판정·인용 검증·Compose 전달 구현. 모의 70개와 전체 백엔드·프런트 검증 완료. 로컬 Docker 부재를 보완하는 PR 검증 워크플로 추가.
- 2026-10-13: fork 브랜치를 푸시하고 PR #11 초안 생성. 원본 PR에서 Actions 실행이 관찰되지 않아 push 트리거도 추가해 본인 fork에서 동일 CI 검증 진행.
- 2026-10-13: [Linux CI](https://github.com/cxo-ca/sea-the-answer/actions/runs/38408707402) 성공: 백엔드 201 통과·실 데이터셋 4 건너뜀, 프런트 테스트·빌드, Compose 구성 3종, Docker e2e 14단계 흐름 1개 테스트·정리 통과. PR #11은 충돌 없이 병합 가능. 실제 공급자 호출 성공은 주장하지 않음.
- 2026-10-14: 팀장 검토 의견에 따라 CI를 분리하고 공통 URL·출력 설정을 `LLM_*`로 변경, URL 호스트별 OpenAI·동국 키 선택과 로컬 무인증을 구현. 최신 `main`의 RAG 전처리와 문서 충돌을 양쪽 내용 보존으로 해결. 모의 HTTP·API 94개·전체 backend 189개 통과(60개 건너뜀). Docker와 실제 동국·Ollama 호출은 미검증.
- 2026-10-14: 최신 main `76620c7`에 기능 변경만 한 커밋으로 정리한 PR #13과 CI 전용 PR #14 제출. 기능과 워크플로를 결합한 별도 검증 브랜치에서 PostgreSQL·Docker e2e 확인을 시작했다. 원본 PR과 DB·개인 `.env`는 보존했다.
- 2026-10-14: [기능 검증](https://github.com/cxo-ca/sea-the-answer/actions/runs/38518450553)에서 백엔드 245개 통과·4개 건너뜀, 프런트 4개·빌드, Compose 3종, Docker e2e 1개·정리 성공. [CI 전용 검증](https://github.com/cxo-ca/sea-the-answer/actions/runs/38518455486)도 성공. 실제 외부 모델 검증은 포함하지 않는다.
