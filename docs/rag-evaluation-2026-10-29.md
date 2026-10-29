# 등록 해사 PDF 검색 평가 — 2026-10-29

## 범위와 판정 기준

feature/rag-vector `746053c` 및 현재 실행 backend의 검색 함수를 대상으로 읽기 전용으로 평가했다.
문서 원본·청크·벡터·질의 이력·설정은 변경하지 않았고, 서비스 재시작·재색인·코드 수정·커밋은 하지 않았다.
결과를 기록하는 이 문서와 [질문 JSON](rag-evaluation-questions.json)만 프로젝트 문서로 추가한다.

원본 PDF와 등록 PDF를 메모리 SHA-256으로 비교해 세 파일 모두 일치함을 확인했다.
PDF 전체 텍스트를 로그에 출력하는 명령은 자동 승인 검토에서 거절됐으며, 이후에는
원문을 내부에서만 분석하고 북마크·페이지·키워드 개수·청크 metadata만 출력했다.
원문 문단이나 환경 비밀값을 평가 산출물에 저장하지 않았다.

이 세트는 **검색 근거 위치의 1차 평가 초안**이며 규정 해석·LLM 답변 정답률 평가가 아니다.
PDF 북마크/해당 페이지의 키워드와 DB heading을 기준으로 기대 조항 후보를 먼저 정했다.
한국어 일부 청크는 heading이 잘못돼 페이지 내 본문 키워드로 후보를 지정했다.
후보 청크가 나와도 답변에 필요한 모든 조건·예외가 포함된다는 보장은 없고,
최종 정답 문장과 대체 정답 조항은 담당자의 추가 검토가 필요하다.
특히 Q10은 승인/형식승인 두 하위 조항이므로 후보 하나 적중이 비교 답변의 완전성을 의미하지 않는다.

- 검색 범위: guest에게 허용된 활성 7문서, **5,485청크 전체**. PDF 3개 외 기존 샘플/요약도 포함.
- 한국어 주 질문 10개 × BM25/vector/hybrid를 실제 호출. 문서 필터 BM25 대조 10개, 영어 대조 6개.
- 전체 corpus BM25 상위 100개에서 첫 기대 후보 순위를 측정. 사용자에게 반환하는 Top-5 적중 여부를 별도 집계.
- vector/hybrid는 기존 `rag_search.search`와 현재 Chroma를 사용했다. 원본 조회는 READ ONLY 트랜잭션,
  검색은 가져온 같은 후보 snapshot으로 실행했고 웹 `/ask`·외부 LLM은 호출하지 않았다.
- 물리 페이지는 PDF 첫 장을 1로 센 번호다. 문서에 인쇄된 쪽번호와 다를 수 있다.

## 실제 등록 문서와 색인 상태

| 문서 | PostgreSQL 청크 | 현재 Chroma에 확인된 청크 | 작업 상태 |
|---|---:|---:|---|
| KR 선급 및 강선규칙 2025 제1편 선급등록 및 검사 | 1,376 | 80 | failed, attempts=5 |
| ABS MVR Part 5D, July 2026 | 1,743 | 496 | failed, attempts=5 |
| ABS MVR Part 6, July 2026 | 2,360 | 1,104 | failed, attempts=5 |
| 기존 IMO 요약/가상 샘플 4문서 | 6 | 6 | done |
| 합계 | **5,485** | **1,686** | 부분 색인 |

실행 중 기본 검색 모드는 bm25였다. 미색인 후보가 하나라도 있으면 기존 정책대로 전체 BM25 fallback하므로,
이번 vector/hybrid 각 10회는 모두 `effective_mode=bm25`, `fallback_reason=index_incomplete_or_stale`였다.
이를 벡터/RRF의 성공 결과나 낮은 정확도 점수로 해석하면 안 된다.

## 평가 질문과 BM25 결과

KR1 = 위 KR 제1편, 5D/6 = 위 ABS Part 5D/6. 순위는 **전체 corpus의 첫 기대 조항 후보 순위**다.
페이지에 다른 조항도 있으므로 페이지 적중과 조항 후보 적중을 구분했다.

