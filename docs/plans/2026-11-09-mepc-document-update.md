# MEPC 문서 등록과 표시 정리

- 상태: 완료 (실행 환경에 따른 미검증 범위는 아래 기록)
- 작성: Codex · 2026-11-09
- 목표: 기존 문서명 테스트용 표시, 지정 MEPC 10건 등록, 전체 페이지 타이틀 통일.

## 범위와 단계

- [x] 최신 v2 소스와 업로드 PDF 10개 확인. MEPC.338(76)은 제외.
- [x] 기존 10개 기본 문서 제목에 `(테스트용)` 추가, 제목 끝 `(가상)` 제거.
- [x] 영어 원문 412개 비어 있지 않은 물리 페이지와 원본 PDF 묶음 준비.
- [x] 기존 DB도 초기화 없이 갱신하는 일회성 bootstrap 업데이트. 완료 마커·재시도·색인 갱신.
- [x] SSR과 브라우저 타이틀을 `해답 · SEA THE ANSWER`로 통일.
- [x] 단위 검사 및 SQL 등록·기존 ID/본문/PDF 보존·실패 시 rollback 확인.
- [x] 빌드 HTML 타이틀·배포 ZIP 구성 확인. 브라우저 자동 검사는 실행 환경 문제로 미완료.

## 구현과 한계

변경한 실행 모듈은 backend/api/knowledge_update.py, store/__init__.py와 frontend/src/workspace/provider.jsx다. 새 런타임 의존성이나 DB 테이블을 추가하지 않는다. 기존 답변 스냅샷과 문서 개정 ID는 보존하며, MEPC 중복 내용과 초안은 메타데이터에 표시한다. 문서 등록이 공식 CII 계산이나 최신 법령 자동 판정 기능을 추가하지는 않는다.

## 검증 기록

- 2026-11-09: 관련 backend 48개 통과, frontend 단위 30개 통과, production 빌드 성공.
- 2026-11-09: 격리 PGlite(PostgreSQL WASM)와 psycopg로 SQL 검사 3개 통과. 신규 20건·원본 PDF 15개, 기존 자료 보존, 재시작 중복 방지·삭제 유지, 중간 실패 원자적 취소 및 재시도, 원문 페이지 검색 확인. 임베딩 fingerprint는 고정 시험값으로 대체했다. Docker PostgreSQL·E5·Chroma 전체 실행 검증과 구분한다.

- 브라우저 자동 검사는 설치/실행 오류로 완료하지 못했다. 앱 HTML 8개의 타이틀은 확인했다. 확대 저장 검사는 모델 fingerprint를 시험값으로 고정해 64 passed / 2 skipped이며 전체 Docker 검증은 미수행이다.
