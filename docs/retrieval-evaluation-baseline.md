# 해사 질문 검색 초기 평가 — 2026-10-28

> 2026-10-28 · 팀 main `91a1cc6` 기반의 로컬 초기 평가. Python 3.13.7 / Windows 11 / Intel Core i5-1335U, `uv sync --frozen` 환경에서 실행했다. 원문·질문·검색 코드 해시는 아래에 기록한다. 앱 DB·화면·런타임은 변경하지 않았다.

## 해석과 확인 사항

- 정답이 있는 16개 중 정답 근거가 1위인 질문은 15개, 상위 5개 안에 포함된 질문은 16개다. 작성자 평가셋에 대한 결과이며 일반 질의·LLM 정답률 100%를 의미하지 않는다.
- q09(Noon report 정의)의 용어집 근거는 2위다. 1위는 선박직원법 정의 조항으로, 상위 결과의 관련성 개선 후보로 남긴다. 검색 코드는 변경하지 않았다.
- 답 없는 질문 4개 모두 검색 후보가 노출됐다. q19의 일반 CII 설명은 개별 선박의 검증된 등급을 제공하지 않으므로 검색 성공으로 세지 않는다. 최종 답변 보류 여부는 이번 검색 평가로 판정할 수 없다.
- 첫 초안에서는 일부 영문 질문에 International 조건을 쓰지 않고 해당 절만 정답으로 지정한 모호함을 발견했다. q14~q16에 조건을 명시한 뒤 전체를 다시 측정했다. 검색 알고리즘을 조정하거나 실패 질문을 제거하지 않았다.
- `--repeats 1`로 질문별 1회씩 측정했다. 첫 검색 약 12.965초, 이후 20개 질문의 p50 약 7.009초, p95 약 7.664초다. API·DB·LLM 처리 시간은 포함하지 않으며, 별도 부하 통제나 반복 신뢰 구간을 확보한 성능 보증이 아니다.
- 검색 호출마다 전체 후보를 토큰화·인덱싱하는 현재 동작을 측정했다. 처리 시간 개선 전후 비교를 위한 기준선이며, 운영 최적화는 별도 변경으로 진행해야 한다.
- 관련 pytest 110개 통과. 질문 조건을 명확히 한 뒤 평가 도구의 15개 테스트를 다시 실행해 통과했다(중복 실행을 합산하지 않음). 전체 backend·Docker·실제 LLM 테스트를 실행했다고 해석하지 않는다.

재현 명령(저장소 최상위):

```powershell
cd backend
uv sync --frozen
uv run python ../scripts/evaluate_retrieval.py --repeats 1
```

실행법·지표 정의·자료 제한은 [검색 평가 안내](retrieval-evaluation.md)를 참고한다. 자동 생성 원본 결과의 로컬 위치는 `output/retrieval-evaluation/results.{json,csv,md}`다. 아래는 이 실행의 자동 생성 결과다.

---

## 자동 생성 측정 결과

실행: 2026-10-28T11:53:23.724640+00:00
문서 청크 955개 · 질문 20개 · k=5 · 반복 1회

- Hit@k: 1.0000
- Recall@k: 1.0000
- MRR@k: 0.9688
- 답 없음 질문의 빈 검색 결과 비율: 0.0000
- 첫 검색 12964.7 ms / 반복 p50 7009.5 ms / p95 7664.1 ms

검색 함수만 측정했습니다. DB·권한·API·LLM·답변 정확성·실제 선박 적용성 검증이 아닙니다.
답 없는 질문의 검색 후보 노출은 환각이나 잘못된 최종 답변을 의미하지 않습니다.

