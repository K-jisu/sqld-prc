# SQLD 개인 학습 앱 DB 설계안

작성일: 2026-10-28 / 수정일: 2026-11-13. 기존 7개 테이블·제약조건을 유지하며 현재 학습·시험 흐름에 맞춰 설명을 정리했다. 정확한 요청·응답은 [API 명세](2026-10-28-api-design.md)를 따른다. 날짜별 검증 결과는 당시 코드의 이력이며 최신 변경은 사용자 지시로 별도 검증하지 않았다.

## 1. 목적과 확정된 요구사항

- Next.js App Router + TypeScript + Tailwind CSS + TanStack Query, FastAPI + SQLModel + psycopg, Neon PostgreSQL을 사용한다. DB 변경 이력은 Alembic으로 관리한다.
- 본인 한 명이 PC와 모바일에서 쓰는 비공개 앱이다. 앱 로그인 없이 Vercel Authentication의 All Deployments로 접근을 제한한다. 서버에 저장된 기록을 다른 기기에서 이어 푼다. 최초 배포 보호 확인은 별도 배포 보고서의 이력이다.
- 사용자가 한 명이므로 사용자 테이블과 소유자 필드를 두지 않는다. DB의 모든 풀이 기록이 곧 내 기록이다.
- 정답 문항 수와 오답 목록은 문항별 최신 유효 채점 결과로 계산한다. 같은 문항을 반복해서 맞혀도 한 문항이며, 이후 틀리면 정답 문항 수에서 빼고 오답 목록에 넣는다.
- 학습 모드는 선택한 과목·단원의 문제를 책 순서대로 풀고 브라우저에서 개별·일괄 채점한다. 문항·정답·해설·그림을 처음에 함께 받고 기록은 모아 저장한다. 명시적으로 다시 풀기를 선택하면 새 답안 시도를 만든다.
- 모의시험은 1과목 10개 + 2과목 40개, 총 50개를 회차 내 중복 없이 추출한다. 보기 순서는 원문을 유지한다. 90분 뒤 또는 수동 제출 시 일괄 채점한다.
- 모의시험은 정답당 2점이다. 총점 60점 이상이고 1과목 8점/20점 이상, 2과목 32점/80점 이상이면 합격이다. 미응답은 오답이다.
- 시험 시작 시 저장한 종료 시각은 접근 재확인, 새로고침, 창 닫기, 재접속으로 연장되지 않는다.
- 문제의 본문·SQL·보기·정답·해설은 제공 PDF 변환 자료를 사용하며 표·ERD는 이미지로 보존한다. 현재 1과목 50개·2과목 117개, 총 167개·668보기다. 원본이 없는 II-61~64·69~70·79~81은 제외했다. 전체 원문 최종 확인은 사용자가 풀면서 진행한다.
- 교재 PDF·변환 데이터·문항 이미지는 Git에 포함하지 않는다. GitHub 저장소가 공개 상태이기 때문이다.
- 모바일·PC를 지원하며 밝고 차분한 학습 노트 화면을 사용한다. 이 문서는 DB 제약과 상태 전이를 설명한다.

## 2. 접근 방식과 제안 기본값

문제은행, 출제 목록, 답안 시도를 분리하는 관계형 구조를 권장한다. 단원·선택지·응시 기록의 연결을 외래키로 검증하고, 같은 문제를 다시 풀어도 과거 채점 결과를 보존한다.

정답 수나 오답 목록을 별도 원본 테이블로 중복 저장하지 않는다. 유효한 채점 이력에서 조회해 계산한다. 현재 규모에서는 별도의 통계 캐시, 이벤트 시스템, 범용 콘텐츠 관리 시스템을 도입하지 않는다.

아래는 사용자 확정 사항과 구분되는 설계 제안이다.

