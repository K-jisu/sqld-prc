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
uv run fastapi dev src/backend/main.py
```

- API 문서: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json

시작 파일은 `src/backend/main.py`입니다. 현재 기능 경로는 아직 정의하지 않았으므로 `/`의 404 응답은 정상입니다.

## 테스트

```bash
uv run pytest -q
```

기존 앱 시작·OpenAPI 테스트와 문항 변환·입력 검증을 실행합니다. `TEST_DATABASE_URL`이 있으면 실제 PostgreSQL 마이그레이션·제약조건·재입력·풀이 이력 보존도 검사합니다. 없으면 통합 테스트는 명시적으로 건너뜁니다. API 기능은 아직 구현하지 않았습니다.

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

샘플은 draft로 입력하고 검수 메모는 학습 콘텐츠에 저장하지 않습니다. `published` 입력은 `review.user_verified=true`로 확인된 자료만 허용합니다. 최종 확인을 앱에서 문제를 풀며 하는 흐름은 이후 API·화면 단계에서 연결합니다. JSON 출력의 `input_draft`는 입력 파일의 draft 개수입니다.

2026-11-11 검증: 로컬 임시 PostgreSQL 16에 이어 실제 Neon PostgreSQL 18.6에서도 연결·마이그레이션·샘플 8개 재입력과 전체 테스트 71개 통과를 확인했습니다. 사용자 연결 값을 `backend/.env`에 반영했으며 이후 명령은 이 파일을 사용합니다. 앱에는 draft 문항 8개·보기 32개가 있고 테스트용 임시 스키마는 모두 정리됐습니다. 자세한 내용은 [3단계 결과](../2026-11-11-phase3-database-report.md)에 있습니다.

설정 근거: [SQLModel UUID](https://sqlmodel.tiangolo.com/advanced/uuid/), [Alembic 연결 재사용](https://alembic.sqlalchemy.org/en/latest/cookbook.html), [Neon 마이그레이션 연결](https://neon.com/docs/guides/sqlalchemy-migrations).

## 의존성 추가

```bash
uv add 패키지이름
uv add --dev 개발전용패키지이름
```

SQLModel·psycopg·Alembic은 기본 런타임 의존성, pytest는 개발 그룹으로 관리합니다. 변경한 `pyproject.toml`과 `uv.lock`을 함께 버전 관리합니다.

## 환경변수

`.env.example`에는 필요한 이름과 로컬 예시만 둡니다. 실제 값은 Git에서 제외된 `.env` 또는 배포 환경에 설정합니다. `.env`는 `uv run --env-file .env ...`로 로드합니다. DB 엔진은 환경변수를 읽어 명시적 마이그레이션·입력 명령에서 생성하며, 앱 시작 시 DB 연결·테이블 생성은 하지 않습니다. 비밀번호 로그인은 다음 API 단계에서 구현합니다.
