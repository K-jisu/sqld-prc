# SQLD 개인 학습 앱 API 명세

작성일: 2026-10-28 / 수정일: 2026-11-04 — 공개 사이트 기준에서 혼자 쓰는 비공개 배포 기준으로 변경 / 버전: v1 설계 계약. 실제 서버에서 생성한 명세가 아니다.

- 사람용 문서: 이 파일.
- 기계용 계약: [OpenAPI 3.1 JSON](2026-10-28-openapi.json).
- 데이터 구조와 기본 요구사항: [DB 설계안](2026-10-28-database-design.md).
- 모바일·PC가 같은 API를 사용한다. 화면 디자인·배치는 별도 AI의 결과를 보고 사용자가 판단한다.
- 확정 요구사항과 구분되는 API 경로·필드명·오류 코드·인증 세부 방식은 작성자의 설계 결정이다.

## 1. 범위와 접근 방식

본인 한 명이 PC와 모바일에서 쓰는 비공개 앱이다. 비밀번호로 로그인한 뒤 학습·채점·해설·모의시험·결과·개인 통계·오답·시험 이력을 이용하고, 어느 기기에서든 같은 기록을 이어 푼다. 통계는 동일 문항의 최신 유효 채점 결과 한 건만 사용한다.

REST·JSON과 로그인 쿠키를 사용한다. 기존 FastAPI·관계형 DB 구조에 맞고, 화면 구성과 독립적인 데이터 계약을 만들 수 있기 때문이다. GraphQL, 브라우저 보관 Bearer 토큰, WebSocket은 현재 기능에 필요하지 않아 추가하지 않는다. 게스트·회원가입·소셜 로그인·SQL 실행기·관리자 화면·임의 PDF 업로드·AI 해설·결제 API도 이번 범위에 없다.

OpenAPI는 이 문서의 필드·형식·경로를 표현한다. DB의 전체 모델을 그대로 내보내지 않는다. JSON 스키마만으로 표현하기 어려운 마감·재전송·조건별 필드 공개 규칙은 이 문서와 작업별 description도 함께 적용한다.

## 2. 공통 계약

### 2.1 주소·인증·캐시

- 브라우저 기준 Base URL: `/api/v1`. 예: `GET /api/v1/catalog`.
- 프론트와 FastAPI를 별도 배포해도 브라우저는 프론트와 동일 출처의 이 경로를 사용한다. 배포 시 해당 경로를 FastAPI로 전달하고 Cookie·Set-Cookie를 보존한다. 실제 서비스 도메인은 배포 단계에서 정한다.
- 비밀번호는 백엔드 환경변수 `ACCESS_PASSWORD`에 둔다. 20자 이상의 무작위 값을 쓰고, 서버 시작 시 길이를 검사해 짧으면 시작하지 않는다. 비교는 상수 시간으로 한다.
- 로그인 요청 횟수 제한은 두지 않는다. 긴 무작위 비밀번호로 대입 공격을 막는 결정이다. 비정상 시도가 관찰되면 제한을 추가한다.
- `sqld_session` 쿠키: `SESSION_SECRET`으로 서명한 만료 시각 토큰, HttpOnly, 운영 Secure, SameSite=Lax, Path=/. 발급 후 30일 유효하다. DB에 저장하지 않는다.
- 로그아웃은 해당 브라우저의 쿠키를 지운다. 모든 기기의 로그인을 끊으려면 `SESSION_SECRET`을 바꾼다.
- `POST /auth/login`과 `POST /auth/logout`만 로그인 없이 호출할 수 있다. 다른 모든 API는 문항 이미지를 포함해 유효한 쿠키가 필요하며, 없거나 만료되면 401 LOGIN_REQUIRED다.
- 화면 코드와 정적 파일에는 교재 데이터를 넣지 않는다. 문항·해설·이미지는 로그인 후 API로만 받는다.
- JSON 응답은 모두 `Cache-Control: private, no-store`, 문항 이미지는 `private, max-age=3600`이다.
- 상태 변경 요청은 설정된 서비스 출처(`APP_ORIGIN`)와 일치하는 Origin을 요구한다. JSON 본문이 있는 작업은 application/json만 허용한다. 외부 Origin, 누락된 Origin, 허용하지 않은 Content-Type은 403.
- API는 점수·정답 여부를 클라이언트 입력으로 받지 않는다.
- 쿠키가 만료되면 프론트는 진행 중 저장을 멈추고 로그인 화면을 표시한다. 다시 로그인하면 서버 상태를 재조회해 저장되지 않은 선택을 사용자가 확인하게 한다. 실패한 저장을 자동으로 재전송하지 않는다.