- 첫 버전 입력은 원문 검수로 확인한 단일 선택 객관식을 기준으로 한다. 한 문항에서 고르는 답은 하나다. 실제 자료에 복수 선택 등 다른 유형이 발견되면 임의로 단일 선택으로 바꾸거나 누락시키지 않고, 데이터 입력 전에 이 설계를 보완한다.
- 문항별 선택지의 수와 번호는 원본에서 검증한다. DB가 임의로 선택지 내용을 생성하지 않는다.
- 앱 비밀번호·로그인 쿠키·접속 세션 테이블은 두지 않는다. 접근 권한은 배포 플랫폼에서 확인한다.
- 진행 중 학습 세션은 여러 개를 허용하고, 진행 중 모의시험은 하나만 허용한다.

## 3. 테이블 관계

총 7개 테이블이다.

```mermaid
erDiagram
    subjects ||--o{ chapters : contains
    chapters ||--o{ questions : contains
    questions ||--o{ question_options : has
    quiz_sessions ||--o{ quiz_items : assigns
    questions ||--o{ quiz_items : used_by
    quiz_items ||--o{ answer_attempts : records
    question_options o|--o{ answer_attempts : selected
```

모든 시간 필드는 `timestamptz`를 사용하고, API는 UTC 시각과 오프셋을 명시한 ISO 8601 문자열을 반환한다. 화면에서 사용자 시간대로 표시한다. 풀이·문항 배정·답안 시도 ID는 UUID를 사용한다. 과목·단원은 고정 정수 ID, 문항과 선택지는 UUID로 통일한다.

### 3.1 subjects — 과목

| 필드 | 형식 | 의미 |
|---|---|---|
| id | smallint, PK | 과목 ID |
| name | text | 과목명 |
| display_order | smallint, UNIQUE | 표시 순서 |

초기 데이터는 데이터 모델링의 이해 / SQL 기본 및 활용 두 과목이다. 시험의 10:40 출제 비율과 2점 배점은 별도 시험 유형 관리 기능 없이 백엔드의 고정 시험 규칙으로 관리한다.

### 3.2 chapters — 단원

| 필드 | 형식 | 의미 |
|---|---|---|
| id | smallint, PK | 단원 ID |
| subject_id | smallint, FK subjects | 소속 과목 |
| name | text | 원문 단원명 |
| display_order | smallint | 과목 내 순서 |

`UNIQUE(subject_id, display_order)`로 단원 순서 중복을 막는다. 문항의 과목은 단원에서 구하므로 questions에 subject_id를 중복 저장하지 않는다.

### 3.3 questions — 문항

| 필드 | 형식 | 의미 |
|---|---|---|
| id | uuid, PK | 문항 ID |
| question_key | text, UNIQUE | 문항의 고정 키. 예: S1-Q001 |
| chapter_id | smallint, FK chapters | 소속 단원 |
| source_number | integer | 책에 표시된 문항 번호 |
| content_blocks | jsonb | 본문·SQL·이미지 블록의 순서 있는 배열 |
| explanation_blocks | jsonb | 원문 해설 블록. 학습 solution에 포함, 시험은 제출/만료 후 공개 |
| question_page_start / question_page_end | integer | 문제 PDF의 실제 1-based 페이지 범위 |
| answer_page_start / answer_page_end | integer | 해설 PDF의 실제 1-based 페이지 범위 |
| status | text | draft / published |
| created_at / updated_at | timestamptz | 생성·변경 시각 |

양수 페이지 범위 및 시작≤끝을 검증한다. status는 검수 여부다. 새 출제는 published가 기본이며 사용자가 include_drafts=true를 명시하면 draft도 포함한다. 검수 상태를 자동 변경하지 않는다.

문항 오타는 같은 행을 수정한다. 별도 버전 행을 만들지 않는다. 입력 절차는 question_key로 기존 행을 찾아 갱신하므로 다시 실행해도 문항이 늘어나지 않고 답안 기록의 참조가 유지된다.

2026-11-11 입력 규칙: 내용이 같은 draft 재입력은 기존 published 상태를 보존한다. 게시 후 내용이 달라진 미검수 입력은 거부하여 다시 검수하도록 한다. 사용자 결정으로 추가 원본이 없는 II-61~64·69~70·79~81은 입력·출제 대상에서 제외한다. 현재 167문항은 모두 draft이며 운영 DB에 입력돼 있다. 별도 데이터 변경 요청 없이 재입력하지 않는다.