| ID | 질문 | 기대 근거·물리 페이지 | 전체 BM25 | 해당 문서만 검색 | 영어 대조 |
|---|---|---|---:|---:|---:|
| Q01 | 선급이 자동으로 정지되는 경우는? | KR1 p.21, 901 | 2 | 1 | — |
| Q02 | 정지된 선급은 어떤 조건에서 회복될 수 있어? | KR1 p.21–22, 901 | 1 | 1 | — |
| Q03 | KR 연차검사는 검사기준일 전후 언제까지 받아야 해? | KR1 p.40, 201 검사시기 | 1 | 1 | — |
| Q04 | KR 선체·의장·소방설비 정기검사의 주기와 검사시기는? | KR1 p.55–56, 401 검사시기 | 5 | 5 | — |
| Q05 | Part 5D에서 heavy deck cargo 강화 규정이 적용되는 기준은 뭐야? | 5D p.17–18, 1.3.1 및 3 Strengthening | 2 | 2 | 1 |
| Q06 | Part 5D에서 heavy deck cargo를 운송하려면 어떤 자료를 제출해야 해? | 5D p.17, 1.5.1 | 1 | 1 | 3 |
| Q07 | Part 5D에서 heavy liquid cargo의 설계수두 Design Head는 어떻게 정해? | 5D p.18, 5.1 | 1 | 1 | 1 |
| Q08 | Part 6의 SOx scrubber 설계 검토를 위해 제출해야 하는 도면과 자료는? | 6 p.331, 6-3-2/3 | **79** | **29** | **2** |
| Q09 | Part 6에서 육상전원 shore connection의 비상정지 emergency shutdown 작동 요건은? | 6 p.412, 6-4-2/25 | 1 | 1 | 1 |
| Q10 | Part 6에서 평형수 처리장치 BWMS의 ABS 승인과 형식승인은 어떻게 구분돼? | 6 p.439, 7.7.1/7.7.2 | **53** | **47** | **1** |

영어 대조 문장은 질문 JSON에 있다. 언어·표현이 함께 달라지는 진단용 대조이며,
개별 단어 하나의 효과를 분리하는 통제 실험은 아니다.

- 기대 후보 Hit@1: **5/10**, Hit@5: **8/10**, MRR@5: **0.62**.
- 전체 BM25 검색 함수 소요: **평균 8.110초**, 범위 **7.110–11.705초**.
  첫 질문 11.705초, 이후 9질문은 7.110–8.476초였다.
- 후보 DB 조회는 이번 snapshot에서 **0.202초**. HTTP·LLM·최종 API DB 재확인 시간은 포함하지 않았다.
  같은 개발 PC에서 진단 계산도 수행한 측정이며 전용 부하/성능 벤치마크는 아니다.
- vector/hybrid는 모두 fallback이므로 여기서 ANN/RRF 고유 성능이나 순위를 비교할 수 없다.

## 확인된 문제

### 1. 자동 색인이 실제 문서에서 실패하는 구현 결함

`backend/api/rag_vector.py`의 `reusable_vectors()`는 Chroma에서 NumPy ndarray 벡터를 받지만,
`rag_embeddings.LocalEmbedder.documents()`는 새 벡터를 Python list로 반환한다.
`VectorIndex.index()`에서 재사용·신규 벡터를 합칠 때 자료형을 통일하지 않는다.
첫 벡터가 ndarray이고 뒤에 list가 섞인 경우 Chroma 클라이언트의 `validate_embeddings`가 ValueError를 낸다.

세 PDF의 첫 누락 배치에 대해 실제 로컬 E5 계산 후 `_validate_and_prepare_upsert_request`까지만 실행했다.
HTTP upsert를 보내지 않고도 같은 자료형 오류를 재현했다.

| 문서 | 첫 누락 청크 번호 / 페이지 | 배치의 벡터 자료형 | 로컬 검증 |
|---|---|---|---|
| KR1 | 81 / p.26 | ndarray 4 + list 12 | ValueError |
| Part 5D | 497 / p.110 | ndarray 1 + list 15 | ValueError |
| Part 6 | 1,105 / p.261 | ndarray 1 + list 15 | ValueError |

동일 벡터들을 메모리에서 모두 list로 바꾸면 세 배치 모두 로컬 입력 검증을 통과했다.
이것은 수정 방향 검증이며 실제 저장 성공/전체 복구 검증은 아니다. 제품 코드는 수정하지 않았다.
기존 소량 테스트는 이 혼합 배치를 충분히 다루지 못했다. 정상 소량 검증을 전체 실제 문서 성공으로 일반화하면 안 된다.

### 2. 한영 표현 차이와 질문 의도 구분

