# 한국어 근거 답변 개선과 실제 모델 검증

- 상태: 완료 (구현·실행 환경 검증 완료, 일반 한국어 품질 한계는 후속)
- 작성: Codex · 2026-10-28
- 담당: 정호영
- 목표 일자: 실행 환경에서 가능한 검증을 완료하고 외부 제약을 구분해 기록
- 관련: [LLM 공급자 계약](../specs/llm-provider.md), [인증 후속 기록](2026-10-21-crew-admin-auth.md), [PR #18](https://github.com/dudco/sea-the-answer/pull/18), [CI PR #14](https://github.com/dudco/sea-the-answer/pull/14)

## 1. 배경과 목표

PR #18은 2026-10-22 병합됐다. 기존 Ollama 3B 실검증에서는 영문 생성·인용은 성공했으나 한국어 요청은 근거 부족 응답이었다. 한국어 설명과 원문 인용을 분리해 지시하고, 고정 근거 평가로 변경 전후의 실제 모델 결과를 비교한다. 통합된 인증·문서 열람 경계를 회귀 검증하며 Docker에서 호스트 모델로 연결되는 경로도 확인한다.

## 2. 범위

- 포함: 기본 문서 기반 한국어 평가 세트·오프라인 실행 도구, 프롬프트 개선, 실제 로컬 모델 호출, 인용·권한·실패 전환 회귀, 환경별 연결 확인과 재현 문서.
- 제외: 검색·청킹 알고리즘 교체, DB 스키마 변경, 새 모델 다운로드, 기존 앱 데이터·개인 설정 변경, 자동 의미 정답 판정, 외부 유료 모델 호출, 관리자 권한이 필요한 PR 병합.

## 3. 단계

### 1단계 — 평가 계약과 환경 확인

- [x] 병합된 코드와 기존 검증·보안 계약 확인.
- [x] 고정 근거 평가 도구·사례와 출력 계약 확정.
- [x] Ollama·Docker·PostgreSQL·브라우저 실행 환경 확인.
- 완료 조건: 평가가 검색 품질·의미 정답률·실제 모델 호출을 혼동하지 않고 재현 가능하다.

### 2단계 — 한국어 생성과 평가

- [x] 한국어 대표 질문 10~20개와 정답 근거·사람 검토 항목 준비.
- [x] 기존 프롬프트 실제 모델 기준 결과 기록.
- [x] 한국어 답변·원문 인용 분리 지시 보완과 실제 모델 비교. 일반 품질 합격은 미충족으로 기록.
- [x] 모의 HTTP로 형식·원문 인용·실패 전환·문서 권한 회귀 검증.
- 완료 조건: 실제 결과와 한계를 보존하고 JSON·인용 검증을 약화하지 않는다.

### 3단계 — 통합·실행 환경 검증

- [x] backend 전체 테스트와 실제 PostgreSQL 인증·문서 권한 검증.
- [x] 브라우저에서 실제 모델 답변·원문·실패 전환 확인.
- [x] Docker e2e에서 발견한 로그인 직후 보고서 생성의 자료 로딩 경합 수정·회귀 검증.
- [x] 격리된 Docker e2e 및 Docker → 호스트 Ollama 실제 호출 확인. 초기 실패와 재검증 성공을 구분해 기록.
- [x] 운영 안내·변경 이력·관련 계획과 색인 갱신.
- 완료 조건: 모의·호스트 직접 실행·브라우저·컨테이너 검증 결과를 각각 구분한다.

### 4단계 — 사용자 요청에 따른 로컬 Docker 설치

- [x] 공식 설치 파일 다운로드·Docker Inc 디지털 서명 확인.
- [x] WSL2 전제 기능·Docker Desktop 설치. 공식 서명·종료 코드·실행 파일과 CLI 확인.
- [x] 사용자 승인에 따라 Windows를 재부팅한 뒤 Docker 엔진 실행 확인.
- [x] Docker Compose 격리 e2e와 컨테이너 → 호스트 Ollama 실제 호출.
- 완료 조건: 실제 엔진·Compose 실행을 확인하거나, 설치 프로그램/OS가 요구하는 다음 조치를 구체적으로 기록한다.

## 4. 영향 받는 파일·문서

| 경로 | 변경 |
|---|---|
| `backend/api/llm.py`, `backend/tests/` | 한국어 프롬프트와 모델·권한 회귀 |
| `frontend/src/views/report-view.jsx`, `e2e/tests/ui-refinements.spec.js` | 초기 자료 로딩 중 보고서 생성 차단·지연 응답 회귀 |
| `scripts/` | 고정 근거 평가 도구·평가 사례 |
| `README.md`, `docs/specs/llm-provider.md`, `docs/user-guide.md` | 실행·평가 계약과 제한 |
| `docs/changelog.md`, 계획·색인 | 실제 결과·남은 제약 |

## 5. 위험과 대응

| 위험 | 대응 |
|---|---|
| 유효 인용을 의미적 정답으로 오인 | 구조 지표와 사람 검토를 분리 |
| 검색 실패와 모델 실패 혼동 | 고정 근거 평가와 실제 API 검색을 분리 |
| 기존 앱 데이터·설정 영향 | 별도 테스트 DB·출력 경로·프로세스 환경 사용 |
| 모델 오류에 비밀값 포함 | 원본 오류·키를 평가 결과에 기록하지 않음 |

## 6. 열린 질문

- 후속: 일반 한국어 업무 품질의 수용 기준·모델 선정·의미적 정답 검토. 이번 구현·연결 검증 완료가 일반 품질 합격을 뜻하지 않는다.
- CI PR #14는 별도 변경으로 유지하며 관리자 병합 권한 제약을 기록한다.

## 7. 진행 기록

- 2026-10-28: 사용자 진행 지시에 따라 시작. 작업 트리는 깨끗하며 현재 커밋은 #18 병합본 `91a1cc6`이다. 평가 도구·환경 확인·모델 보안 검토를 병렬 진행한다.
- 2026-10-28: 평가 CLI·기본 문서 16문항·인용/권한 회귀 구현. 실제 PostgreSQL 전체 504 통과·4 건너뜀, 최종 집중 138 통과. 샌드박스 임시 폴더 오류는 승인 환경 재실행으로 구분했다. Docker 명령은 미설치로 실패했다.
- 2026-10-28: 실제 16문항 원측정은 테스트 동시 실행의 CPU 경합 가능성을 발견해 성능 비교로 사용하지 않는다. 부하를 제거한 동일 6문항 순차 비교와 한국어 우선 지시 실험을 진행한다. 원문 인용이 일치해도 조건을 잘못 설명하는 의미 오류를 관측했다.
- 2026-10-28: 실제 Chrome → Next standalone → FastAPI → PostgreSQL → Ollama에서 가상 한국어 단문 답변·원문 모달·권한 제외·근거 부족 검증과, 없는 모델의 원문 발췌 전환을 각각 통과했다. 일반 한국어 품질 합격과는 구분한다. 사용자가 다른 서버 대신 이 PC에 Docker를 직접 설치·실행하도록 지시해 4단계를 추가했다.
- 2026-10-28: Docker Desktop 4.97.0 사용자 설치 종료 코드 0, Docker CLI 29.9.2·Compose 5.6.1·Desktop CLI 4.97.0·WSL 3.0.3.0을 확인했다. WSL/VMP 활성화는 재부팅 대기다. 실제 시작은 45초 대기 후 실패했고 backend는 `Virtual Machine Platform not enabled`로 엔진을 중지했다. `wsl --status`도 `WSL_E_WSL_OPTIONAL_COMPONENT_REQUIRED`다. 설치 성공과 엔진 실행 성공을 구분하며 재부팅 전 컨테이너 검증을 완료로 표시하지 않는다. 검증 PostgreSQL과 임시 모델 프리셋은 정리했다.

- 2026-10-29: [PR #20](https://github.com/dudco/sea-the-answer/pull/20)에 최신 main `7c0ba46`(검색 토큰 재사용·해사 검색 평가)을 반영했다. 문서 3곳의 양쪽 기록을 보존하고 backend/scripts 전체 533 통과·4 건너뜀, Docker production 빌드·e2e 8 통과 및 테스트 스택 정리를 확인했다. 상세 범위와 경고는 [변경 이력](../changelog.md)에 기록했다.

### Docker 검증 재현 순서

2026-10-29 재부팅 완료를 확인했다. WSL 상태는 기본 버전 2로 정상이며 Docker Server 29.9.2(Linux/amd64)의 실제 응답과 Compose 구성 검사를 통과했다. 첫 가상 디스크/VM 초기화에 약 2분이 걸려 처음 45초 기동 확인은 시간 초과였고 이후 정상 기동했다. `haedap-korean-e2e-20261029` 프로젝트에서 실제 e2e 빌드·실행을 완료했다.

첫 실행은 UI 모의 6건 통과·실제 workspace 1건 실패였다. 선원 재로그인 직후 선박 조회 완료 전에 Noon 버튼을 눌러 선박 미선택 알림으로 중단됐으며 보고서 생성 POST는 없었다. 연결·자료 로딩 중 생성 버튼을 잠그는 수정과 지연 응답 회귀를 추가하고 새 테스트 DB에서 재실행했다. 첫 실행 스택은 `down` 종료 코드 0으로 정리했다. 설치가 끝난 임시 Docker 설치 파일과 이 작업의 standalone 복사본만 삭제해 공간을 확보했으며 원본·모델·검증 기록은 보존했다.

수정 후 frontend `npm test` 20건과 Docker production 빌드를 통과했다. 새 DB의 Docker e2e는 **8건 통과(1.7분)**이며, 실제 DB 업무 흐름 1건과 모의 API UI/지연 응답 회귀 7건이다. Compose 실행·정리는 모두 종료 코드 0이었다. 이어 같은 backend 이미지에서 실제 호스트 Ollama를 호출해 한국어 단문·유효 원문 인용을 **19.28초**에 확인했다(별도 모델 적재 12.19초). 컨테이너의 `llm.py` 해시도 현재 소스와 일치했다. 호스트는 `127.0.0.1:11434`, 컨테이너는 `http://host.docker.internal:11434/v1`이었다. e2e는 모델을 끄고 실행했으며 실제 모델 연결 검사는 별도다.

결과는 `.verification/docker-e2e-20261029-9499f1c6/`와 `.verification/container-llm-20261029-f64912e2/`에 있다. Docker Desktop과 호스트 Ollama 검증 서버(PID 10316)는 실행 상태이며 테스트 컨테이너·네트워크는 정리했다. Ollama는 기존 `.verification/ollama-models`를 사용하며 새 모델을 다운로드하지 않았다.

2026-10-28 사용자가 PC 재부팅을 승인했다. 재부팅 전 상태는 `.verification/reboot-20261028.json`에 보존하고, 재접속 후 실제 부팅 완료와 Docker Server 응답을 먼저 확인한다.

새 PowerShell에서 저장소 최상위로 이동한다. Docker 경로가 아직 PATH에 없으면 현재 터미널에서만 추가한다.

```powershell
$env:PATH = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:PATH"
docker desktop start --timeout 60
docker version
docker compose -p haedap-korean-e2e-20261029 --profile e2e config --quiet
docker compose -p haedap-korean-e2e-20261029 --profile e2e up --build --force-recreate --exit-code-from e2e e2e
# 성공·실패와 무관하게 이 테스트 프로젝트만 정리
docker compose -p haedap-korean-e2e-20261029 --profile e2e down
```

엔진의 실제 Server 정보가 반환되는지 먼저 확인한다. `docker info`는 최초 실패 시 HTTP 500을 출력하고도 종료 코드 0이었으므로 종료 코드만으로 성공을 판단하지 않는다. 기존 앱 `.env`·DB·볼륨은 보존한다. 빌드·e2e가 끝난 뒤 Ollama를 기존 모델 폴더로 시작하고, 모델 적재 후 `.verification/container-llm-probe-20261028.py`를 backend 이미지에 읽기 전용 마운트해 `http://host.docker.internal:11434/v1`로 실제 연결했다. probe 컨테이너에 모델 ID·`json_schema`·로컬 호스트용 `NO_PROXY`를 명시했고 공급자 키는 비웠다. 이는 직접 모델 호출 검사이며 인증 API·DB·브라우저 검증으로 확대 해석하지 않는다. Ollama·테스트 로그와 설치 서명·해시·재부팅 기록은 `.verification/`에 보존한다.

`.verification/`의 probe·로그는 이 PC의 로컬 산출물이며 PR에는 포함하지 않는다. 새 checkout에서는 위 e2e 명령으로 backend 이미지를 만든 뒤, [Ollama 실행 안내](../user-guide.md#로컬-ollama-실행)에 따라 호스트 모델을 적재하고 다음 PowerShell 명령으로 같은 가상 단문 호출을 재현할 수 있다. 실행 위치는 저장소 최상위다.

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new()
@'
import json
from api import config, llm
source = "청해쿼츠는 출항 전 장비 점검 절차입니다."
evidence = [{"id": "container-test-1", "title": "가상 연결 검증", "text": source}]
answer = llm.grounded_statements("청해쿼츠는 무엇인가요?", evidence, "ko", config.llm_settings())
print(json.dumps(answer, ensure_ascii=False))
'@ | docker run --rm --no-healthcheck -i `
  -e LLM_API_BASE_URL=http://host.docker.internal:11434/v1 `
  -e OPENAI_MODEL=qwen2.5:3b -e LLM_RESPONSE_FORMAT=json_schema `
  -e OPENAI_API_KEY= -e DONGUK_AI_CHAT_API_KEY= `
  -e NO_PROXY="host.docker.internal,127.0.0.1,localhost" `
  --entrypoint python haedap-korean-e2e-20261029-e2e-backend:latest -
```

예상 결과는 한국어 `text`, 제공한 `chunkId`, 원문에 그대로 포함된 `quote`를 가진 배열이다. 빈 배열이면 모델이 근거 부족으로 판단한 것이며 연결 실패와 구분한다. 설정·접속·형식·인용 오류는 기존 검증에서 예외로 거절한다. 이 최소 호출 성공도 일반 한국어 업무 품질 합격을 뜻하지 않는다.
