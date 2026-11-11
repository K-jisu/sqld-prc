# SQLD Practice

SQLD 문제풀이와 모의시험을 혼자 공부하기 위한 개인 학습 앱입니다. PC와 모바일에서 쓰기 위해 비공개로 배포하며, 비밀번호로 로그인해야 문항과 기록을 볼 수 있습니다.

- 프론트: Next.js App Router, React, TypeScript, Tailwind CSS, TanStack Query
- 백엔드: Python, FastAPI, SQLModel, psycopg, Alembic
- DB 계획: Neon PostgreSQL

이 저장소는 공개 상태입니다. 교재 PDF·변환한 문항 데이터·문항 이미지는 커밋하지 않습니다.

## 개발 실행

프로젝트 루트에서 각각 별도 터미널로 실행합니다.

### 프론트

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

http://localhost:3000 에서 확인합니다. 프로젝트의 pnpm 버전은 `frontend/package.json`의 `packageManager`에 고정합니다.

전역 pnpm 실행기가 다른 버전이나 설치 경로를 가리켜 실행되지 않는 환경에서는 동일한 프로젝트 버전을 명시합니다.

```bash
npx --yes pnpm@10.32.1 install --frozen-lockfile
npx --yes pnpm@10.32.1 dev
```

이 명령도 의존성 관리는 pnpm으로 수행합니다. npm install을 섞어 사용하지 않습니다.

### 백엔드

```bash
cd backend
uv sync --locked
uv run fastapi dev src/backend/main.py
```

http://127.0.0.1:8000/docs 에서 확인합니다.

## 검증

3단계 DB 모델·마이그레이션·샘플 입력 절차는 [백엔드 README](backend/README.md)에 있습니다. [로컬 PostgreSQL과 실제 Neon 검증 결과](2026-11-11-phase3-database-report.md)를 구분해 기록합니다.

프론트의 `frontend/`에서:

```bash
pnpm lint
pnpm typecheck
pnpm build
```

백엔드의 `backend/`에서:

```bash
uv run pytest -q
```

자세한 실행·검증 방법은 [프론트 README](frontend/README.md)와 [백엔드 README](backend/README.md)를 참고합니다.

## 환경변수와 Git

각 프로젝트의 `.env.example`을 기준으로 필요한 값을 정합니다. 실제 `.env`, 교재 PDF, 가상환경, node_modules, 빌드 결과와 캐시는 Git에서 제외하고 `frontend/pnpm-lock.yaml`, `backend/uv.lock`은 포함합니다. API 연결·DB·로그인 구현에서 예제 변수들을 실제로 연결합니다.

## 설계와 진행

2단계 샘플 준비는 제공 ZIP을 루트에 둔 뒤 백엔드에서 실행합니다.

```bash
cd backend
uv run --locked python scripts/prepare_samples.py
```

자료는 Git에서 제외한 `data/private/phase2/`에 생성됩니다. 생성 결과는 재실행 시 갱신되지만 `user-review.md`의 사용자 기록은 보존합니다. 샘플은 자동으로 검수 완료 처리하지 않습니다. [2단계 결과와 남은 검수](2026-11-10-phase2-report.md)를 참고합니다.

원본 대조로 확인한 교정은 같은 폴더의 `sample-corrections.json`에 보관합니다. 이 파일도 비공개 입력 자료이므로 ZIP과 함께 보관합니다. 재실행 때 원문이 교정 대상과 일치하지 않으면 오류로 알립니다.

- [기술 스택](TECH_STACK.md)
- [작업 체크리스트](WORK_CHECKLIST.md)
- [DB 설계](2026-10-28-database-design.md)
- [API 명세](2026-10-28-api-design.md)
- [OpenAPI](2026-10-28-openapi.json)
