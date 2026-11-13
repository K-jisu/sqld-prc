# SQLD Practice 기술 구성

정리일: 2026-11-13. 버전은 저장소 선언 기준이며 실제 해석 버전은 잠금파일을 따른다.

## 구성

| 영역 | 사용 기술 | 역할 |
|---|---|---|
| 화면 | Next.js App Router·React·TypeScript | 학습·시험·기록 |
| 스타일 | Tailwind CSS4·전역 CSS | 밝고 차분한 학습 노트·반응형 배치 |
| 서버 상태 | TanStack Query5 | 캐시·변경 요청·저장 상태 |
| 로컬 상태 | React·메모리·localStorage | 즉시 채점·그림·미전송 기록 |
| API | Python3.14·FastAPI·Pydantic | 요청·응답과 트랜잭션 |
| DB 접근 | SQLModel·SQLAlchemy·psycopg3 | 모델·조회·잠금 |
| DB/마이그레이션 | Neon PostgreSQL·Alembic | 문제은행·풀이 이력·기존7개 테이블 |
| 배포 | Vercel Next.js + Python 함수 | 한 프로젝트에서 화면·API 제공 |
| 접근 보호 | Vercel Authentication + All Deployments | 앱 인증 없이 본인 접근 제한 |
| 의존성 관리 | pnpm·uv | 선언·잠금파일·전용 가상환경 |

앱 비밀번호·카카오 OAuth·사용자 테이블은 사용하지 않는다.

## 선언 버전

| 프론트 | 선언 |
|---|---|
| Next.js | 16.4.4 |
| React / React DOM | 19.3.0 |
| TypeScript / Tailwind CSS | ^5 / ^4 |
| TanStack Query | ^5.105.3 |
| pnpm | 10.32.1 |

| 백엔드 | 선언 |
|---|---|
| Python | >=3.14 |
| FastAPI standard | >=0.162.0 |
| SQLModel | >=0.0.48 |
| psycopg binary | >=3.3.7 |
| Alembic | >=1.20.1 |

잠금파일은 `frontend/pnpm-lock.yaml`, `backend/uv.lock`이다. 패키지 관리자를 혼용하지 않는다.

## 현재 데이터 흐름

일반 학습은 문항·정답·해설·그림을 일괄 수신하고 캐시에 유지한다. 그림 데이터까지 포함한 JSON은 gzip으로 전송한다. 선택·채점·재풀이는 로컬 반영, 기록은1초 묶음 전송이다. 종료는 전송 후 확정하며 탭 복귀/재연결 자동 재조회는 하지 않는다.

시험은 문항을 일괄 수신하고 선택을 바로 반영하되 제출 전 정답·해설을 보내지 않는다. 서버 고정 마감·부모 세션 잠금·일괄 채점으로 종료한다. 시험의 포커스/재연결 마감 확인은 유지한다.

통계는 문항별 최신 확정 답안, 시험 점수는 해당 회차 답안으로 계산한다. 상세 계약은 [API 명세](2026-10-28-api-design.md)를 따른다.

## 배포·확인 상태

운영은 https://sqld-prc-study.vercel.app 이다. 브라우저는 동일 출처 `/api/v1`을 사용하고 별도 공개 백엔드는 두지 않는다. `scripts/prepare_vercel.py`가 코드와 참조 그림만 비공개 폴더로 모은다. 교재·문항 JSON·이미지·접속정보·백업은 Git에 넣지 않는다.

주요 기능은 구현·배포됐으며 최신 배포 빌드만 통과했다. 사용자 요청에 따라 별도 테스트·lint·브라우저/API/DB 확인은 실행하지 않았다. pytest·Playwright는 남아 있으나 일부 테스트는 이전 정책 기준이다. 과거 실행 결과는 날짜별 보고서에만 적용한다.
