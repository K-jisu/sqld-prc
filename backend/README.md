# SQLD Practice Backend

Python + FastAPI 백엔드입니다. 프로젝트와 가상환경·의존성은 uv로 관리합니다.

## 설치

`backend/`에서 실행합니다.

```bash
uv sync --locked
```

`pyproject.toml`은 의존성 선언, `uv.lock`은 해석된 버전, `.venv/`는 로컬 가상환경입니다. `.venv/`는 Git에 포함하지 않습니다. 현재 Python 요구사항은 3.14 이상이며 `.python-version`을 함께 확인합니다.

## 개발 서버

```bash
uv run --env-file .env --locked fastapi dev src/backend/main.py
```

- API 문서: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json

시작 파일은 `src/backend/main.py`입니다. 학습 API는 `/api/v1`에 있고 `/`의 404 응답은 정상입니다.

## 테스트

```bash
uv run pytest -q
```

앱 시작·OpenAPI·문항 변환·입력 검증과 학습 API를 검사합니다. `TEST_DATABASE_URL`이 있으면 실제 PostgreSQL 마이그레이션·제약조건·재입력·풀이 이력 보존도 검사합니다. 없으면 통합 테스트는 명시적으로 건너뜁니다. 화면 연결은 5단계에서 구현했고 모의시험·통계 API는 후속 단계입니다.

```bash
uv run --env-file .env --locked pytest -q
```

`TEST_DATABASE_URL`은 앱 DB와 다른 DB 또는 Neon 테스트 브랜치여야 합니다. 각 테스트는 UUID가 붙은 별도 임시 스키마를 만들고 그 스키마만 정리합니다. 테스트 계정에는 스키마 생성 권한이 필요합니다. 앱 DB를 초기화하거나 기존 풀이 기록을 삭제하지 않습니다.

## 마이그레이션과 문제 입력

DB가 없어도 SQL과 실제 비공개 샘플의 형식을 확인할 수 있습니다.

```bash
uv run --locked alembic upgrade head --sql
uv run --locked python -m backend.import_questions --validate-only
```

Neon을 준비한 뒤 `.env.example`을 참고하여 실제 `.env`에 `DATABASE_URL`과 별도의 `TEST_DATABASE_URL`을 설정합니다. 마이그레이션에는 direct 연결 문자열을 사용하고 `sslmode=require`를 포함합니다. 기존 풀이 기록이 있는 DB의 스키마를 변경하기 전에는 백업합니다.

```bash
uv run --env-file .env --locked alembic upgrade head
uv run --env-file .env --locked python -m backend.import_questions
```

입력 기본값은 루트의 `data/private/phase2/samples.json`과 같은 폴더의 `assets/`입니다. 다른 입력을 쓰려면 `--input 경로 --assets 이미지폴더`를 지정합니다. 문항 번호·책 범위(1과목 50/2과목 126, 문제 PDF 224/해설 PDF 64쪽), 보기 네 개·정답 하나·페이지·이미지 존재와 경로를 검사합니다. 사용자 결정으로 II-61~64·69~70·79~81은 입력에서 제외합니다.

문항 키와 보기 번호로 기존 UUID를 유지해 갱신하며, 채점 완료 답안과 과거 점수는 수정하지 않습니다. 입력은 한 트랜잭션으로 처리합니다. 참조 중인 보기 삭제는 문항 키와 사유를 알리고 전체 입력을 취소합니다. 같은 내용의 draft 재입력으로 이미 게시한 문항을 draft로 되돌리지 않습니다. 게시된 문항에 검수 대기 상태의 다른 내용을 덮어쓰는 것은 거부합니다.

샘플은 draft로 입력하고 검수 메모는 학습 콘텐츠에 저장하지 않습니다. `published` 입력은 `review.user_verified=true`로 확인된 자료만 허용합니다. 학습 생성에 include_drafts=true를 명시하면 검수용으로 풀 수 있으며 사용자 확인 상태를 자동 변경하지 않습니다. 5단계 학습 화면의 `검수 대기 문항 포함`으로 연결했습니다. 검수 상태 변경 기능은 포함하지 않습니다. JSON 출력의 `input_draft`는 입력 파일의 draft 개수입니다.

2026-11-11 검증: 로컬 임시 PostgreSQL 16에 이어 실제 Neon PostgreSQL 18.6에서도 연결·마이그레이션·샘플 8개 재입력과 전체 테스트 71개 통과를 확인했습니다. 사용자 연결 값을 `backend/.env`에 반영했으며 이후 명령은 이 파일을 사용합니다. 앱에는 draft 문항 8개·보기 32개가 있고 테스트용 임시 스키마는 모두 정리됐습니다. 자세한 내용은 [3단계 결과](../2026-11-11-phase3-database-report.md)에 있습니다.