- 채점 결과는 answer_attempts.is_correct에 저장되므로 문항이나 정답을 고쳐도 과거 시험 점수는 바뀌지 않는다.
- 과거 시험을 다시 볼 때는 수정된 문장과 현재 정답·해설이 보인다. 혼자 쓰는 앱에서는 오타가 고쳐진 쪽이 낫다고 판단했다.
- 정답을 고친 문항의 통계는 다시 풀어 채점할 때 바로잡힌다.
- 이미 답안에서 참조하는 선택지는 삭제할 수 없다. 입력 절차가 오류로 알리고 사용자가 판단한다.

이미지는 파일 경로/객체 키만 기록한다. 경로에 문항 키를 포함한다. 이미지·PDF 바이너리와 임의 HTML을 DB 본문에 넣지 않는다. 블록은 최소한 다음 세 유형을 사용하고 FastAPI와 프론트가 같은 규격을 따른다.

```json
[
  { "type": "text", "text": "문제 본문" },
  { "type": "sql", "text": "SELECT ...\nFROM ..." },
  { "type": "image", "src": "/api/v1/question-assets/S1-Q001/diagram.webp", "alt": "문항에 제시된 관계도" }
]
```

이미지도 교재 데이터이므로 `frontend/public` 같은 정적 공개 경로에 두지 않는다. 원본 블록에는 보호된 API 경로를 기록하고 전체 문항 응답의 assets에 그림 데이터를 함께 보낸다. 로컬 파일은 `data/private/phase2/assets`, 배포 파일은 비공개 준비 폴더에 두며 Git에 포함하지 않는다.

### 3.4 question_options — 선택지

| 필드 | 형식 | 의미 |
|---|---|---|
| id | uuid, PK | 선택지 ID |
| question_id | uuid, FK questions | 소속 문항 |
| option_number | smallint | 원본 보기 번호 및 순서 |
| content_blocks | jsonb | 보기의 텍스트·SQL·이미지 |
| is_correct | boolean | 정답 여부. 학습에는 정답 보기 ID 제공, 시험 진행 중에는 제외 |

`UNIQUE(question_id, option_number)`와 `UNIQUE(id, question_id)`를 둔다. 단일정답 검수 완료 문항은 is_correct=true가 정확히 하나여야 한다. 부분 고유 인덱스로 문항별 정답을 최대 하나로 제한하고, 정확히 하나 존재하는지와 원문 보기 수·번호는 입력 트랜잭션에서 검증한다.

### 3.5 quiz_sessions — 한 번의 학습 또는 모의시험

| 필드 | 형식 | 의미 |
|---|---|---|
| id | uuid, PK | 풀이 세션 ID |
| mode | text | study / mock |
| study_filter | jsonb, nullable | 학습 시작 시 과목·단원·오답 필터. 검증된 입력만 저장 |
| status | text | active / completed / abandoned |
| current_position | integer | 현재 보고 있는 출제 순번 |
| started_at | timestamptz | 시작 시각 |
| deadline_at | timestamptz, nullable | 모의시험의 고정 종료 시각 |
| finished_at | timestamptz, nullable | 실제 의미의 종료 시각. 시간 만료는 deadline_at |
| finish_reason | text, nullable | manual / timeout / abandoned |
| created_at / updated_at | timestamptz | 생성·변경 시각 |

mode와 상태 값, current_position≥1, mock은 deadline_at 필수·study는 NULL을 CHECK로 검증한다. active는 finished_at·finish_reason이 모두 NULL, completed는 finished_at과 manual/timeout 사유가 필수, abandoned는 mock에만 허용하며 finished_at과 abandoned 사유가 필수다. timeout은 mock에만 허용한다. current_position의 실제 출제 개수 범위와 과목별 배정은 API에서 검증한다. 출제 목록이 비어 있으면 세션을 생성하지 않는다.

