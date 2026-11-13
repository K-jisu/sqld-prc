# SQLD Practice 백엔드

정리일: 2026-11-13. Python3.14·FastAPI·SQLModel·psycopg·Alembic을 사용하며 uv로 관리한다.

## 설치·실행

`backend/`에서 실행한다.

```bash
uv sync --locked
uv run --env-file .env --locked fastapi dev src/backend/main.py
```

시작 파일은 `src/backend/main.py`다. 로컬 문서는 http://127.0.0.1:8000/docs , 스키마는 http://127.0.0.1:8000/openapi.json 이다. API는 `/api/v1`이며 루트404는 별도 홈이 없어 정상이다.

`.env.example`을 기준으로 실제 `.env`를 별도 보관한다. `DATABASE_URL`, `APP_ORIGIN`, 필요 시 `QUESTION_ASSETS_DIR`을 설정한다. DB 엔진은 앱 시작 때 준비하고 요청별 트랜잭션을 응답 전에 완료한다. 시작 시 마이그레이션·문항 입력·테이블 생성은 하지 않는다.

## API와 기록

정확한 경로·필드는 [API 명세](../2026-10-28-api-design.md)와 [OpenAPI](../2026-10-28-openapi.json)를 따른다.

- `GET /catalog`: 과목·단원·문항 수.
- `GET /study-materials/{data-modeling|sql}`: DB 없이 교정·보충 PDF 제공. 기본 inline, `?download=true`는 attachment.
- `/study-sessions`, `/quiz-sessions`: 학습 생성·진행·위치·결과.
- `GET /quiz-sessions/{id}/items`: 전체 문항과 허용된 정답/해설, 그림 assets를 포함한 gzip JSON.
- `POST /study-sessions/{id}/progress`: 학습 기록 묶음 저장. 화면 판정은 응답을 기다리지 않는다.
- `/mock-sessions/{id}`, `/progress`, `/submit`, `/abandon`: 시험 생성·저장·제출·포기.
- `GET /me/stats`, `/me/wrong-answers`, `/me/mock-sessions`: 통계·오답·시험 이력.
- 개별 문항 조회·선택·서버 채점·재풀이는 호환용으로 유지한다.

학습에는 solution을 보내 로컬 채점하고 시험 진행 중에는 solution/review를 공개하지 않는다. 시험 제출/만료 후 review를 보낸다. 상태 변경은 동일한 APP_ORIGIN과 JSON을 요구하고, 보기/시도 소속·순번·세션 상태를 확인한다. 부모 세션 잠금과 생성 advisory lock을 사용하며 확정 답안은 덮어쓰지 않는다.

통계는 문항별 최신 유효 채점 하나다. 새 학습 draft는 이전 graded를 대체하지 않고, 시험은 완료 회차만 반영한다. timeout의 확정 시각은 고정 마감이며 미응답은 오답이다. 포기는 점수·정답을 공개하지 않는다.

## 문항 입력과 배포

운영 DB에는167문항·668보기가 이미 있다. 별도 데이터 변경 요청 없이 다시 입력하거나 초기화하지 않는다.

새 개발 DB에 필요한 명령은 다음과 같다.

```bash
uv run --env-file .env --locked alembic upgrade head
uv run --env-file .env --locked python -m backend.import_questions
```

입력은 `data/private/phase2/questions.json`과 `assets/`를 기본으로 하고 전체 파일이 없을 때만 samples.json을 사용한다. 다른 입력은 `--input`, `--assets`로 지정한다. 문항 키·보기 번호의 UUID와 기존 채점 이력을 유지하고, 참조 보기 삭제 등 오류 시 전체 트랜잭션을 취소한다.

원본에서 변환할 때는 `uv run --locked python scripts/prepare_samples.py` 후 `uv run --locked python scripts/prepare_bank.py`를 사용한다. 전자는 대표8개, 후자는 전체167개다. 교정·사용자 확인 기록과 이미지는 비공개 자료다.

모두 검수 대기이며 include_drafts=true로 포함할 수 있다. 자동 게시하지 않는다. 제외한9개와 입력 근거는 [전체 등록 보고서](../2026-11-11-full-question-bank-report.md)에 있다.

운영은 같은 Vercel 프로젝트의 Python 함수다. `scripts/prepare_vercel.py`가 코드·참조 그림·지정한 학습 PDF를 비공개 배포 폴더로 모은다. 로컬 기본 이미지 경로는 `data/private/phase2/assets`다. 실제 환경변수·교재·JSON·그림·백업을 공개 Git에 넣지 않는다.

학습 PDF는 `data/private/study-materials/data-modeling.pdf`, `sql.pdf` 두 파일이다. 필요하면 `STUDY_MATERIALS_DIR`로 위치를 바꾼다. 배포 준비 도구는 지정한 두 PDF도 함수 내부 `study-materials/`에 복사하고, 배포 진입점이 해당 경로를 설정한다. 자료 파일이 없으면 배포 준비를 중단한다. 공개 정적 경로나 Git에 PDF를 넣지 않는다.

## 개발 도구와 확인 상태

pytest는 개발 의존성이다. TEST_DATABASE_URL은 앱과 다른 DB/Neon 브랜치를 사용하고 각 테스트는 고유 임시 스키마를 만든다. 현재는 사용자 지시로 테스트·DB 검증을 실행하지 않는다. 일부 테스트는 이전 학습 정책 기준이다.

과거 [3단계](../2026-11-11-phase3-database-report.md)·[4단계](../2026-11-11-phase4-study-api-report.md) 결과를 최신 통합 검증으로 사용하지 않는다. 백업·복원 실습은 미확인이며 운영 데이터에 임의 실행하지 않는다. 잠금파일은 관리하고 .venv는 제외한다.