### 2.2 형식

- ID: UUID 문자열. 과목·단원 ID: 양의 정수. 출제 순번·보기 번호·시도 순번은 1부터 시작한다.
- 시간: RFC 3339 UTC 문자열, 예: `2026-10-28T01:00:00Z`. 동적 성공 응답의 `server_now`는 서버 기준 시각이다.
- nullable은 JSON null로 보낸다. 배열은 없으면 []이며, 요청의 정의되지 않은 필드는 422로 거부한다.
- 요청의 과목·단원 배열은 중복을 금지하고 비교 전 정렬하여 정규화한다. 선택 과목·단원은 실제 범위에 존재해야 한다.
- 목록은 전체를 한 번에 반환한다. 문항과 기록이 적어 페이지네이션을 두지 않는다.
- 정확도는 `정답 문항 수 / 채점 문항 수 × 100`, 소수점 둘째 자리에서 반올림하여 소수 한 자리까지 반환한다. 분모가 0이면 0.0이다. 예: 2/3 → 66.7.
- OpenAPI에 포함된 문항·숫자·UUID·주소는 가상 예시다. 원문 변환 결과나 실제 데이터가 아니다.

### 2.3 오류 응답

모든 JSON 오류는 같은 구조다. FastAPI 기본 검증 오류도 이 구조로 변환한다. 서버 예외·SQL·비밀번호·쿠키 값을 노출하지 않는다.

```json
{
  "error": {
    "code": "ATTEMPT_NOT_CURRENT",
    "message": "이미 새 시도가 시작된 답안입니다. 현재 문항을 다시 확인해 주세요.",
    "request_id": "00000000-0000-4000-8000-0000000003e7",
    "details": {
      "current_attempt_id": "00000000-0000-4000-8000-000000000004"
    }
  }
}
```

`details`는 추가 정보가 없으면 {}. 필드 검증은 `{"fields":[{"path":"body.chapter_ids","reason":"존재하지 않는 단원"}]}` 형식이며 제출한 비밀 값을 되돌려 보내지 않는다.

| HTTP | code | 의미·프론트 처리 |
|---|---|---|
| 401 | INVALID_PASSWORD | 비밀번호 불일치. 입력 화면에 안내 |
| 401 | LOGIN_REQUIRED | 쿠키가 없거나 만료. 로그인 화면 표시 |
| 403 | ORIGIN_NOT_ALLOWED / CONTENT_TYPE_NOT_ALLOWED | 요청 출처·형식 거부. 자동 반복 금지 |
| 404 | RESOURCE_NOT_FOUND | 존재하지 않는 리소스 |
| 409 | CREATE_REQUEST_CONFLICT | 같은 생성 UUID에 다른 조건. 새 작업이면 새 UUID 사용 |
| 409 | ACTIVE_MOCK_EXISTS | 기존 시험을 이어 풀거나 명시적으로 포기. details.session_id |
| 409 | ATTEMPT_NOT_CURRENT / ANSWER_ALREADY_GRADED | 이전 시도 또는 채점 완료 답안 변경 시도. 현재 문항 재조회 |
| 409 | SESSION_CLOSED | 이미 종료·마감. details.session_status와 finish_reason을 확인하고 재조회 |
| 409 | MODE_MISMATCH | 학습 전용 작업을 모의시험에 요청하는 등 모드 불일치 |
| 409 | RESULT_NOT_READY / SESSION_ABANDONED | 아직 결과 없음 / 포기한 시험에는 결과·정답 공개 없음 |
| 409 | PREVIOUS_ATTEMPT_NOT_GRADED | 다시 풀기 전에 기존 시도 채점 필요 |
| 409 | QUESTION_UNAVAILABLE | 재학습 대상 문항이 draft로 돌아가 출제 불가. details.question_keys |
| 422 | VALIDATION_ERROR / INVALID_FILTER | 필드 오류·서로 맞지 않는 과목/단원 조합 |
| 422 | EMPTY_QUESTION_POOL | 선택 범위·현재 오답에 출제할 문제가 없음 |
| 422 | INVALID_OPTION / ANSWER_REQUIRED | 다른 문항의 보기 / 학습 채점 전에 선택 필요 |
| 503 | QUESTION_POOL_TOO_SMALL | 모의시험 10:40 배정 불가. details.required_by_subject, available_by_subject |
| 503 | SERVICE_UNAVAILABLE | 일시 장애. 기록을 초기화하지 않고 재시도 안내 |
| 500 | INTERNAL_ERROR | 예상하지 못한 서버 오류. request_id로 추적, 내부 내용 비공개 |

