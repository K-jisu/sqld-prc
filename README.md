# SQLD Practice

정리일: 2026-11-13.

교재 기반 SQLD 문제풀이·모의고사를 혼자 사용하는 비공개 학습 앱입니다.

[운영 앱](https://sqld-prc-study.vercel.app) · [작업 상태](WORK_CHECKLIST.md) · [다음 세션 안내](HANDOFF.md)

## 사용하기

본인 Vercel 계정으로 접근을 확인한 뒤 사용합니다. 앱 자체 로그인·로그아웃은 없습니다.

- **학습:** 전체·과목·단원별 범위, 이어풀기, 즉시/일괄 채점, 해설, 재풀이, 결과 복습.
- **모의고사:** 50문항(1과목10·2과목40), 90분, 제출/만료 채점, 포기, 점수·합격/과락, 해설.
- **내 기록:** 전체·과목·단원 통계, 필터별 오답 다시 풀기, 지난 시험 결과.
- **학습 자료:** 홈의 메뉴에서 모델링 11쪽·SQL 24쪽 교정·보충 PDF를 새 탭으로 열거나 내려받기.

문제은행은 **167문항·668보기**입니다. 1과목50개·2과목117개이며 모두 검수 대기입니다. 학습의 `검수 대기 문항 포함`, 시험의 `미검수 문항도 출제`를 선택합니다. 검수 상태는 자동 변경하지 않습니다. 기존8문항 학습은 보존되므로 전체 범위는 새 학습으로 시작합니다.

일반 학습은 문제·정답·해설·그림을 처음에 함께 받아 유지하고 선택·채점·이동을 바로 반영합니다. 기록은 모아 저장하며 종료 전에 전송합니다. 탭 복귀/재연결로 전체 문제를 자동 재조회하지 않습니다. 다른 기기 변경은 새로고침하면 반영됩니다.

시험은 문항을 한 번에 받고 선택은 즉시 반영하지만 정답·해설은 제출/만료 후 공개합니다. 마감과 채점은 서버 기준입니다.

## 개발 실행

각 프로젝트를 별도 터미널에서 실행합니다.

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

```bash
cd backend
uv sync --locked
uv run --env-file .env --locked fastapi dev src/backend/main.py
```

프론트는 http://localhost:3000 , 백엔드 문서는 http://127.0.0.1:8000/docs 입니다. `.env.example`을 참고하고 백엔드 `APP_ORIGIN`을 브라우저 출처와 맞춥니다. 프론트의 서버 전용 `BACKEND_API_URL` 기본값은 http://127.0.0.1:8000 입니다.

pnpm 실행기가 잘못 연결됐다면 `npx --yes pnpm@10.32.1 <명령>`을 사용합니다. npm install과 혼용하지 않습니다.

## 문서

| 문서 | 용도 |
|---|---|
| [작업 상태](WORK_CHECKLIST.md) | 구현·배포와 미확인 사항 |
| [인계 안내](HANDOFF.md) | 브랜치·핵심 파일·사용자 지시 |
| [기술 구성](TECH_STACK.md) | 현재 스택과 선언 버전 |
| [프론트](frontend/README.md) / [백엔드](backend/README.md) | 실행·설정·저장 방식 |
| [API 명세](2026-10-28-api-design.md) / [OpenAPI](2026-10-28-openapi.json) | 현재 요청·응답 계약 |
| [DB 설계](2026-10-28-database-design.md) | 테이블·키·제약조건 |
| [제품](PRODUCT.md) / [화면](DESIGN.md) | 개인 학습 목적·학습 노트 디자인 |

## 비공개 자료와 확인 상태

화면·API·이미지는 한 Vercel 프로젝트의 Authentication + All Deployments로 보호합니다. 운영 DB에는167문항이 이미 있으므로 다시 입력할 필요가 없습니다.

교재 PDF·ZIP·변환 JSON·문항 이미지·실제 `.env`·백업은 Git에 없습니다. 집에서 로컬 연동/재배포하려면 개인 경로로 별도 전달해야 합니다. 미전송 기록은 해당 브라우저 localStorage에 있으며 서버 저장 후 다른 기기와 공유됩니다.

학습 자료 PDF는 `data/private/study-materials/data-modeling.pdf`, `sql.pdf`에 따로 보관합니다. 배포 준비 도구가 두 파일만 Python 함수의 비공개 폴더로 복사합니다. `/materials` 목록과 `/api/v1/study-materials/{data-modeling|sql}`은 기존 Vercel 접근 보호를 사용하며 공개 정적 폴더에는 PDF를 넣지 않습니다.

주요 기능은 구현·배포됐습니다. 사용자 요청에 따라 최신 변경의 테스트·lint·브라우저/API/DB 확인은 실행하지 않았고 배포 빌드만 통과했습니다. 원문 최종 검수와 백업·복원 실습은 미확인입니다.

날짜별 보고서는 당시 이력입니다. 과거 테스트 결과를 최신 코드의 검증 결과로 사용하지 않습니다.

- [전체167문항 등록](2026-11-11-full-question-bank-report.md)
- [최초 비공개 배포](2026-11-11-private-deployment-report.md)
- [모의고사·기록 통합](2026-11-12-finish-study-app-plan.md)
- [학습 재로딩 수정](2026-11-13-learning-preload-fix.md)
- [학습 자료 PDF 추가](2026-11-13-study-materials-report.md)