`mode='mock' AND status='active'`에 대한 부분 고유 인덱스로 진행 중 모의시험을 하나만 허용한다. 두 기기에서 동시에 시작해도 시험이 둘 생기지 않는다.

모의시험 총점·과목별 정답 수·정답률은 고정된 quiz_items와 각 문항의 확정 답안 하나에서 계산한다. 학습 세션 요약은 quiz_item별 최신 채점 완료 시도 하나로 계산한다. 재시도 중인 미채점 답안은 기존 채점 이력을 대체하지 않는다. 다른 곳의 카운터를 증가시키는 방식은 사용하지 않는다. 채점 완료 답안이 바뀌지 않으므로 과거 시험 점수도 유지된다.

### 3.6 quiz_items — 이 세션에 배정된 문항

| 필드 | 형식 | 의미 |
|---|---|---|
| id | uuid, PK | 배정 문항 ID |
| quiz_session_id | uuid, FK quiz_sessions | 소속 풀이 세션 |
| question_id | uuid, FK questions | 배정된 문항 |
| position | integer | 세션에서의 출제 순번 |

`UNIQUE(quiz_session_id, position)`, `UNIQUE(quiz_session_id, question_id)`, `UNIQUE(id, question_id)`를 둔다.

시험 생성 시 50개 문항과 순서를 한 번 저장한다. 재조회·접근 재확인·새로고침 때 다시 추첨하지 않는다. 학습의 책 순서 목록과 오답 복습 대상도 시작 시 이 테이블에 고정한다. 학습 중 정오답이 변해도 현재 목록이 갑자기 줄거나 순서가 바뀌지 않는다.

### 3.7 answer_attempts — 문항별 답안 시도

| 필드 | 형식 | 의미 |
|---|---|---|
| id | uuid, PK | 한 번의 답안 시도 ID |
| quiz_item_id | uuid | 배정 문항 |
| question_id | uuid | 배정된 문항. 복합 외래키 검증을 위한 값 |
| attempt_number | integer | 같은 배정 문항의 시도 순번. 1부터 증가 |
| selected_option_id | uuid, nullable | 선택한 보기. 미응답이면 NULL |
| is_correct | boolean, nullable | 채점 전 NULL, 채점 후 서버 판정 |
| graded_at | timestamptz, nullable | 결과가 효력을 갖는 시각 |
| created_at / updated_at | timestamptz | 실제 생성·변경 시각 |

필수 제약은 다음과 같다.

- `(quiz_item_id, question_id)` → quiz_items의 `(id, question_id)` 복합 외래키.
- `(selected_option_id, question_id)` → question_options의 `(id, question_id)` 복합 외래키. 다른 문제의 보기를 제출할 수 없다.
- `UNIQUE(quiz_item_id, attempt_number)`, attempt_number>0.
- graded_at이 NULL이면 is_correct도 NULL, graded_at이 있으면 is_correct는 필수.
- graded_at이 NULL인 행에 대한 quiz_item_id 부분 고유 인덱스로 현재 작성 중인 시도를 최대 하나만 허용한다.

학습 선택·채점·재풀이는 브라우저에서 즉시 반영하고 묶음 전송한다. 서버는 소속·순번·상태를 확인하고 graded=true인 기록의 정오답과 채점 시각을 확정한다. 채점 완료 답안은 수정하지 않는다. 다시 풀기는 다음 attempt_number로 새 행을 만든다. 같은 확정 내용을 재전송해도 중복 기록을 만들지 않는다.

모의시험은 각 quiz_item에 attempt_number=1만 사용한다. 제출 전에는 선택만 변경하며 is_correct·graded_at은 NULL이다. 전체 제출 시 모든 출제 문항에 대해 답안을 확정하고, 미응답도 is_correct=false로 채점한다. 제출 후 답안 변경과 개별 재채점은 허용하지 않는다. 결과 복습에서 다시 풀려면 새 학습 세션을 만든다.