기본 500 및 기타 오류도 ErrorResponse를 사용한다.

## 3. 데이터 모델과 정답 공개

### 3.1 콘텐츠

`ContentBlock`은 아래 중 하나다. 배열 순서를 그대로 렌더링하며 SQL 줄바꿈을 보존한다.

```json
[
  { "type": "text", "text": "다음 SQL의 실행 결과를 고르시오." },
  { "type": "sql", "text": "SELECT 1;" },
  { "type": "image", "src": "/api/v1/question-assets/S1-Q001/diagram.webp", "alt": "관계도 예시" }
]
```

이미지 src는 로그인 쿠키를 확인하는 같은 출처의 API 경로다. 외부 URL·임의 HTML은 허용하지 않는다. 이미지 저장 위치는 비공개 배포 단계에서 정하되, `frontend/public` 같은 정적 공개 경로에는 두지 않는다.

`Question`에는 id, question_key, subject_id, chapter_id, source_number, type, content_blocks, options가 있다. `Option`에는 id, option_number, content_blocks만 있다. 원문 보기 순서를 유지하며 단일 선택 문항만 출제한다. 다른 유형은 원문 검수 후 설계를 보완한다.

### 3.2 답안과 공개 조건

`Attempt`: id, attempt_number, selected_option_id, status(draft/graded), graded_at. 정답 여부는 여기에 넣지 않는다.

`Review`: is_correct, correct_option_id, explanation_blocks. 조건을 충족한 때만 객체로 반환하고 그 외에는 null이다.

| 상황 | 반환할 시도 | review |
|---|---|---|
| 학습 진행 중, 현재 시도 미채점 | 현재 draft | null |
| 학습 문항 채점 완료 | 해당 graded | 공개 |
| 학습에서 다시 풀기 시작 | 새 draft | null |
| 종료한 학습 복습 | 마지막 graded, 없으면 마지막 draft | graded에만 공개 |
| 모의시험 진행 중 | draft | null |
| 모의시험 제출·시간 만료 완료 | 고정된 graded | 공개 |
| 모의시험 포기 | 남아 있는 draft | null |