설정 근거: [SQLModel UUID](https://sqlmodel.tiangolo.com/advanced/uuid/), [Alembic 연결 재사용](https://alembic.sqlalchemy.org/en/latest/cookbook.html), [Neon 마이그레이션 연결](https://neon.com/docs/guides/sqlalchemy-migrations).

## 학습 API

- `GET /api/v1/catalog`: 과목·단원과 검수 완료/대기 문항 수.
- `PUT /api/v1/study-sessions/{UUID}`: 전체·과목·단원·최신 오답·완료 목록으로 생성. 같은 UUID와 정규화 조건은 재전송 시 기존 학습을 반환합니다.
- `GET /api/v1/quiz-sessions`, `GET/PATCH /api/v1/quiz-sessions/{UUID}`: 진행 목록·고정 출제 목록·현재 위치.
- `GET /api/v1/quiz-sessions/{UUID}/items/{item_UUID}`: 문항·보기·내 답안. 채점 전 review는 null이고 정답 필드는 보내지 않습니다.
- 해당 item 뒤의 `PATCH /answer`, `POST /grade`, `POST /retry`: 선택/해제·한 문항 채점·새 시도. 과거 답안과 채점 결과를 보존합니다.
- `POST /api/v1/study-sessions/{UUID}/finish`, `GET /api/v1/quiz-sessions/{UUID}/result`: 명시적 종료와 최신 채점 우선 요약. 미채점 문항은 오답으로 만들지 않습니다.
- `GET /api/v1/question-assets/{question_key}/{file_name}`: 참조된 본문·보기 그림. 해설 전용 그림은 해당 문항을 채점한 이후 제공하며 폴더 탈출·임의 파일 접근을 거부합니다.

학습 생성 예: `{"scope":"all"}`. 검수 대기 샘플을 풀려면 `{"scope":"all","include_drafts":true}`를 명시합니다. 기본 학습은 published만 사용하고 draft 상태를 바꾸지 않습니다.

변경 요청은 APP_ORIGIN과 동일한 Origin 헤더와 application/json을 요구합니다. UUID·보기 소속·시도·세션 상태를 서버에서 검사합니다. 생성은 트랜잭션 advisory lock, 변경·종료는 부모 세션 행 잠금으로 동시에 도착한 요청도 한 번씩 처리합니다.

현재 정답·해설은 교정된 문제은행을 따르며 당시 채점 결과·선택·시각·점수는 유지합니다. 앱 인증은 없습니다. 운영 배포에서는 Vercel Authentication의 All Deployments로 화면·API·이미지와 별도 백엔드 직접 주소를 모두 보호해야 합니다. 실제 설정과 우회 차단 검증은 아직 수행하지 않았습니다.

API 문서: `/docs`, 실제 계약: `/openapi.json`. 루트 `2026-10-28-openapi.json`은 현재 구현된 12개 작업의 생성 결과이며, 계획 단계의 모의시험·통계 API는 포함하지 않습니다.

QUESTION_ASSETS_DIR을 비우면 루트 data/private/phase2/assets를 사용합니다. 배포용 영구 저장 위치는 후속 단계에서 설정합니다. 이미지와 교재 자료는 Git에 넣지 않습니다.

## 의존성 추가

```bash
uv add 패키지이름
uv add --dev 개발전용패키지이름
```

SQLModel·psycopg·Alembic은 기본 런타임 의존성, pytest는 개발 그룹으로 관리합니다. 변경한 `pyproject.toml`과 `uv.lock`을 함께 버전 관리합니다.

## 환경변수

`.env.example`에는 필요한 이름과 로컬 예시만 둡니다. 실제 값은 Git에서 제외된 `.env` 또는 배포 환경에 설정합니다. `.env`는 `uv run --env-file .env ...`로 로드합니다. 앱 생명주기에 DB 엔진을 준비하고 첫 DB 요청에서 연결합니다. 요청별 트랜잭션은 응답 전 완료하며 실패하면 취소합니다. 앱 시작 시 마이그레이션·입력·테이블 생성은 하지 않습니다. 앱 로그인·로그아웃은 제공하지 않습니다.

4단계 검증(2026-11-11): 로컬 PostgreSQL 16과 실제 Neon PostgreSQL 18.6에서 각각 전체 104개 통과. 실제 Uvicorn HTTP와 임시 테스트 스키마의 draft 샘플 8개도 검증했습니다. 앱 DB의 풀이 기록은 0건이며 테스트 스키마는 모두 정리됐습니다. [4단계 결과](../2026-11-11-phase4-study-api-report.md)를 참고합니다.