- Q08은 한국어 질문에서 기대 조항 79위, 영어 대조에서 2위였다. 전체 검색 1위는 Part 6이 아니라 KR1 p.176이었다.
- Q10은 한국어 53위, 영어 대조 1위였다. 한국어 1위는 관련 장치이지만 승인 절차가 아닌 p.441 Definitions였다.
- Q05의 적용 기준 질문은 1위가 제출자료 조항(1.5.1), 기대 적용 조항은 2위였다.
  장치·화물 단어가 같아도 적용/제출/정의/승인이라는 의도가 다르면 필요한 근거가 다르다.
- 문서 필터만 적용해도 Q08 29위, Q10 47위여서 문제를 완전히 해결하지 못했다.
- 질의 토큰에는 일부 혼합 언어 조각(`르`, `의`)과 설계수두 분해 결과가 남는다.
  전문 용어·일반 업무 표현의 한영 대응, 단복수, 혼합 언어 형태소 처리를 추가 평가해야 한다.

### 3. 저장된 청크 heading 품질

| 문서 | 전체 | 80자 미만 | heading='본문' | 반복 KR 머리말 형태 heading | KR 꼬리말 형태 heading |
|---|---:|---:|---:|---:|---:|
| KR1 | 1,376 | 445 | 21 | 841 | 182 |
| Part 5D | 1,743 | 99 | 259 | 0 | 0 |
| Part 6 | 2,360 | 245 | 145 | 0 | 0 |

짧은 청크 개수 자체가 모두 오류라는 뜻은 아니다. 다만 KR p.21의 검색 결과 heading이
901 대신 반복 장·편 머리말이며, p.55에는 인쇄 쪽번호가 붙은 꼬리말 heading도 있다.
Q04의 전체 검색 1위는 정기검사 본문이 아닌 **KR p.5 목차**였고 실제 기대 조항은 5위였다.
목차 처리 개선 이후에도 목차 청크를 본문과 동일하게 검색하면 목차가 먼저 나올 수 있다.

### 4. BM25 반복 처리 비용

현재 브랜치는 청크 토큰 캐시가 없고 질문마다 5,485개 청크의 Kiwi 분석과 BM25 객체 생성을 반복한다.
이번 측정에서 DB 조회보다 검색 함수의 비용이 컸다. 최신 팀 main의 토큰 재사용 개선을 통합한 뒤
동일 질문·corpus로 다시 측정해야 하며 이번 작업에서 main을 머지하지 않았다.

## 권장 다음 순서

1. 재사용/신규 벡터 자료형 통일 및 혼합 배치 회귀 테스트 추가.
2. 사용자 승인 후 실패 작업 retry, 세 PDF의 전체 완료/현재 record 존재 확인.
3. 같은 10질문으로 진짜 BM25/vector/hybrid 비교. fallback을 별도 실패 지표로 기록.
4. Q08/Q10 중심으로 한영 표현·전문 용어·의도 구분을 평가하고 과적합을 피하도록 다른 질문도 추가.
5. KR 원문 기반 재청킹/heading 복구와 목차 우선순위 정책을 검토. 단순 벡터 재색인은 청크를 고치지 않는다.

## 재현

현재 앱을 켜 둔 상태에서 프로젝트 루트 PowerShell:

```powershell
docker compose exec rag-worker python -m api.rag_worker status --limit 100
docker compose run --rm --no-deps -v ./scripts:/app/scripts:ro backend python scripts/debug_retrieval.py "Part 6의 SOx scrubber 설계 검토를 위해 제출해야 하는 도면과 자료는?" --top-k 5
docker compose run --rm --no-deps -v ./scripts:/app/scripts:ro backend python scripts/debug_retrieval.py "SOx scrubbers plans and data to be submitted" --top-k 5
```

위 명령은 기존 진단 CLI다. Top-5에는 79위·53위 후보가 보이지 않는 것이 정상이다.
원래 질문을 문서 필터 없이 실행해야 위 전체 corpus 결과와 비교할 수 있다.
관리자 전용 문서가 추가되면 `--username admin`과 guest의 corpus가 달라지므로 같은 역할로 비교한다.
현재 평가 문서는 모두 공개 scope였다.

질문 10개 일괄 실행은 로컬 진단 스크립트 `.verification/run-registered-eval.py`,
metadata 결과는 `.verification/registered-rag-evaluation.json`에 보관했다(둘 다 Git 제외).
`uv run --locked --project backend python .verification/run-registered-eval.py`로 재실행할 수 있다.
새 정식 평가 CLI는 이번 범위에서 구현하지 않았다. 질문 JSON과 본 보고서는 재사용 가능하다.
