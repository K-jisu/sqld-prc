# SQLD Practice Frontend

Next.js App Router + React + TypeScript 프론트입니다. Tailwind CSS로 스타일을 작성하고 TanStack Query는 API 연결 단계에서 사용합니다.

## 설치·실행

`frontend/`에서 실행합니다. 패키지 관리자는 `package.json`의 `packageManager`에 고정된 pnpm 10.32.1입니다.

```bash
pnpm install --frozen-lockfile
pnpm dev
```

http://localhost:3000 에서 기본 화면을 확인합니다.

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
pnpm build
```

- lint: ESLint 검사
- typecheck: `next typegen`으로 라우트 타입을 생성한 뒤 `tsc --noEmit` 검사
- build: Next.js 프로덕션 빌드

전역 실행기 문제가 있는 환경에서는 위 명령도 `npx --yes pnpm@10.32.1 lint`처럼 실행합니다.

빌드 후 프로덕션 실행은 다음과 같습니다.

```bash
pnpm start
```

기본 템플릿의 Google Font는 최초 빌드 때 네트워크 다운로드가 필요할 수 있습니다.

## 환경변수

`.env.example`에는 서버에서 사용할 백엔드 주소 이름과 로컬 예시를 기록합니다. 실제 `.env.local` 등은 Git에서 제외합니다. 백엔드 연결·같은 출처 API 전달은 화면 연동 단계에서 구현합니다.

`NEXT_PUBLIC_` 접두사가 붙은 값은 브라우저에 노출되므로 DB 접속 정보나 카카오 비밀을 넣지 않습니다.

## 다음 구현 단계

현재 기본 템플릿을 유지합니다. TanStack Query Provider, API 호출, 로그인 및 문제풀이 화면은 각 기능 단계에서 연결합니다. 전체 순서는 [작업 체크리스트](../WORK_CHECKLIST.md)를 참고합니다.