| ID | 질문 | 유형 | 결과 | Recall@k | 중앙 시간(ms) |
|---|---|---|---|---|---|
| q01 | ECA 밖에서 사용하는 연료의 황 함유량 한도는 얼마야? | answerable | complete | 1.0000 | 7407.7 |
| q02 | 배출규제해역 안에서는 연료 황 함유량이 몇 퍼센트여야 해? | answerable | complete | 1.0000 | 7499.8 |
| q03 | CII 적용 대상은 DWT로 판단해, GT로 판단해? | answerable | complete | 1.0000 | 7609.2 |
| q04 | CII가 D 등급으로 3년 연속이면 어떤 조치가 필요해? | answerable | complete | 1.0000 | 7489.5 |
| q05 | E 등급을 한 번 받으면 CII 개선 계획을 내야 해? | answerable | complete | 1.0000 | 7149.1 |
| q06 | 가상 연료 전환 점검표에는 무엇을 기록하게 되어 있어? | answerable | complete | 1.0000 | 7431.2 |
| q07 | 가상 계산 예제의 단순 탄소집약도 공식은 뭐야? | answerable | complete | 1.0000 | 7343.6 |
| q08 | DWT와 GT는 같은 단위야? | answerable | complete | 1.0000 | 7542.4 |
| q09 | Noon report가 무슨 뜻인지 알려줘. | answerable | complete | 1.0000 | 7604.8 |
| q10 | 해양환경관리법에서 기름오염방지설비 설치는 어떻게 정하고 있어? | answerable | complete | 1.0000 | 8708.3 |
| q11 | 선박오염물질기록부는 얼마 동안 보존해야 해? | answerable | complete | 1.0000 | 6869.8 |
| q12 | COLREG Rule 5 requires which means for keeping a proper look-out? | answerable | complete | 1.0000 | 4315.0 |
| q13 | What factors determine safe speed under International Rule 6? | answerable | complete | 1.0000 | 4295.6 |
| q14 | Under COLREG International Rule 7, what should a vessel assume if there is doubt about risk of collision? | answerable | complete | 1.0000 | 4273.8 |
| q15 | Under COLREG International Rule 8, should a succession of small course alterations be used to avoid collision? | answerable | complete | 1.0000 | 4324.2 |
| q16 | Under COLREG International Rule 15, which vessel keeps out of the way in a crossing situation? | answerable | complete | 1.0000 | 4259.5 |
| q17 | 우리 배 주기관 XZ-999의 고장코드 E742를 어떻게 수리해? | unanswerable | candidate_review | N/A | 4565.7 |
| q18 | 내일 부산항 입항 시각의 실시간 풍속을 알려줘. | unanswerable | candidate_review | N/A | 4268.0 |
| q19 | 우리 선박의 2025년 검증된 공식 CII 등급을 알려줘. | unanswerable | candidate_review | N/A | 4535.2 |
| q20 | 선장님 개인 휴대전화 번호 알려줘. | unanswerable | candidate_review | N/A | 4139.8 |

## 실패·부분 검색·답 없음 후보의 수동 검토

### q17: 우리 배 주기관 XZ-999의 고장코드 E742를 어떻게 수리해?

해당 기종 정비 매뉴얼이 없으므로 일반 검색 후보를 수리 절차로 확정하지 않고 매뉴얼을 요청한다.

- 검색 후보 `kr-maritime-traffic-safety-act:91`: 제2절 선박이 서로 시계 안에 있는 때의 항법 · 제78조(앞지르기) (p.22)
- 검색 후보 `kr-ship-officers-act:22`: 제3장 선박직원 · 제13조(허가에 의한 승무기준의 특례) (p.7)
- 검색 후보 `kr-maritime-traffic-safety-act:58`: 제1절 선박의 안전관리체제 · 제50조(인증심사 업무의 대행 등) (p.14)
- 검색 후보 `kr-maritime-traffic-safety-act:85`: 제1절 모든 시계상태에서의 항법 · 제74조(좁은 수로 등) (p.21)
- 검색 후보 `kr-maritime-traffic-safety-act:8`: 제1절 해양시설의 보호수역 설정 및 관리 · 제6조(보호수역의 입역) (p.3)

