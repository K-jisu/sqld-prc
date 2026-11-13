# SQLD 개인 학습 앱 API 명세

현재 구현 기준: 2026-11-13. 파일명 날짜는 최초 설계일이다.
정확한 필드 스키마는 [OpenAPI JSON](2026-10-28-openapi.json)과 `backend/src/backend/api_schemas.py`를 따른다.

## 공통 규칙

본인 한 명의 비공개 앱이다. 앱 인증 API·사용자별 소유권 검사는 없으며 Vercel Authentication + All Deployments로 화면·API·이미지를 보호한다.

기준 경로는 `/api/v1`이다. 상태 변경은 APP_ORIGIN과 같은 Origin 및 application/json을 요구한다. ID는 UUID, 시각은 타임존 포함 ISO8601, 콘텐츠는 text/sql/image 블록이다. 정의하지 않은 입력 필드는 거부한다.

응답은 개인 데이터이며 공개 CDN 캐시로 취급하지 않는다. 전체 문항 응답은 그림 assets를 포함한 gzip JSON이다. 접근 확인 HTML을 JSON 저장 성공으로 취급하지 않는다.

오류는 error.code·message·request_id·details다. 주요 상태는403(출처/형식),404(리소스),409(상태/충돌),422(입력),503(서비스/문항 부족)이다.

## 경로

| Method | 경로 | 역할 |
|---|---|---|
| GET | /catalog | 과목·단원·검수 상태별 문항 수 |
| GET | /study-materials/{material_id} | 지정한 학습 PDF 열기, download=true면 첨부 다운로드 |
| PUT | /study-sessions/{session_id} | 학습 생성, 최초201·동일 재전송200 |
| GET | /quiz-sessions | 진행 목록, 선택적 mode=study/mock |
| GET | /quiz-sessions/{session_id} | 세션·고정 목록·응답 현황 |
| PATCH | /quiz-sessions/{session_id} | 현재 위치 저장 |
| GET | /quiz-sessions/{session_id}/items | 전체 문항·답안·허용 해설·그림 |
| GET | /quiz-sessions/{session_id}/items/{item_id} | 개별 문항, 호환용 |
| PATCH | /quiz-sessions/{session_id}/items/{item_id}/answer | 개별 선택/해제, 호환용 |
| POST | /quiz-sessions/{session_id}/items/{item_id}/grade | 학습 서버 채점, 호환용 |
| POST | /quiz-sessions/{session_id}/items/{item_id}/retry | 학습 새 시도, 호환용 |
| POST | /study-sessions/{session_id}/progress | 학습 기록 묶음 저장 |
| POST | /study-sessions/{session_id}/finish | 학습 종료·결과 |
| GET | /quiz-sessions/{session_id}/result | 완료한 풀이 결과 |
| PUT | /mock-sessions/{session_id} | 시험 생성, 최초201·재전송200 |
| POST | /mock-sessions/{session_id}/progress | 미채점 선택 묶음 저장 |
| POST | /mock-sessions/{session_id}/submit | 시험 일괄 채점·결과 |
| POST | /mock-sessions/{session_id}/abandon | 명시적 시험 포기 |
| GET | /me/stats | 전체·과목·단원 통계 |
| GET | /me/wrong-answers | 필터별 최신 오답 |
| GET | /me/mock-sessions | 완료·포기 시험 이력 |
| GET | /question-assets/{question_key}/{file_name} | 참조 그림의 호환 제공 경로 |

## 학습 생성·조회

학습 자료의 material_id는 data-modeling·sql만 허용한다. 응답은 application/pdf이며 기본 Content-Disposition은 inline, download=true는 attachment다. 파일은 비공개 자료 폴더에서 제공하고 private, no-store를 적용한다. 자료 조회에는 DB가 필요하지 않으며 Vercel의 기존 접근 보호를 유지한다. 다른 ID나 없는 파일은404다.

scope는 all, subjects(subject_ids), chapters(chapter_ids), previous_session(previous_session_id), wrong_answers(선택적 subject_ids·chapter_ids)다. 이전 풀이 목록은 완료 상태만 허용한다.

include_drafts 기본은 false다. 현재167개는 모두 검수 대기이므로 사용자가 true를 명시해야 포함한다. 과목·단원 ID와 소속을 확인하고 문항은 과목·단원·원문 번호 순으로 고정한다.

같은 생성 ID·정규화 조건이면 기존 풀이를 반환한다. 조건이 다르면 CREATE_REQUEST_CONFLICT다. 같은 ID로 출제나 마감을 다시 만들지 않는다.

세션은 mode, status, current_position, item_count, answered_item_count, graded_item_count, started_at, deadline_at, finished_at, finish_reason, study_filter를 가진다.

전체 문항 응답은 server_now·session_id·session_status·items·assets다. assets는 참조 이미지 URL과 data URL의 사전이다. 서버는 허용된 참조 파일만 읽고 브라우저가 이후 이동에 재사용한다.

## 로컬 채점·기록 저장

일반 학습 item은 본문·보기·attempt·review와 solution을 포함한다. solution은 correct_option_id·explanation_blocks다. 미채점 review는 null이지만 학습용 solution은 처음부터 보낸다. 시험에는 이 정책을 적용하지 않는다.

선택·개별/일괄 채점·재풀이를 화면에서 즉시 반영한다. 탭 복귀/재연결로 학습 문항을 자동 재조회하지 않고 다른 기기 변경은 새로고침으로 반영한다. 미전송 기록은 localStorage에도 보관하고1초 뒤 모아서 전송한다.

