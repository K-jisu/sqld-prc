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
| 데이터베이스 | PostgreSQL | 문제은행·풀이 기록 저장 |
| DB 클라우드 서비스 | Neon | PostgreSQL 호스팅 |
| 접근 보호 | Vercel Authentication + All Deployments | 본인 계정만 접속, 앱 인증 제외 |

백엔드는 Spring Boot도 검토했지만 최종적으로 Python + FastAPI를 선택했다. DB는 초기 SQLite 안에서 Neon PostgreSQL로 변경했다. 2026-11-04 비공개 배포 기준으로 앱 비밀번호 로그인을 검토했고, 2026-11-11 사용자 결정으로 이를 제외했다. 접근 제한은 Vercel Authentication의 All Deployments로 처리한다.

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

TanStack Query Provider와 실제 학습 API 연결을 5단계에서 구현했다. `/api/v1`은 Next.js 서버에서 백엔드로 전달하고, 조회와 변경은 자동 재시도하지 않는다. 문항별 답안 저장은 직렬화하고 실패 시 수동 재시도·서버 답안 복원을 제공한다. 전역 pnpm 실행기가 잘못된 설치 경로를 가리키는 환경에서는 `npx --yes pnpm@10.32.1 <명령>`으로 같은 버전을 실행한다.

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
- DB 연결 정보는 백엔드에서만 관리한다. 앱용 비밀번호와 쿠키 서명 키는 사용하지 않는다.
- 접근 제한은 배포 플랫폼이 담당한다. 현재 화면과 Python API를 한 Vercel 프로젝트에 배포했고 모든 배포 주소의 화면·API·이미지 접근 차단을 확인했다.
- Python 의존성은 프로젝트 전용 가상환경으로 분리한다.
- 백엔드 패키지 관리자는 uv다. `pyproject.toml`, `uv.lock`, `.venv/`로 선언·잠금·가상환경을 관리한다.

uv 프로젝트 초기화와 의존성 설치를 확인했다. 현재 `requires-python`은 `>=3.14`, `.python-version`은 `3.14`다. 2026-11-11에는 기존 SQLModel·psycopg·Alembic으로 DB 모델 7개·마이그레이션·샘플 입력을 구현했다. 로컬 PostgreSQL 16과 실제 Neon PostgreSQL 18.6에서 각각 전체 테스트 71개가 통과했고, Neon 앱 DB에 draft 샘플 8개를 입력·재입력했다. Python3.14 함수의 Vercel 배포와 실제 API·DB 동작도 확인했다.

## 4. 데이터베이스와 인증

- Neon PostgreSQL에 문제은행·풀이 기록을 저장한다.
- 본인 한 명만 쓰므로 사용자 테이블과 소유권 검사를 두지 않는다.
- 배포 접근 권한을 가진 본인만 문항·해설·이미지·풀이 기록을 볼 수 있다. 앱 인증 API는 구현하지 않는다.
- 교재 PDF·변환 데이터·문항 이미지는 공개 GitHub 저장소에 커밋하지 않는다.

## 5. 배포·테스트 계획

| 항목 | 현재 상태 |
|---|---|
| 배포 목적 | 모바일에서도 쓰기 위한 비공개 배포. 필수 |
| 프론트 배포 | Vercel Next.js, https://sqld-prc-study.vercel.app |
| 백엔드 배포 | 같은 Vercel 프로젝트의 Python3.14 FastAPI 함수. 별도 공개 백엔드 주소 없음 |
| 접근 제한 | Vercel Authentication + All Deployments 적용. 운영 고정 주소·개별 배포 주소의 비인증 접근 차단 확인. 임시 점검 키 폐기 완료 |
| 문항 이미지 저장 | Git 제외 원본에서 참조된 이미지만 Python 함수 번들에 포함하고 API로 제공. 직접 정적 경로는404 |
| DB 배포 | Neon 사용으로 결정. 무료 플랜으로 시작하는 방향이며 실제 한도는 사용 시 확인 |
| 백엔드 테스트 | 앱·변환·DB 입력·학습 API를 포함해 로컬 PostgreSQL 16과 실제 Neon PostgreSQL 18.6에서 각각 104개 통과. TEST_DATABASE_URL 없는 실행은 DB 통합 검증을 건너뜀 |
| 브라우저 테스트 | 기존17개 통과. 실제 클라우드·분리된 Neon 테스트 스키마에서 생성·저장·새로고침·채점·재풀이·이미지·종료·결과 확인. 실제 앱 DB는 읽기만 확인, 물리 휴대폰 확인은 대기 |

## 6. 프로젝트 구조와 진행 방식

```text
sqld-prc/
├─ frontend/                    # Next.js
├─ backend/                     # Python + FastAPI
├─ TECH_STACK.md
├─ 2026-10-28-database-design.md
├─ 2026-10-28-api-design.md
├─ 2026-10-28-openapi.json
└─ *.pdf                        # 교재 원본. Git 제외
```

초기 설정 이후 사용자가 승인한 단계별로 구현·검증한다. 4단계는 GitHub main에 업로드했고 5단계는 별도 개발 브랜치에서 작업했다. [5단계 결과](2026-11-11-phase5-learning-ui-report.md)에 화면·검증 범위와 남은 사용자 확인을 기록한다.

## 7. 관련 설계 문서

- [DB 설계안](2026-10-28-database-design.md)
- [API 명세](2026-10-28-api-design.md)
- [OpenAPI JSON](2026-10-28-openapi.json)