### q18: 내일 부산항 입항 시각의 실시간 풍속을 알려줘.

문서 스냅샷에 실시간 기상 정보가 없음을 알린다.

- 검색 후보 `kr-maritime-traffic-safety-act:98`: 제4절 등화와 형상물 · 제85조(적용) (p.24)
- 검색 후보 `kr-maritime-traffic-safety-act:34`: 제2절 항행장애물의 처리 · 제29조(국내항의 입항ㆍ출항 등 거부) (p.9)
- 검색 후보 `kr-maritime-traffic-safety-act:80`: 제1절 모든 시계상태에서의 항법 · 제70조(경계) (p.20)
- 검색 후보 `sample-fuel-checklist:1`: 연료 전환 기록 / Fuel changeover checklist (p.None)
- 검색 후보 `kr-maritime-traffic-safety-act:65`: 제2절 선박 점검 및 사업장 안전관리 · 제57조(항만국통제) (p.16)

### q19: 우리 선박의 2025년 검증된 공식 CII 등급을 알려줘.

일반 CII 설명과 개별 선박의 검증된 등급을 구분하고 선박과 검증 자료를 요청한다.

- 검색 후보 `imo-cii:2`: CII 등급과 시정조치 / Rating and corrective action (p.None)
- 검색 후보 `maritime-glossary:6`: 탄소집약도와 에너지효율 / EEDI, EEXI, CII, SEEMP (p.None)
- 검색 후보 `sample-carbon:1`: 배출량과 단순 탄소집약도 / Emissions calculation (p.None)
- 검색 후보 `imo-cii:1`: CII 적용 대상 / Scope (p.None)
- 검색 후보 `kr-ship-officers-act:13`: 제2장 해기사의 자격과 면허 등 · 제8조(면허의 실효) (p.4)

### q20: 선장님 개인 휴대전화 번호 알려줘.

개인 연락처 자료가 없으므로 번호를 만들어 내지 않는다.

- 검색 후보 `kr-maritime-traffic-safety-act:136`: 제7장 벌칙 · 제117조(양벌규정) (p.33)
- 검색 후보 `kr-marine-environment-management-act:154`: 제12장 벌칙 · 제130조(양벌규정) (p.40)
- 검색 후보 `kr-ship-officers-act:43`: 제5장 벌칙 · 제30조(양벌규정) (p.10)
- 검색 후보 `kr-maritime-traffic-safety-act:50`: 제1절 선박의 안전관리체제 · 제45조(선장의 권한 등) (p.12)
- 검색 후보 `kr-maritime-traffic-safety-act:69`: 제2절 선박 점검 및 사업장 안전관리 · 제60조(지도ㆍ감독) (p.17)

## 재현 환경

```json
{
  "python": "3.13.7",
  "platform": "Windows-11-10.0.26200-SP0",
  "packages": {
    "kiwipiepy": "0.24.0",
    "kiwipiepy_model": "0.24.0",
    "rank-bm25": "0.2.2",
    "numpy": "2.5.4"
  },
  "sha256": {
    "seed": "ebc05ebdeca8010a18e25b1b922de8ecb6d34e80f9ec9748241ad92394ebb4bb",
    "cases": "4bb2698defb530990bc18ca4398439e303f1159982ba0cb254250f6f6bd622b4",
    "runner": "73fb2d98227f1c060d0f83aaffa2383799d3600c92c1d2c8bb750b1387ceb53d",
    "preprocessing": "b8d59d454d88fba539ee7250ceee2d7aa2089847f04c5607388dafdef8777ea6",
    "retrieval": "d15a0d4021ce3a05f1a1012455064f02d7b545649aeeed86cdb93f7d2746e534",
    "vocabulary": "7a5be9f686f14214fb291c817d6958b3ca31e54d838128c28630998142c032f0"
  },
  "scope": "offline seed snapshot; no DB, authentication, API or LLM; author-labelled pilot"
}
```
