# 벡터·하이브리드 검색 계약

- 상태: 구현됨
- 작성: Codex · 2026-10-27
- 관련: [계획](../plans/2026-10-27-vector-hybrid.md), [ADR 0016](../adr/0016-local-vector-retrieval.md)

## 1. 목적과 범위

기존 검색/답변의 evidence 필드와 Top-5 계약을 유지한다. 원문·권한은 PostgreSQL 기준이다.
임베딩 모델·Chroma·RRF는 독립 모듈이며 기본 bm25 경로는 무거운 의존성을 초기화하지 않는다.

## 2. 설정과 입력

`HAEDAP_RETRIEVAL_MODE=bm25|vector|hybrid` 기본 bm25. `HAEDAP_RAG_CANDIDATES=30`,
`HAEDAP_RRF_K=60`. 모델은 multilingual-e5-small의 고정 SHA revision을 사용한다.
`HAEDAP_EMBED_MODEL_DIR`은 명시적 prepare 명령으로 검증한 로컬 디렉터리다.
`HAEDAP_CHROMA_HOST/PORT`가 있으면 서버, 없으면 `HAEDAP_CHROMA_PATH`의 단일 프로세스 저장소다.
검색 시 다운로드·색인 생성·PostgreSQL 쓰기는 수행하지 않는다.

## 3. 벡터 계약

- passage 입력은 title/reference/heading/text의 자연어를 라벨·줄바꿈으로 결합하고 `passage: `를 붙인다.
  query 원문에는 `query: `를 붙인다. Kiwi 토큰·별칭 확장은 벡터 입력에 적용하지 않는다.
- E5 512토큰 한도를 특수 토큰까지 확인한다. 긴 passage는 문자 손실 없이 구간 분할해 각 구간을
  정규화 임베딩한 뒤 평균·재정규화한다. 긴 query는 명시적 실패/fallback으로 처리한다.
- 모델 ID·고정 revision·384차원·입력/분할 버전·실행 라이브러리 버전의 fingerprint를 collection에 기록한다.
- record ID는 청크 ID+현재 내용 해시+fingerprint로 결정한다. 같은 내용 재실행은 건너뛰고 변경 내용은 새 record다.
  제목·참조·heading·본문·문서/청크 ID·페이지를 해시/메타데이터에 포함한다. 점수는 cosine 유사도다.
- API 검색 전에 현재 허용 후보 전부의 정확한 record ID 존재/metadata를 검사한다. 하나라도 빠지면
  부분 corpus를 정상 벡터 결과로 사용하지 않는다. Chroma query에 허용 record ID를 직접 전달한다.
- 최종 결과는 DB 재조회로 활성·상태·권한·종류·선택 범위 및 내용 동일성을 재확인한다.
  동시에 변경되어 탈락한 결과는 제거하되 부족한 개수는 임의 결과로 채우지 않는다.

## 4. 결합과 실패

RRF = 각 목록의 1/(k+rank) 합. rank는 1부터, 같은 목록의 중복 청크는 첫 등장만 센다.
동점은 첫 등장 순서(BM25 목록 우선)로 결정한다. 원점수는 직접 합산하지 않는다.
후보 수는 최종 k 이상으로 보장한다. 빈 후보/질문은 빈 결과다.
준비 안 된 모델·색인 누락·불일치·Chroma 장애·잘못된 설정은 전체 BM25 fallback한다.
경고 로그는 requested/effective mode와 안전한 reason 코드만 담고 질문·본문·환경값은 출력하지 않는다.
HTTP 응답 형식은 유지하고 개발자 CLI는 effective mode와 fallback 사유를 명시한다.
health.retrieval은 설정된 모드를 나타내며 색인 준비 상태/해당 요청의 성공 보장은 아니다.

## 5. CLI·동기화

`scripts/rag_index.py prepare`만 네트워크 다운로드를 허용한다. `index` 기본 dry-run,
`--apply`, `--limit`, `--batch-size`, `--document-id`, `--document-title`, `--username`, `--kind` 지원.
후보는 기존 DebugStore READ ONLY 스냅샷에서 가져오며 관리자 역할은 기존 활성 계정을 확인한다.
등록·개정 후 명시적으로 index를 다시 실행한다. 삭제·권한 변경은 DB 필터가 즉시 반영한다.
오래된 record는 자동 삭제하지 않는다(별도 재구축으로 정리). 색인 중 실패하면 완료 배치는 남고 재실행한다.
`scripts/debug_retrieval.py`는 같은 허용 corpus로 BM25/vector/hybrid를 비교한다.
rank·ID·문서명·페이지·heading·각 점수와 fallback을 출력하되 본문 preview는 기본 생략한다.

## 6. 수용 기준

- [x] 단위·Chroma 저장/복원·RRF·권한/상태/개정/선택 필터·실패 회귀.
- [x] 실제 로컬 임베딩과 소량 실제 문서 검색 검증(모의 테스트와 구분).
- [x] backend 전체·격리 Docker E2E 및 실행 안내.

## 7. 한계

벡터 top-k는 관련성이 낮아도 결과를 낼 수 있으며 점수는 신뢰도가 아니다.
긴 구간 평균은 세부 의미가 약해질 수 있다. 전 후보 metadata 검사 비용·첫 모델 로딩 비용이 남는다.
평가용 작은 corpus의 성공을 전체 문서 정확도로 일반화하지 않는다.
