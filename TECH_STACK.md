# SQLD Practice 기술 스택

최종 정리: 2026-11-04

프로젝트 위치: `C:\Users\wltn7\Desktop\sqld-prc`

대화에서 선택한 기술과 현재 프로젝트 설정을 정리한다. 실제 설정에 있는 기술과 앞으로 도입할 기술을 구분한다.

## 1. 핵심 구성

| 구분 | 선택한 기술 | 역할 |
|---|---|---|
| 프론트엔드 | Next.js App Router + React + TypeScript | 웹 화면과 라우팅 |
| 스타일 | Tailwind CSS 4 | 모바일·PC 반응형 스타일 |
| 서버 데이터 관리 | TanStack Query 5 | API 조회 결과 캐시와 요청 상태 관리 |
| 프론트 패키지 관리 | pnpm | 패키지 설치와 실행 |
| 백엔드 언어 | Python | 서버 코드 작성 |
| 백엔드 프레임워크 | FastAPI | 문제 조회·채점·시험·학습 기록 API |
| 데이터베이스 | PostgreSQL | 문제은행·사용자·풀이 기록 저장 |
| DB 클라우드 서비스 | Neon | PostgreSQL 호스팅 |
| 로그인 | 카카오 OAuth 2.0 | 별도 회원가입 입력 화면 없이 로그인 |

백엔드는 Spring Boot도 검토했지만 최종적으로 Python + FastAPI를 선택했다. DB는 초기 SQLite 안에서 Neon PostgreSQL로 변경했다.

## 2. 프론트엔드

- Next.js는 App Router를 사용한다.
- TypeScript로 작성하고 Tailwind CSS로 모바일과 PC를 모두 지원한다.
- 서버 데이터는 TanStack Query 5, 단순 화면 상태는 React 기본 상태로 관리한다.
- HTTP 요청은 기본 fetch를 사용한다.
- 패키지 관리자는 pnpm이다.
- 화면 디자인과 배치는 AI가 만든 결과를 보고 사용자가 판단한다.

현재 `frontend/package.json`에 선언된 버전은 다음과 같다. 2026-11-04에 고정 버전 설치, lint, 타입 검사, 프로덕션 빌드와 개발 서버의 기본 페이지 HTTP 200 응답을 확인했다.

| 패키지 | 선언된 버전 |
|---|---|
| next | 16.4.4 |
| react / react-dom | 19.3.0 |
| typescript | ^5 |
| tailwindcss | ^4 |
| @tailwindcss/turbopack | ^4 |
| eslint | ^9 |
| eslint-config-next | 16.4.4 |
| @tanstack/react-query | ^5.105.3 |
| pnpm (packageManager) | 10.32.1 |

TanStack Query는 의존성에 추가했다. Provider와 실제 API 연결은 화면 연동 단계에서 구현한다. 전역 pnpm 실행기가 잘못된 설치 경로를 가리키는 환경에서는 `npx --yes pnpm@10.32.1 <명령>`으로 같은 버전을 실행한다.

## 3. 백엔드

FastAPI를 중심으로 기존 DB·API 설계에서 잡은 구성이다. FastAPI·SQLModel·psycopg·Alembic은 런타임 의존성, pytest는 개발 의존성으로 설치했다. Pydantic은 FastAPI 의존성으로 함께 설치된다.

| 기술 | 역할 |
|---|---|
| FastAPI | HTTP API와 요청 처리 |
| Pydantic | 요청·응답 데이터 형식 정의와 검증 |
| SQLModel | Python 코드와 DB 테이블·조회 연결 |
| psycopg 3 | PostgreSQL 연결 드라이버 |
| Alembic | DB 테이블 구조 변경 이력 관리 |
| pytest | 백엔드 개발 테스트 |

- API는 REST·JSON 방식이며 브라우저 기준 경로는 `/api/v1`이다.
- 프론트와 백엔드를 별도 배포해도 브라우저는 같은 출처의 API 경로를 사용하도록 연결한다.
- DB 연결 정보와 카카오 인증 비밀은 백엔드에서만 관리한다.
- 로그인 상태는 서버 접속 세션과 HttpOnly 쿠키로 관리한다.
- Python 의존성은 프로젝트 전용 가상환경으로 분리한다.
- 백엔드 패키지 관리자는 uv다. `pyproject.toml`, `uv.lock`, `.venv/`로 선언·잠금·가상환경을 관리한다.

uv 프로젝트 초기화와 의존성 설치를 확인했다. 현재 `requires-python`은 `>=3.14`, `.python-version`은 `3.14`이며 로컬 검증은 Python 3.14.3에서 진행했다. 기본 라이브러리 import와 FastAPI 시작·OpenAPI 응답 테스트 1개가 통과했다. 배포 환경의 Python 호환성은 배포 단계에서 확인한다.

## 4. 데이터베이스와 인증

- Neon PostgreSQL에 문제은행·사용자·풀이 기록을 저장한다.
- 로그인 없이 문제풀이·채점·해설·모의시험·현재 시험 결과를 이용할 수 있다.
- 개인 통계·오답 목록·지난 시험 이력·기기 간 이어 풀기는 카카오 로그인 후 제공한다.
- 로그인 직전 현재 게스트 풀이 기록을 계정에 연결한다.

## 5. 배포·테스트 계획

| 항목 | 현재 상태 |
|---|---|
| 프론트 배포 | 기존 검토안은 Vercel. 실제 배포 설정은 아직 확인하지 않음 |
| 백엔드 배포 | 기존 검토안은 Vercel의 FastAPI 배포. 최종 설정과 호환성은 배포 단계에서 확인 |
| DB 배포 | Neon 사용으로 결정. 무료 플랜으로 시작하는 방향이며 실제 한도는 사용 시 확인 |
| 백엔드 테스트 | pytest 설치, 앱 시작·OpenAPI 응답 테스트 1개 통과 |
| 브라우저 테스트 | Playwright로 주요 흐름 검증을 제안한 상태 |

## 6. 프로젝트 구조와 진행 방식

```text
sqld-prc/
├─ frontend/                    # Next.js
├─ backend/                     # Python + FastAPI
├─ TECH_STACK.md
├─ 2026-10-28-database-design.md
├─ 2026-10-28-api-design.md
└─ 2026-10-28-openapi.json
```

사용자가 초기 세팅을 직접 진행한다. AI는 요청받은 명령어·설정의 역할을 설명하고 결과를 확인하는 방식으로 돕는다. 기능 구현은 이후에 진행한다.

## 7. 관련 설계 문서

- [DB 설계안](2026-10-28-database-design.md)
- [API 명세](2026-10-28-api-design.md)
- [OpenAPI JSON](2026-10-28-openapi.json)
