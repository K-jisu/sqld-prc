# 휴대폰 문제풀이용 비공개 배포 결과

작성일: 2026-11-11.

접속 주소: **https://sqld-prc-study.vercel.app**. 본인 Vercel 계정으로 확인한 뒤 `검수 대기 문항 포함`을 선택하면 샘플 8문항을 풀 수 있다. PC와 휴대폰에서 같은 주소를 사용한다.

## 배포 구조

기존 Next.js와 FastAPI를 한 Vercel 프로젝트 `sqld-prc-study`에 배포했다. Python3.14 함수가 `/api/v1` 요청을 받고 Neon PostgreSQL을 사용한다. 별도 공개 백엔드 주소는 만들지 않았다. 쓰기 요청의 출처는 위 운영 고정 주소로 설정했다. 개별 배포·미리보기 주소는 본인 확인을 통과해도 출처 검사로 쓰기가 거부될 수 있으므로 학습에는 운영 고정 주소를 사용한다.

자료를 업로드하기 전에 Vercel Authentication의 **All Deployments**를 설정했고 최종에도 유지됨을 확인했다. 앱 로그인·비밀번호·유료 비밀번호 보호 기능이나 플랜 변경은 추가하지 않았다.

교재 PDF·ZIP·변환 원문·접속정보·테스트 기록은 배포 패키지에 넣지 않았다. 참조된 문항 이미지만 공개 정적 폴더 밖의 Python 함수 번들에 포함했다. 원본은 Git 제외 개인 자료 폴더에 보관한다. DB 접속정보는 비밀 환경변수로 전달했고 `TEST_DATABASE_URL`은 앱 환경변수에 넣지 않았다.

## 확인한 결과

| 확인 | 결과 |
|---|---|
| 배포 패키지 테스트 | **4 passed**: 비밀 파일·불필요 이미지 제외, 출력 경계, 누락·경로 이탈 이미지 거부 |
| 기존 브라우저 회귀 | **17 passed (28.9s)** |
| Vercel 클라우드 빌드 | 테스트 연결과 실제 앱 연결 배포 모두 READY |
| 인증된 클라우드 풀이 | 생성→저장→새로고침→채점→재풀이→문항 이동→이미지→종료→결과 통과 |
| 실제 채점 요약 | 8문항 중2채점, 정답1·오답1·미채점6·정답률50% 일치 |
| 모바일 크기 | Edge 390×844, 전체 가로 넘침 없음·화면 오류0 |
| 최종 운영 연결 | 실제 Neon의 draft8·보기32, 학습/출제/답안 기록 각각0 유지 |
| 인증 없는 요청 | 운영 고정 주소와 개별 배포 주소의 화면·API·실제 이미지 모두302 본인 확인 |
| 인증된 이미지 | API200, 직접 정적 이미지·서버 소스 경로404 |
| 정리 | 테스트용 별도 Neon 스키마 삭제, 임시 자동 점검용 우회 키 폐기, All Deployments 유지 |

쓰기는 실제 앱 DB와 다른 테스트 DB의 전용 UUID 스키마에서 수행했다. 테스트 중 실제 앱의 풀이 기록이 바뀌지 않은 것을 읽기 전용 쿼리로 확인했다. 검증 완료 후 실제 앱 DB로 전환해 다시 배포했고, 실제 앱에서는 문항 목록·이미지·홈만 읽었다. 최종 확인 때 사용자 풀이 기록은0건이었다.

클라우드 검증의 처음 시도에서는 확인 대기시간이 짧았고, 다음 시도에서는 새 문항 렌더링 전에 검증 코드가 이전 문항 번호를 읽었다. 검증 절차를 수정해 전체 흐름을 통과시켰다. 앱 채점 로직이나 정답을 바꾸지 않았다. Vercel 설정의 파일 glob은 배열 대신 문자열이어야 해 형식을 교정했다.

독립 소스 검토에서 현재 사용 범위의 수정이 필요한 문제는 없었다. 로그·실행 상태·결과 JSON은 Git 제외 `data/private/`에 보관한다. 물리 휴대폰의 실제 Vercel 계정 확인, 기기 간 이어 풀기와 사용자 최종 문항 검수0/8은 별도 확인이 남아 있다. 모의시험·전체 교재 입력·오답 통계는 추가하지 않았다.

## 재배포

일반 GitHub push로 자동 배포하지 않는다. 비공개 이미지를 포함한 전용 배포 폴더를 다시 만들어 기존 프로젝트에 연결한다. 실제 `.env`와 private 자료는 GitHub에 올리지 않는다.

```text
cd backend
uv run --locked python ../scripts/prepare_vercel.py
npx --yes vercel@65.14.0 link --yes --project sqld-prc-study --cwd <출력된_배포_폴더>
npx --yes vercel@65.14.0 deploy --yes --prod --cwd <출력된_배포_폴더>
```

배포 전 프로젝트의 All Deployments 설정을 유지하고, 배포 후 인증 없는 접근 차단과 운영 고정 주소의 API를 다시 확인한다. DB를 초기화하거나 마이그레이션·문제 입력을 자동 실행하지 않는다. 이미지 변경 시 패키지를 다시 배포해야 한다.

참고: [Vercel Python 런타임](https://vercel.com/docs/functions/runtimes/python), [Vercel Authentication](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments/vercel-authentication), [보호 기능 제공 범위](https://vercel.com/docs/deployment-protection/usage-and-pricing).
