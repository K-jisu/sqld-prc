# 3단계 DB 구현과 Neon 연결·검증 결과

작성일: 2026-11-11. **3단계 완료: Neon 연결·마이그레이션·샘플 재입력과 전체 테스트 71개 통과.**

사용자는 처음에는 Neon이 없어 DB 코드부터 진행하도록 선택했고, 같은 날 Neon 연결정보를 설정했다. 샘플 최종 확인은 완성된 앱에서 문제를 풀며 하기로 했으며, 이를 사용자 검수 완료로 기록하지 않았다.

## 구현한 내용

- 기존 설계의 테이블 7개를 SQLModel로 작성했다: subjects, chapters, questions, question_options, quiz_sessions, quiz_items, answer_attempts.
- UUID·JSONB·시간대 있는 시각과 페이지·상태 CHECK, 고유키, 복합 외래키, 부분 고유 인덱스를 적용했다.
- Alembic 초기 revision `0001`을 작성했다. 앱 시작 시 테이블을 만들지 않으며 명시적 마이그레이션 명령으로만 변경한다.
- PostgreSQL URL을 환경변수에서 읽고 설치된 psycopg 드라이버를 사용한다. Neon URL은 TLS를 요구하며 연결 문자열·SQL 매개변수를 출력하지 않는다.
- 입력에서 고정 문항 키·과목/단원·책 범위·보기 네 개·정답 하나·페이지·이미지 경로와 존재를 검사한다. 누락·불완전 9문항은 제외한다.
- 입력은 한 트랜잭션으로 실행하고 문항·선택지 UUID를 유지한다. 과거 답안·채점 결과를 재계산하지 않는다. 참조된 보기 삭제는 거부하고 전체 입력을 취소한다.
- 같은 내용의 draft 재입력은 기존 published 상태를 보존한다. 게시된 문항에 미검수 내용 변경을 덮어쓰는 것은 거부한다.
- 실제 샘플은 draft로 입력한다. 검수 메모·생성된 그림 설명은 학습 콘텐츠에 저장하지 않는다.

## 로컬 PostgreSQL 검증

먼저 기존 로컬 Docker의 PostgreSQL 16 이미지로 localhost에만 연결되는 별도 임시 DB를 만들어 검사했다. 이 로컬 검사에서는 Neon과 기존 사용자 DB를 사용하지 않았다.

| 검증 | 결과 |
|---|---|
| 변경 전 기준 테스트 | 21 passed |
| 최종 전체 테스트, 실제 PostgreSQL 포함 | 71 passed (6.89s) |
| 빈 DB 마이그레이션 | 테이블 7개·제약·인덱스 생성, revision 0001, 모델과 차이 없음 |
| 같은 마이그레이션 재적용 | 중복 테이블·변경 없음 |
| 실제 비공개 샘플 입력·재입력 | 과목 2개·단원 5개·문항 8개·보기 32개, UUID 유지, 모두 draft |
| 과거 답안 보존 | 합성 문항의 정답 변경·두 번 재입력 후 기존 선택·채점 결과·시각·정답 집계 유지 |
| 입력 실패 취소 | 뒤 문항의 참조 보기 삭제가 거부될 때 앞 문항 변경도 취소됨 |
| DB 직접 제약 | 다른 문항 보기 참조, 정답·진행 모의시험·미채점 답안 중복과 잘못된 상태 조합 거부 |
| 삭제 범위 | 세션 삭제 시 해당 출제·답안만 삭제, 문제은행 보존. 참조 보기 직접 삭제 거부 |
| DB 없는 실행 | 47 passed, 24 skipped (0.96s). 샘플 8개 검증과 오프라인 SQL 생성 가능 |

PostgreSQL 테스트는 각 테스트 전용 UUID 스키마를 만들고 그 스키마만 정리한다. 앱과 TEST_DATABASE_URL이 같은 DB를 가리키면 실행을 거부한다. 실제 샘플 검사 후 남은 임시 테스트 스키마가 없음을 확인했다.

## Neon 실제 연결 검증

