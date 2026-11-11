# SQLD Practice Frontend

Next.js App Router + React + TypeScript 프론트입니다. Tailwind CSS와 TanStack Query로 범위 선택·이어 풀기·문제풀이·결과 화면을 구현했습니다. 밝고 차분한 학습 노트 스타일이며 PC와 모바일에 맞춰 배치합니다.

## 설치·실행

`frontend/`에서 실행합니다. 패키지 관리자는 `package.json`의 `packageManager`에 고정된 pnpm 10.32.1입니다.

```bash
pnpm install --frozen-lockfile
pnpm dev
```

http://localhost:3000 에서 학습 화면을 확인합니다. 실제 백엔드도 별도 터미널에서 실행해야 합니다. [백엔드 실행 방법](../backend/README.md)을 참고합니다.

전역 pnpm 실행기가 다른 설치 경로를 가리켜 실행되지 않으면 프로젝트 버전을 직접 지정합니다.

```bash
npx --yes pnpm@10.32.1 install --frozen-lockfile
npx --yes pnpm@10.32.1 dev
```

`npx`는 지정 버전 pnpm을 실행하는 역할이고 패키지·잠금파일은 pnpm으로 관리합니다. npm install을 혼용하지 않습니다.

## 정적 검사와 빌드

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

- lint: ESLint 검사
- typecheck: `next typegen`으로 라우트 타입을 생성한 뒤 `tsc --noEmit` 검사
- test: Playwright로 합성 HTTP 응답을 사용하는 학습 화면 회귀 테스트
- build: Next.js 프로덕션 빌드

전역 실행기 문제가 있는 환경에서는 위 명령도 `npx --yes pnpm@10.32.1 lint`처럼 실행합니다.

빌드 후 프로덕션 실행은 다음과 같습니다.

```bash
pnpm start
```

Geist·Geist Mono는 Next.js가 자체 제공하는 글꼴 파일로 서비스합니다. 최초 빌드 때 글꼴 다운로드에 네트워크가 필요할 수 있습니다.

## 브라우저 테스트

테스트는 전용 개발 서버 `127.0.0.1:3210`을 띄우고 종료합니다. 기존 서버를 재사용하지 않으므로 해당 포트를 비워 둡니다. Windows에서는 설치된 Microsoft Edge를 사용하고, 다른 환경에서는 `pnpm exec playwright install chromium`으로 브라우저를 설치합니다.

HTTP 응답은 `tests/api-fixture.ts`의 직접 만든 예제입니다. 실제 교재·DB 접속정보를 사용하지 않으며 Neon에 풀이 기록을 만들지 않습니다. 저장 순서·이전 응답·실패 후 복구·새로고침·채점/재풀이·종료/결과·다른 기기의 채점·접근 확인 HTML·모바일·키보드 조작을 검증합니다. trace와 결과는 Git에서 제외한 `data/private/phase5-browser-results/`에 저장합니다.

실제 백엔드와 PostgreSQL을 통한 별도 검증은 [5단계 결과](../2026-11-11-phase5-learning-ui-report.md)에 구분해 기록합니다. 화면 테스트만으로 실제 DB 연결이나 배포 접근 제한을 검증했다고 보지 않습니다.

## 환경변수

`.env.example`의 `BACKEND_API_URL`은 Next.js 서버가 `/api/v1/*` 요청을 전달할 백엔드 주소입니다. 기본값은 `http://127.0.0.1:8000`입니다. 다른 주소를 쓰려면 `.env.local`에 설정하고 개발 서버를 재시작하거나 다시 빌드합니다. 실제 환경변수 파일은 Git에서 제외합니다.

백엔드 `APP_ORIGIN`은 브라우저가 사용하는 프론트 주소(로컬 기본 `http://localhost:3000`)와 일치해야 합니다. 브라우저는 동일 출처 `/api/v1`로만 요청하며 DB 접속정보는 백엔드에만 둡니다. 교재 문항·이미지는 `public/`이나 화면 코드에 넣지 않고 API로만 받습니다. 앱 로그인 화면은 없습니다. 운영에서는 배포 플랫폼의 접근 제한을 별도로 적용합니다.

## 학습하기

현재 전체167문항(1과목50·2과목117)은 검수 대기 상태입니다. 홈에서 `검수 대기 문항 포함`을 선택하면 풀 수 있고 검수 완료로 자동 변경되지는 않습니다. 기존8문항 학습은 그대로 남으므로 전체 문항을 풀려면 새 학습을 시작합니다.

선택은 자동 저장합니다. `저장 중`에는 이동·채점·종료를 막고, 실패하면 `다시 저장` 또는 `서버 답안 다시 확인`으로 복구합니다. 정답 확인 뒤 해설이 표시되고 다시 풀어도 이전 채점은 보존합니다. 마지막 문항까지 푼 뒤에도 `학습 종료`를 직접 눌러 결과를 확인합니다.

모의시험·통계는 후속 단계입니다. 운영은 [비공개 학습 앱](https://sqld-prc-study.vercel.app)에 배포했고, Vercel에서는 같은 프로젝트의 Python 함수로 API를 전달합니다. [배포 결과](../2026-11-11-private-deployment-report.md)와 [작업 체크리스트](../WORK_CHECKLIST.md)를 참고합니다.