실제 답안 채점 여부나 정답·해설은 Question/Option에 숨겨서 보내지 않는다. FastAPI는 응답 모델을 별도로 사용해 출력 필드를 제한한다. 프론트에서 가리는 방식으로 대신하지 않는다. [FastAPI 응답 모델](https://fastapi.tiangolo.com/tutorial/response-model/)

모의시험은 개인 통계·오답·네비게이터에도 제출 전 정오답을 반영하지 않는다. 별도 학습 세션에서 같은 문제의 해설을 보는 것까지 막지는 않는다.

### 3.3 풀이 상태

`Session`은 mode, status, current_position, item_count, answered_item_count, graded_item_count, started_at, deadline_at, finished_at, finish_reason, study_filter 등을 제공한다.

- active: 종료 시각·사유 null. mock에만 고정 deadline_at이 있다.
- completed: 학습 종료 또는 모의시험 제출/시간 만료. 과거 답안은 변경하지 않는다.
- abandoned: 마감 전 사용자가 명시적으로 포기한 mock만 해당. 정답·점수 없음.
- answered_item_count: 모의시험은 저장된 선택 수. 학습 active는 현재 시도 기준이며 completed는 최신 graded 우선, 없으면 draft 기준.
- graded_item_count: 학습은 한 번 이상 채점된 배정 문항 수, mock은 완료 전 0·완료 후 전체 수. 풀이 시도 횟수와 다르다.
- 학습 요약은 배정 문항별 마지막 graded 한 건을 사용한다. 새 draft가 이전 graded를 통계나 요약에서 지우지 않는다.
- current_position은 이어 풀기를 위한 위치일 뿐 저장 완료·채점을 의미하지 않는다.

## 4. 전체 API 목록

모든 경로는 /api/v1 기준. 로그인 없이 호출할 수 있는 것은 login과 logout뿐이다.

| Method | 경로 | 조건 | 성공 |
|---|---|---|---|
| POST | /auth/login | Origin 검증 | 200 AuthStatus |
| GET | /auth/me | 로그인 | 200 AuthStatus |
| POST | /auth/logout | Origin 검증 | 204 |
| GET | /catalog | 로그인 | 200 CatalogResponse |
| GET | /question-assets/{question_key}/{file_name} | 로그인 | 200 이미지 |
| PUT | /study-sessions/{session_id} | 로그인 | 201 / 재전송 200 |
| PUT | /mock-sessions/{session_id} | 로그인 | 201 / 재전송 200 |
| GET | /quiz-sessions | 로그인 | 200 ActiveSessionsResponse |
| GET | /quiz-sessions/{session_id} | 로그인 | 200 SessionResponse |
| PATCH | /quiz-sessions/{session_id} | 로그인, active | 200 SessionResponse |
| GET | /quiz-sessions/{session_id}/items/{item_id} | 로그인 | 200 ItemResponse |
| PATCH | /quiz-sessions/{session_id}/items/{item_id}/answer | 로그인, active draft | 200 ItemResponse |
| POST | /quiz-sessions/{session_id}/items/{item_id}/grade | 로그인, study | 200 GradeResponse |
| POST | /quiz-sessions/{session_id}/items/{item_id}/retry | 로그인, study | 201 / 재전송 200 |
| POST | /study-sessions/{session_id}/finish | 로그인, study | 200 ResultResponse |
| POST | /mock-sessions/{session_id}/submit | 로그인, mock | 200 ResultResponse |
| POST | /mock-sessions/{session_id}/abandon | 로그인, mock | 200 SessionResponse |
| GET | /quiz-sessions/{session_id}/result | 로그인, completed | 200 ResultResponse |
| GET | /me/stats | 로그인 | 200 StatsResponse |
| GET | /me/wrong-answers | 로그인 | 200 WrongAnswersResponse |
| GET | /me/mock-sessions | 로그인 | 200 MockHistoryResponse |

전체 요청·응답의 필드, 필수 여부, nullable, enum, 예시는 OpenAPI가 정의한다.

## 5. 생성·조회

### 5.1 학습 생성

`PUT /study-sessions/{session_id}`. 프론트가 새 작업마다 UUID를 한 번 생성하고 네트워크 재시도에도 같은 값을 사용한다. 학습 범위 요청은 아래 다섯 가지 중 하나다.

```json
{ "scope": "all" }
```

```json
{ "scope": "subjects", "subject_ids": [1] }
```

```json
{ "scope": "chapters", "chapter_ids": [1, 2] }
```

```json
{ "scope": "wrong_answers", "subject_ids": [1], "chapter_ids": [1] }
```

```json
{ "scope": "previous_session", "previous_session_id": "00000000-0000-4000-8000-000000000001" }
```

- wrong_answers의 두 필터 배열은 각각 생략 가능하며 함께 있으면 교집합이다. chapter가 subject 밖에 속하면 422 INVALID_FILTER. 다른 scope에 불필요한 필드를 넣으면 422.
- previous_session은 completed study/mock만 허용한다. 당시 고정된 문항 목록을 새 학습에 다시 배정한다. 문제은행 문항을 수정하지 않는다.
- 문제 순서는 과목 display_order → 단원 display_order → source_number → question_key다. 재학습도 이 책 순서를 사용한다. 모의시험의 과거 랜덤 순서를 학습에 그대로 적용하지 않는다.
- 오답 목록은 시작할 때 고정한다. 중간에 맞혔다고 현재 학습에서 문항이 사라지지 않는다.
- 출제 대상 중 published가 아닌 문항이 있으면 QUESTION_UNAVAILABLE로 알린다. 조용히 누락시키거나 다른 문제로 대체하지 않는다.
- 생성 트랜잭션에서 quiz_sessions, quiz_items, 각 문항의 attempt_number=1·선택 null인 draft를 함께 만든다. 빈 세션은 생성하지 않는다.

### 5.2 모의시험 생성

`PUT /mock-sessions/{session_id}`, 본문 `{}`.

- published 단일 선택 문항 중 1과목 10개·2과목 40개를 무작위 비복원 추출하고 전체 출제 순서도 섞어 저장한다. 같은 문항은 회차 안에서 한 번만 등장한다. 보기 순서는 원문대로다.
- 과목별 문항 부족이면 503 QUESTION_POOL_TOO_SMALL. 임의로 비율을 바꾸거나 중복 출제하지 않는다.
- 처음 성공한 DB 생성 시각이 started_at, deadline_at은 정확히 5,400초 뒤다. 클라이언트가 시각·시간·문항 수를 지정할 수 없다.
- active mock이 있으면 먼저 만료 판정을 한다. 유효 시간이 남았으면 ACTIVE_MOCK_EXISTS.
- 진행 중 mock을 하나로 제한하는 DB 부분 고유 인덱스가 두 기기의 동시 생성도 막는다. 인덱스 위반은 ACTIVE_MOCK_EXISTS로 변환한다.

### 5.3 생성 재전송과 목록

동일 UUID·동일 모드·동일 정규화 생성 조건이면 기존 리소스를 200으로 반환한다. 출제·마감·답안을 다시 만들지 않으며 이미 종료됐어도 기존 상태를 반환한다. 조건이 다르면 CREATE_REQUEST_CONFLICT. 재시도 비교는 저장된 study_filter와 mode를 사용하고 현재 오답 목록을 다시 추출해 비교하지 않는다.

`GET /quiz-sessions`: 진행 중 풀이 전체. mode 필터 지원. started_at DESC, id DESC. 기한 지난 mock을 먼저 완료시킨 뒤 목록에서 제외한다.

`GET /quiz-sessions/{id}`: 상태와 네비게이터 목록. 각 항목은 item_id·position·question_key·subject_id·chapter_id·answered·graded다. 본문·정답·해설은 포함하지 않는다.

`PATCH /quiz-sessions/{id}`: `{"current_position":3}`. active에서만 범위 내 위치를 저장한다. 여러 기기의 위치 변경은 서버 도착 순서로 마지막 값이 남는다.

`GET /quiz-sessions/{id}/items/{item_id}`: 문항 본문·보기·답안과 조건에 맞는 review를 반환한다. item은 반드시 URL의 session에 속해야 한다.

## 6. 답안 저장·채점·재풀이

### 6.1 보기 선택 저장

`PATCH /quiz-sessions/{session_id}/items/{item_id}/answer`

```json
{
  "attempt_id": "00000000-0000-4000-8000-000000000004",
  "selected_option_id": "00000000-0000-4000-8000-00000000000b"
}
```

selected_option_id=null이면 선택 해제다. active의 현재 draft만 변경할 수 있고 선택지는 해당 question_id 소속이어야 한다.

- 서로 다른 선택은 서버 도착 순서로 마지막 값이 남는다.
- 현재 선택과 같은 값을 재전송하면 쓰기 없이 현재 응답을 반환한다.
- 모의시험은 잠금 후 서버 시각으로 마감을 검사한다. 마감됐으면 저장을 적용하지 않고 timeout 채점 후 SESSION_CLOSED를 반환한다.
- graded 시도·과거 시도·종료 세션에는 선택 변경을 적용하지 않는다.

프론트는 문항별 저장을 직렬화한다. 빠르게 여러 보기를 누르면 최종 선택을 순서대로 저장한다. 저장 대기·실패 상태를 표시하고, 답안 저장 확인 전 정답 확인·제출을 실행하지 않는다. 화면 이동해도 이미 보낸 저장 요청을 임의 취소해서 저장 여부를 알 수 없게 만들지 않는다.

### 6.2 학습 문항 채점

`POST .../items/{item_id}/grade`

```json
{
  "attempt_id": "00000000-0000-4000-8000-000000000004"
}
```

저장된 선택으로 해당 문항 한 개만 채점한다. 선택이 없으면 ANSWER_REQUIRED. 아직 draft라면 현재 시도를 검사하여 graded로 확정한다. GradeResponse는 요청한 attempt와 review를 반환한다.

이미 graded인 동일 attempt의 재요청은 그 결과를 반환한다. 이후 다른 시도가 생겼어도 새 시도를 재채점하거나 이전 결과를 현재 UI에 강제로 덮지 않는다. 모의시험에는 이 API를 허용하지 않는다.

### 6.3 학습 문항 다시 풀기

`POST .../items/{item_id}/retry`

```json
{ "previous_attempt_id": "00000000-0000-4000-8000-000000000004" }
```

현재 graded 시도 다음 순번에 선택 null의 draft를 만든다. 첫 생성 201, 이미 해당 다음 시도가 존재하면 200으로 같은 시도를 반환한다. 이전 답안은 보존한다. 이전 시도가 미채점이면 PREVIOUS_ATTEMPT_NOT_GRADED.

재전송으로 받은 시도보다 더 최신 시도가 이미 있다면 프론트는 getQuizItem을 다시 조회한다. 현재 시도를 과거 응답으로 되돌리지 않는다. 종료 후에는 새 시도를 만들 수 없고, 이미 생성했던 시도의 읽기 성격 재전송만 허용한다.

### 6.4 학습 종료

`POST /study-sessions/{id}/finish`, 본문 `{}`.

active → completed/manual. 각 배정 문항의 최신 graded로 요약하며 미채점 문항을 오답 처리하지 않는다. 최신 시도가 draft여도 이전 graded가 있으면 그 결과를 사용한다. 종료 재요청은 기존 결과다. 마지막 문제를 채점한 것만으로 자동 종료하지 않는다. 종료 후 다시 학습은 새 UUID로 생성한다.

## 7. 모의시험 제출·마감·포기

### 7.1 수동 제출

프론트는 저장 대기 요청을 완료한 뒤 응답 현황을 다시 읽는다. 미응답 수를 표시하고 사용자가 제출을 확인하면 요청한다.

`POST /mock-sessions/{id}/submit`, 본문 `{}`.

quiz_session 잠금 후 모든 문항을 한 트랜잭션에서 채점하고 completed/manual로 종료한다. 미응답도 is_correct=false·graded_at이 있는 답안으로 확정한다.

재제출은 기존 결과를 반환한다. 이미 abandoned면 SESSION_ABANDONED. 마감이 도달했으면 timeout 채점 결과를 반환한다.

### 7.2 마감과 동시 요청

답안 변경·채점·재시도·종료·포기는 quiz_session을 공통 잠금 대상으로 사용한다. 답안 저장과 제출이 경쟁할 때 먼저 확정된 부모 상태에 따라 한 번만 처리한다.

서버의 실제 현재 시각으로 잠금 획득 후 마감을 확인한다. PostgreSQL 트랜잭션 시작 시각이나 브라우저 시각만으로 판정하지 않는다. 저장과 마감 확인을 같은 트랜잭션에서 처리한다.

타임아웃은 브라우저 타이머·상시 서버 프로세스·실행 중 메모리에 의존하지 않는다. 세션·문항·결과·내 통계·시험 이력 조회, 저장/제출/포기에서 기한 지난 active mock을 발견하면 확정한다. 읽기 API의 만료 정리는 이미 도달한 결과를 물리화하는 내부 처리이며 임의 제출·포기는 GET으로 하지 않는다.

timeout의 finished_at과 각 답안 graded_at은 deadline_at, updated_at은 실제 처리 시각이다. 며칠 뒤 발견한 과거 시험이 이후 공부 결과보다 최신 이력으로 집계되지 않는다. 한 트랜잭션에서 전체 결과를 확정하므로 일부 채점 상태는 노출하지 않는다.

### 7.3 명시적인 포기

`POST /mock-sessions/{id}/abandon`, 본문 `{}`.

포기 확인 후 마감 전 active만 abandoned로 종료한다. 점수·정답·해설은 공개하지 않고 개인 정답 통계에서도 제외한다. deadline을 이미 지났으면 completed/timeout을 반환한다. 이미 종료된 상태는 그대로 반환한다.

창 닫기·이동·백그라운드 진입·로그아웃을 포기로 해석하지 않는다. 새 시험을 만들기 위해 기존 시험을 자동 포기시키지도 않는다.

### 7.4 결과

`GET /quiz-sessions/{id}/result`.

- 학습: item_count, graded_item_count, correct_item_count, incorrect_item_count, ungraded_item_count, accuracy_percent.
- 모의시험: 50문항, 응답·미응답·정답·오답 수, 총점·최대점·정답률, 과목별 점수·과락 여부, passed.
- 정답당 2점. 총점≥60, 1과목≥8/20, 2과목≥32/80일 때 passed=true.
- 결과의 items는 배정 순서이며 outcome에 당시 선택·정답 보기 ID·정오답·채점 시각을 담는다. 미채점 학습 문항의 outcome은 null이다.
- 본문·해설은 개별 item 조회로 읽는다.
- active 미마감은 RESULT_NOT_READY. abandoned는 SESSION_ABANDONED로 정답을 공개하지 않는다.
- 이후 다른 학습의 결과가 바뀌어도 과거 회차 점수는 바뀌지 않는다.

## 8. 로그인

`POST /auth/login`

```json
{ "password": "example-only-not-a-real-password" }
```

일치하면 `sqld_session` 쿠키를 발급하고 AuthStatus(server_now, authenticated, expires_at)를 반환한다. 불일치는 401 INVALID_PASSWORD이며 그 밖의 정보를 주지 않는다. 비밀번호를 로그에 남기지 않는다.

`GET /auth/me`는 쿠키가 유효하면 AuthStatus, 아니면 401 LOGIN_REQUIRED를 반환한다.

`POST /auth/logout`은 본문 없이 쿠키를 지우고 204를 반환한다. 서버의 풀이 기록은 보존하고 프론트는 TanStack Query 캐시를 비운 뒤 로그인 화면으로 이동한다.

## 9. 개인 통계·오답·시험 이력

- GET /me/stats: 문항별 가장 최근 유효 채점 결과로 전체 및 과목별 Counts를 반환한다. graded_question_count=correct_question_count+wrong_question_count.
- 학습은 문항 채점 즉시, mock은 completed 이후만 포함한다. 새 draft·포기한 시험은 제외한다. unanswered mock도 채점 문항·오답에 포함한다.
- 최신 순서는 graded_at DESC, answer_attempts.id DESC. 재시도 때문에 문항 수를 늘리지 않는다.
- GET /me/wrong-answers?subject_id=1&chapter_id=1: last_graded_at DESC, question_key ASC. 필터는 교집합이고 서로 안 맞으면 INVALID_FILTER. draft로 되돌린 문항은 available=false다.
- available=false인 문항은 복습 생성에서 QUESTION_UNAVAILABLE로 알린다. 역사적 채점 결과를 지우지는 않는다.
- GET /me/mock-sessions?status=completed: finished_at DESC, id DESC. status 생략 시 completed·abandoned. abandoned는 summary=null이다.

## 10. 프론트 연결 지침

API 명세는 페이지 수·배치·색상·PC/모바일의 화면 구성을 강제하지 않는다. 화면 AI는 아래 데이터 흐름과 상태를 지키면서 디자인한다.

1. 최초 접속: auth/me. 401이면 로그인 화면, 성공하면 catalog와 quiz-sessions.
2. 학습 시작: 새 UUID로 PUT study → session에서 첫 item ID → GET item.
3. 보기 선택: 문항별 저장 큐 → PATCH answer → 응답 반영. 저장 중·실패를 구분한다.
4. 정답 확인: 저장 완료 → POST grade → 해당 attempt일 때 review 표시.
5. 다시 풀기: POST retry → GET item으로 현재 시도 확인.
6. 시험 시작: 새 UUID로 PUT mock. 브라우저가 받은 server_now와 deadline_at으로 남은 시간을 표시하고 포커스 복귀·재접속 때 서버에 재확인한다.
7. 시험 제출: 저장 완료 → 최신 현황·미응답 확인 → POST submit → 결과.
8. 기기 전환: 포커스 복귀 때 조회를 다시 실행해 다른 기기에서 저장한 답안을 반영한다.
9. API 실패 시 저장됐다고 표시하지 않는다. 오프라인 답안 큐·자동 재로그인·무한 재시도는 이번 범위에 넣지 않는다. 마지막 서버 확인 상태와 아직 저장되지 않은 선택을 구분한다.
10. 어느 API든 401 LOGIN_REQUIRED를 받으면 캐시를 비우고 로그인 화면으로 이동한다.

TanStack Query는 조회 캐시, mutation은 생성·저장·채점·종료를 담당한다. 생성·채점 mutation의 재시도를 하더라도 동일 리소스 UUID·attempt ID를 사용한다. 정답·해설은 허용 시점 전 캐시에 넣지 않는다.

## 11. DB 대응과 검증 기준

### 11.1 DB 대응

[DB 설계안](2026-10-28-database-design.md)의 7개 테이블을 사용한다. 로그인 상태는 서명 쿠키에만 있으므로 DB 테이블이 필요 없다.

별도 idempotency 테이블은 추가하지 않는다. 생성은 quiz_session UUID, grade는 attempt ID, retry는 이전 시도+다음 attempt_number, submit/finish는 세션 종료 상태로 재전송을 처리한다. 기존 유니크 제약과 트랜잭션을 함께 사용한다.

### 11.2 구현 완료 시 확인할 시나리오

1. 쿠키 없이 login·logout을 뺀 모든 API와 문항 이미지를 요청하면 401이다.
2. 만료되거나 서명이 틀린 쿠키는 거부되고, 틀린 비밀번호는 쿠키를 발급하지 않는다.
3. 외부 Origin의 상태 변경 요청은 403이다.
4. 모든 제출 전 mock 응답과 캐시에 정답 보기 ID·해설·정오답이 없다.
5. 같은 생성 UUID를 여러 번 전송해도 문제·시도·마감이 하나이고 조건 변경은 거부된다.
6. 두 생성 UUID의 동시 mock 생성은 active 하나만 성공한다.
7. grade/retry/submit/finish 재전송으로 결과·시도·통계가 중복 증가하지 않는다.
8. 저장·제출·포기와 마감이 경쟁해도 결과는 한 번만 확정된다.
9. 창 닫기 후 만료된 mock이 재조회·통계 조회에서 deadline_at 기준으로 반영된다.
10. 같은 문항 정답→오답→정답에 따라 최신 통계·오답이 바뀌고 과거 시험 점수는 유지된다.
11. 문항을 수정해 다시 입력해도 풀이 기록과 과거 시험 점수가 유지된다.
12. 모바일·PC에서 동일 계약으로 로그인·저장·시험 제출이 가능하고, 한쪽에서 풀던 세션을 다른 쪽에서 이어 풀 수 있다.
13. 예외·DB 오류에 비밀번호·쿠키 값·SQL이 포함되지 않는다.

### 11.3 현재 확인 범위와 남은 사항

이 작업은 API 문서와 정적 OpenAPI 작성이다. 실제 FastAPI 서버·DB·브라우저 통합 테스트를 대신하지 않는다.

2026-11-04 수정 후 정적 점검 결과: 21개 작업·50개 스키마의 참조와 경로 파라미터가 맞고, OpenAPI 요청/응답 예제 20개가 스키마의 필수·허용 필드와 타입에 맞는다. 자체 검사 스크립트 결과이며 정식 OpenAPI 규격 검증기나 실행 서버 검증 결과가 아니다.

로그인 유지 30일은 작성자 제안값이다. 실제 배포 도메인·프록시 설정·문항 이미지 저장 위치는 비공개 배포 단계에서 확정한다.

원문 전수 문항·정답 대응·단일 선택 외 유형은 검수 전이다. 다른 유형이 있으면 선택/정답 입력 스키마를 데이터 입력 전에 보완한다.