- 사용자 설정은 프로젝트 루트 `.env`에 있었다. 값을 출력하지 않고 형식·TLS·direct URL·앱/테스트 대상 분리를 확인한 뒤 두 연결 값만 `backend/.env`에 반영했다. 다른 설정과 루트 파일은 보존했다. 이후 백엔드 명령의 기준 파일은 `backend/.env`다.
- 앱용·테스트용 Neon 서버 모두 PostgreSQL 18.6이었다. 두 대상 모두 앱 테이블과 마이그레이션 이력이 비어 있음을 확인하고 진행했다.
- 앱 DB에 초기 revision 0001을 적용하고 모델과의 차이가 없음을 확인했다. 과목 2개·단원 5개·문항 8개·보기 32개를 입력하고 재입력해 UUID가 유지됨을 확인했다. 문항은 모두 draft이며 풀이 세션·배정·답안은 0건이다.
- 첫 전체 실행은 70 passed, 1 failed였다. 참조 보기 삭제는 정상 거부됐으나 PostgreSQL 18의 RESTRICT 오류 코드 23001이 로컬 PostgreSQL 16의 예상값 23503과 달랐다.
- [PostgreSQL 18 원본 구현](https://raw.githubusercontent.com/postgres/postgres/REL_18_STABLE/src/backend/utils/adt/ri_triggers.c)과 [공식 오류 코드 표](https://www.postgresql.org/docs/18/errcodes-appendix.html)로 확인했다. 테스트는 두 버전의 코드를 허용하면서 해당 외래키 이름과 오류 후 보기·답안 보존까지 검사하도록 보완했다. 해당 단일 테스트는 1 passed다.
- 수정 후 별도 Neon 테스트 DB에서 전체 **71 passed (186.75s)**를 확인했다. 앱 DB의 샘플·draft 상태·풀이 기록 0건이 유지됐고, 앱·테스트 DB 모두 남은 테스트용 임시 스키마는 0개다. 테스트 DB의 public에는 앱 테이블이 생성되지 않았다.
- 최종 결과는 Git 제외 `data/private/neon-verification.json`, 비밀 값을 가린 전체 테스트 출력은 `data/private/neon-test-results-final.log`에 기록했다.

## 별도 코드 검토와 수정

별도 검토에서 게시 상태의 재입력 회귀, 원문 범위 상한 누락, 참조 보기 삭제의 CLI 안내 부족을 확인했다. 각각 실패하는 회귀 테스트를 먼저 실행한 뒤 수정했고 전체 테스트를 통과했다. 값이 같은 재입력은 사용자 확인을 보존하고, 변경된 미검수 입력은 문항 키와 검수 필요 사유만 알린다.

초기 통합 테스트에서는 참조되지 않는 추가 보기를 삭제한 뒤 다시 ORM에 추가하려는 오류도 발견해 수정했다. 해당 실패 시나리오와 참조 중인 보기 삭제 거부를 모두 테스트한다.

## 실행 방법

`backend/`에서 DB 없이 확인:

```bash
uv run --locked alembic upgrade head --sql
uv run --locked python -m backend.import_questions --validate-only
```

Neon을 준비한 다음 Git 제외 `.env`에 direct 연결 문자열을 설정한다. DATABASE_URL은 앱/개발용 DB, TEST_DATABASE_URL은 별도 DB 또는 테스트 브랜치다.

```bash
uv run --env-file .env --locked alembic upgrade head
uv run --env-file .env --locked python -m backend.import_questions
uv run --env-file .env --locked pytest -q
```

검증에는 기존 `.venv`를 사용했고 pyproject.toml·uv.lock과 런타임 의존성은 변경하지 않았다. 자세한 환경변수·오류 안내는 [백엔드 README](backend/README.md)에 있다.

## 남은 작업과 검증 범위

- Neon 연결·마이그레이션·샘플 입력·전체 테스트와 임시 스키마 정리까지 완료했다. 연결정보는 Git 제외 파일에서만 사용하며 테스트 결과 로그에서도 연결 문자열·비밀번호·호스트를 가렸다.
- 로그인·문항 조회·채점 API, 사용자 최종 확인을 위한 앱 흐름·화면·모바일·배포는 이번 단계에 포함하지 않았다.
- 실제 사용자 풀이 기록을 수정하거나 삭제하지 않았다. 커밋·푸시·기존 작업 복원은 하지 않았다.
- 마지막 실제 샘플 재입력에서도 문항 8개·보기 32개의 UUID와 draft 상태 유지 확인 후, 직접 만든 임시 PostgreSQL 컨테이너를 중지·자동 제거하고 임시 연결 파일도 삭제했다. 기존 컨테이너·DB는 변경하지 않았다.