## 4. 핵심 처리 흐름

### 4.0 모드별 상태 전이

| 모드·현재 상태 | 동작 | 결과 |
|---|---|---|
| study / active | 보기 선택·문항 채점·문항 다시 풀기 | active 유지 |
| study / active | 사용자가 학습 종료 선택 | completed / manual. 미채점 답안은 점수에 포함하지 않음 |
| study / completed | 다시 학습·오답 복습 선택 | 기존 세션은 보존하고 새 study 세션 생성 |
| mock / active | 마감 전 수동 제출 | completed / manual |
| mock / active | 종료 시각 도달 | completed / timeout |
| mock / active | 마감 전 명시적인 시험 포기 확인 | abandoned / abandoned. 점수·정답·해설 공개 없이 종료 |
| mock / completed 또는 abandoned | 답안 변경·재채점·재개 | 거부. 기존 결과는 유지하고 새 시험만 생성 가능 |

학습은 마지막 문항을 채점했다고 자동으로 다른 화면으로 이동하거나 종료하지 않는다. 해설을 읽고 다시 풀 수 있게 active를 유지하고, 사용자가 학습 종료를 선택하면 요약으로 이동한다. 종료 후에는 원래 세션 답안을 바꾸지 않는다. 같은 범위로 다시 학습하면 당시 목록의 문항을 새 세션에 배정하며, 오답 복습은 현재 오답 목록으로 새 세션을 만든다.

학습 화면에서 종료하면 선택한 답안을 로컬 일괄 채점하고 기록 전송 후 finish를 호출한다. finish API 자체는 저장된 최신 graded를 요약하며 미응답·미채점 답안을 새로 채점하지 않는다.

창 닫기·화면 이동·다른 기기 접속만으로 mock을 포기 처리하지 않는다. 새 모의시험을 시작할 때 기존 active 시험이 있으면 계속 풀기 또는 명시적인 포기를 선택하게 한다. 포기 요청 시 이미 마감됐으면 abandoned로 바꾸지 않고 timeout 채점을 완료한다. 기한이 지나기 전 사용자가 명시적으로 포기한 시험만 자동 채점 대상에서 제외한다.

### 4.1 모의시험 저장·제출·시간 만료

- 모든 답안 변경과 제출은 동일한 부모 quiz_session 상태를 확인하고 일관된 순서로 잠근다. active인 동안만 답안을 바꿀 수 있다.
- 답안 변경은 서버 도착 순서대로 마지막 값이 남는다. 프론트는 기록을 모아 순서대로 전송하고 저장 중 생긴 새 변경을 보존한다. 시험 기록에는 attempt_number=1, graded=false만 허용한다.
- 마감 판정은 서버 시각을 사용하며, 잠금 대기 후에도 마감 여부를 다시 확인한다. 브라우저 시각이나 클라이언트가 전달한 점수를 신뢰하지 않는다.
- 제출은 한 트랜잭션에서 답안을 채점하고 quiz_session을 종료한다. 재제출은 기존 결과를 반환한다. 일부만 채점된 시험은 완료로 노출하지 않는다.
- 만료된 시험을 늦게 열었을 때도 자동 채점한다. 타이머와 정답 판정을 서버 프로세스 메모리나 백그라운드 타이머에 의존시키지 않는다.
- 시간 만료 시 finished_at과 답안의 graded_at은 deadline_at을 사용하고, updated_at은 실제 처리 시각을 남긴다. 며칠 뒤 자동 정리된 오래된 시험이 최근 학습 결과를 덮지 않게 한다.
- 시험 목록·통계를 조회할 때에는 기한 지난 active 시험을 먼저 확정한다.

### 4.2 오답·정답 통계

