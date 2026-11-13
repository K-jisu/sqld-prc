# 교정·보충 PDF 학습 자료 추가

작성일: 2026-11-13.

운영 주소: https://sqld-prc-study.vercel.app/materials

홈 상단의 학습 자료 메뉴에서 데이터 모델링 11쪽·SQL 24쪽 교정·보충본을 열거나 내려받는다. PDF 열기는 새 탭을 사용하며, 새 탭에서 표시하지 못하는 기기는 내려받기를 사용한다.

## 반영 내용

- `/materials`: 기존 학습 노트 스타일의 자료 목록.
- `/api/v1/study-materials/data-modeling`, `/sql`: 등록된 두 PDF만 허용하는 파일 응답. DB를 조회하지 않는다.
- 기본 응답은 `application/pdf`, inline이다. `?download=true`는 attachment로 제공한다. `private, no-store`를 사용한다.
- 로컬 파일은 Git 제외 `data/private/study-materials/data-modeling.pdf`, `sql.pdf`에 보관한다. 제작한 교정본을 복사했으며 원본 교재 PDF는 배포하지 않는다.
- 배포 준비 도구는 지정한 두 파일만 Python 함수의 `study-materials/`에 포함한다. 공개 정적 폴더와 Git에는 PDF를 넣지 않는다.
- 기존 배포 패키지 테스트의 입력과 파일 허용 목록을 새 구성에 맞췄다. 테스트는 실행하지 않았다.

## 배포 결과와 확인 범위

기존 `sqld-prc-study` 프로젝트에 배포했다. CLI 종료 코드는0이며 다음 결과를 반환했다.

```text
Vercel CLI 65.14.0
readyState: READY
target: production
deploymentProtection: vercel_authentication
productionUrl: https://sqld-prc-study.vercel.app
```

개별 배포: https://sqld-prc-study-a75n1zwjq-jisukangs-projects.vercel.app

사용자 요청에 따라 배포 빌드 외의 테스트·lint·브라우저/API/DB 확인은 실행하지 않았다. OpenAPI JSON은 라우트 정의에서 다시 추출했으며 API 호출·DB 검증을 뜻하지 않는다. DB 마이그레이션·문항 재입력·기록 변경은 없다. main 병합은 하지 않았다.

재배포에는 위 두 비공개 PDF가 필요하다. Git만 새로 받은 환경에서는 파일을 별도 전달받아 같은 폴더에 둬야 한다. 기존 Vercel All Deployments 보호 설정을 유지한다.