`POST /study-sessions/{session_id}/progress` 본문:

```json
{
  "answers": [
    {
      "item_id": "00000000-0000-4000-8000-000000000001",
      "attempt_id": "00000000-0000-4000-8000-000000000002",
      "attempt_number": 1,
      "selected_option_id": "00000000-0000-4000-8000-000000000003",
      "graded": true
    }
  ]
}
```

서버는 문항·보기·시도 소속과 순번·상태를 확인해 한 트랜잭션으로 저장한다. graded=true면 저장 기록의 정오답·시각을 확정하지만 화면 판정은 응답을 기다리지 않는다. 확정 답안은 변경하지 않고 재풀이는 다음 순번의 새 시도다. 동일 확정 내용 재전송은 중복 기록을 만들지 않는다.

응답은 server_now·saved_attempt_ids다. 브라우저는 이전 성공 응답이 더 최신 변경을 지우지 않도록 변경 ID를 비교한다. 실패는 표시하고 미전송 상태를 보존한다.

학습 화면의 종료는 선택한 답안을 로컬 일괄 채점하고 기록 전송 후 finish를 호출한다. finish API 자체는 저장된 최신 graded를 요약하며 미채점 선택을 새로 채점하지 않는다. 미채점은 오답에 넣지 않고 새 draft가 있어도 이전 graded는 유지한다.

개별 answer/grade/retry는 호환용이다. 학습 전용 작업을 시험에 요청하면 MODE_MISMATCH다.

## 모의고사

생성 본문은 `{"include_drafts":false}`이며 필드를 생략할 수 있다. true로 검수 대기도 포함할 수 있으나 검수 상태는 바꾸지 않는다.

- 1과목10개·2과목40개를 비복원 추출하고 전체 순서를 섞어 저장한다. 보기는 원문 순서다.
- 부족하면503 QUESTION_POOL_TOO_SMALL이며 비율 변경·중복 출제하지 않는다.
- 시작은 서버 생성 시각, 마감은 정확히5,400초 뒤다. 클라이언트가 시간·문항 수를 지정하지 않는다.
- 진행 중 시험은 하나다. 기존 시험의 마감을 확인하고 유효하면 ACTIVE_MOCK_EXISTS다.
- 같은 생성 ID·조건의 재전송은 원래 출제·마감·상태를 반환한다.

진행 중 solution·review는 null이고 본문·보기 그림만 포함한다. progress는 같은 answers 형식이지만 attempt_number=1, graded=false만 허용한다.

제출은 기록 전송 후 submit을 호출한다. 서버가 부모 세션을 잠그고 마감을 확인해50개를 일괄 채점한다. 미응답은 오답이다. 재제출은 같은 확정 결과를 반환한다.

조회·저장·제출·포기에서 기한 지난 active 시험을 발견하면 timeout으로 확정한다. 창을 닫아도 마감은 늘어나지 않는다. 마감 후 저장은 반영하지 않고 SESSION_CLOSED를 반환하며 시간 만료 결과를 유지한다. timeout의 finished_at·graded_at은 deadline_at이다.

포기는 마감 전 active만 abandoned로 종료한다. 점수·정답·해설을 공개하지 않는다. 이미 마감됐다면 timeout 결과를 반환한다. 화면 이동이나 창 닫기를 자동 포기로 해석하지 않는다.

정답당2점, 총100점이다. 총점60점 이상이며 1과목8/20점·2과목32/80점 이상이면 합격이다. 결과에는 응답·미응답·정답·오답·총점·과목 점수·과락·passed가 있다. 확정 뒤 문항 조회는 review를 반환한다.

## 개인 기록

stats는 overall·subjects·chapters를 반환한다. 각 집계는 total_question_count, graded_question_count, correct_question_count, wrong_question_count, ungraded_question_count, accuracy_percent다.

최신 유효 결과는 문항별 graded_at DESC, attempt ID DESC의 첫 결과다. 학습 graded와 completed 시험만 포함한다. 새 draft·진행/포기 시험은 제외하고 완료 시험 미응답은 오답이다.

wrong-answers의 subject_id·chapter_id는 교집합 필터다. 존재하지 않거나 소속이 맞지 않으면 INVALID_FILTER다. 최신 오답을 채점 시각 내림차순·문항 키 오름차순으로 반환한다. available은 현재 published 여부이며 검수 대기를 복습하려면 생성에 include_drafts=true를 명시한다.

mock-sessions는 completed·abandoned를 종료 시각·ID 내림차순으로 반환한다. status로 제한할 수 있다. 각 항목은 session·summary이며 포기의 summary는 null이다. 다른 학습이 과거 시험 점수를 바꾸지 않는다.

## 데이터·확인 상태

기존7개 테이블과 제약, 부모 세션 잠금, 생성 advisory lock을 사용한다. revision·문항 버전·별도 idempotency 테이블은 추가하지 않았다. 현재 정답·해설은 교정된 문제은행을 따르지만 확정 답안·과거 점수는 덮어쓰지 않는다.

문항·이미지·접속정보는 공개 Git에 넣지 않는다. OpenAPI 문서 추출은 서버/DB/API 동작 검증이 아니다. 최신 기능의 별도 검증은 사용자 요청으로 생략했고 배포 빌드만 통과했다.