- 채점 완료된 유효 답안만 사용한다.
- 학습은 채점 기록이 서버에 저장된 뒤 통계에 반영하고, 모의시험은 전체 종료 이후 반영한다. 진행·포기 시험의 임시 답안은 통계에 포함하지 않는다.
- 문항별로 graded_at DESC, answer_attempts.id DESC의 결정적인 순서를 사용한다. 재시도 횟수 때문에 문항 수가 늘어나지 않는다.
- 사용자 확정 기준: 가장 최근의 유효 결과가 오답이면 오답 목록, 정답이면 정답 문항으로 계산한다. 작성 중 답안이나 접속 동작만으로 통계가 바뀌지 않는다.
- '정답 문항 수'와 '채점 문항 수'를 구분해 표시한다. 모의시험 미응답도 오답으로 판정되므로 채점 문항 수에 포함한다. 정답률은 정답 문항 수 / 채점 문항 수이며, 분모가 0이면 0%로 표시한다.
- 이번 회차의 점수와 문항별 최신 통계는 다른 지표다. 과거 시험 80점은 이후 복습으로 달라지지 않는다.

### 4.3 접근 제한·데이터 보호

- 앱 로그인·로그아웃 API와 앱용 비밀번호·쿠키 서명 키는 제외한다.
- Vercel Authentication의 All Deployments로 화면·API·이미지와 백엔드 직접 주소 모두를 보호한다. 프론트만 보호하고 별도 API 주소를 공개하지 않는다.
- 이 보호는 운영에 적용돼 있다. 최초 비인증 접근 차단 확인은 [비공개 배포 보고서](2026-11-11-private-deployment-report.md)의 당시 이력이며 이번 문서 정리에서 다시 확인하지 않았다.
- 참조된 문항의 삭제는 제한한다. 풀이 세션 삭제 시 그 세션의 quiz_items와 answer_attempts만 함께 삭제한다.

## 5. 화면 및 API 데이터 계약

URL·응답 스키마는 [API 명세](2026-10-28-api-design.md)와 현재 라우트 정의에서 생성한 [OpenAPI 파일](2026-10-28-openapi.json)을 따른다. 앱 로그인 화면은 만들지 않는다.

| 화면/동작 | 필요한 데이터 | 표시 조건 |
|---|---|---|
| 시작 화면 | 과목·단원·검수 상태별 문항 수, 진행 중 풀이 | 항상 |
| 문제풀이 | quiz_session ID·상태·현재 순번·deadline_at, 전체 quiz_item·본문·보기·선택 답안·그림 | 처음 일괄 수신 |
| 학습 채점 | solution의 정답 보기·해설, 로컬 선택 결과 | 처음 수신하되 채점 후 화면에 표시 |
| 모의시험 진행 | 출제 순번과 응답 여부, 선택 답안 | 제출 전 정답·해설·is_correct 제외 |
| 이번 시험 결과 | 총점·과목별 점수·합격/과락·문항별 결과와 해설 | 종료된 풀이 |
| 내 기록 | 정답 문항 수·채점 문항 수·정답률·오답 목록·시험 이력 | 항상 |

DB 모델 전체를 그대로 JSON 직렬화하지 않는다. 학습에는 로컬 채점용 solution을 보내고 시험 진행 중에는 solution·review를 보내지 않는다. 시험 제출/만료 전에 정답·해설이 브라우저 캐시에 들어가지 않게 한다.

## 6. 인덱스·검증·운영

초기 인덱스는 각 PK/UNIQUE 인덱스와 아래 접근 경로로 제한한다.

- questions: 출제 문항 조회용 `(chapter_id, source_number)`.
- quiz_sessions: `(started_at DESC)`, 진행 중 모의시험 부분 고유 인덱스, 미종료 모의시험의 deadline_at.
- quiz_items: `(quiz_session_id, position)`, question_id.
- answer_attempts: `(quiz_item_id, attempt_number DESC)`, question_id 및 graded_at, 작성 중 답안 부분 고유 인덱스.

가져오기 시 고정 문항 키·과목별 개수·선택지 번호·정답 수·이미지 파일 존재·원문 페이지 범위를 검사한다. 문제·보기·정답·해설을 원본과 대조하며, 검증되지 않은 문항을 published로 만들지 않는다.

