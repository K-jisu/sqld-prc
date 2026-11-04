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

기본 테스트는 애플리케이션 시작과 OpenAPI 응답을 확인합니다. 실제 DB 연결이나 기능 API의 검증은 해당 기능 구현 때 추가합니다.

## 의존성 추가

```bash
uv add 패키지이름
uv add --dev 개발전용패키지이름
```

SQLModel·psycopg·Alembic은 기본 런타임 의존성, pytest는 개발 그룹으로 관리합니다. 변경한 `pyproject.toml`과 `uv.lock`을 함께 버전 관리합니다.

## 환경변수

`.env.example`에는 필요한 이름과 로컬 예시만 둡니다. 실제 값은 Git에서 제외된 `.env` 또는 배포 환경에 설정합니다. 환경변수 로딩, DB 연결, 카카오 연동은 각 구현 단계에서 연결합니다. 현재 앱은 예제 파일의 DB·카카오 값을 사용하지 않습니다.