앱 데이터는 Neon DB 하나에 두고, 테스트는 Neon의 별도 브랜치 또는 로컬 임시 PostgreSQL에서 실행해 내 풀이 기록을 지우지 않는다. DB 연결 정보는 FastAPI 환경변수에만 둔다. 스키마 변경은 요청마다 실행하지 않고 Alembic 마이그레이션 단계로 적용한다. 스키마 변경 전에 풀이 기록을 내보내 백업한다.

## 7. 설계 당시 확인 시나리오

아래는 설계 시 작성한 확인 항목이며 최신 코드의 통과 목록이 아니다. 현재는 사용자 지시로 실행하지 않는다.

1. 배포 후 비인증 브라우저가 화면·API·문항 이미지와 백엔드 직접 주소에 접근하면 플랫폼에서 거부된다.
2. 다른 문항의 선택지를 제출하면 DB 외래키 또는 API 검증에서 거부한다.
3. 학습에서 한 문항만 채점되고 다른 문항의 선택 상태는 유지된다. 재채점 요청은 같은 결과를 반환하며, 다시 풀기는 새 시도를 만든다.
4. 모의시험은 50개/10:40/문항 중복 없음/순서 고정을 만족한다. 제출 전 정답·해설이 API와 프론트 캐시에 없다.
5. 수동 제출, 자동 시간 만료, 저장 요청이 겹쳐도 시험은 한 번만 종료되며 종료 후 답안은 바뀌지 않는다.
6. 두 기기에서 동시에 모의시험을 시작해도 진행 중 시험은 하나만 생긴다.
7. 마감 후 늦게 처리한 과거 시험이 최근 학습의 정오답 상태를 역전시키지 않는다.
8. 문항을 수정해 다시 입력해도 문항이 중복되지 않고 풀이 기록과 과거 시험 점수가 유지된다.
9. 답안 저장 실패는 화면에 표시되고, 오래된 저장이 새 선택을 덮지 않는다.
10. PC에서 풀던 세션을 모바일에서 이어 풀 수 있다.
11. 학습 종료 전에는 마지막 문항도 다시 풀 수 있다. 종료 후에는 새 학습 세션을 만들며 기존 요약은 바뀌지 않는다. 모의시험 화면을 닫거나 교체하는 것만으로 시간 만료 채점을 피할 수 없다. 마감 후 포기 요청도 시간 만료 결과를 반환한다.

## 8. 현재 상태와 과거 확인 이력

- 앱 인증은 제외했고 Vercel 보호를 적용해 배포했다. 실제 기기 간 전체 흐름과 백업·복원 실습은 미확인이다.
- 운영 문제은행은 draft 167문항·668보기다. 전체 원문 문구·정답·SQL·그림 대조는 사용자가 풀면서 진행한다.
- 최신 학습·모의고사·기록 변경은 배포 빌드만 통과했으며 테스트·lint·브라우저/API/DB 확인은 사용자 지시로 생략했다.
- 과거 이력: 2026-11-11 로컬 임시 PostgreSQL 16과 실제 Neon PostgreSQL 18.6에서 초기 마이그레이션·제약조건·재입력/과거 답안 보존을 검증했다. 각각 당시 전체 테스트 71개가 통과했고 Neon 앱 DB에 draft 샘플 8개를 입력했다. 당시에는 배포 전이었으며 이후 전체 문항 입력·비공개 배포·기능 통합을 진행했다. 이 결과를 최신 코드의 검증으로 사용하지 않는다.

## 참고한 공식 문서

- [PostgreSQL 제약조건](https://www.postgresql.org/docs/current/ddl-constraints.html)
- [PostgreSQL 부분 인덱스](https://www.postgresql.org/docs/current/indexes-partial.html)
- [PostgreSQL 행 잠금](https://www.postgresql.org/docs/current/explicit-locking.html)
- [PostgreSQL 날짜·시간](https://www.postgresql.org/docs/current/datatype-datetime.html)
- [Neon 개발 브랜치](https://neon.com/docs/introduction/branching)
