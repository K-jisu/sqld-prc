---
name: "SQLD 연습"
description: "밝고 차분한 개인 학습 노트"
colors:
  foreground: "#20242b"
  background: "#f6f7f8"
  surface: "#fff"
  muted: "#626a74"
  border: "#e3e6e9"
  control: "#c8ced5"
  blue: "#1d5fbf"
  positive: "#276447"
  negative: "#aa3838"
  subdued: "#f0f1f3"
  code-surface: "#f3f5f7"
typography:
  headline:
    fontSize: "26px"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "-.025em"
  title:
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "-.015em"
  body:
    fontFamily: 'var(--font-geist-sans), "Apple SD Gothic Neo", "Malgun Gothic", sans-serif'
    fontSize: "14px"
    lineHeight: 1.6
  reading:
    fontSize: "16px"
    lineHeight: 1.9
  label:
    fontSize: "12px"
  sql:
    fontFamily: "var(--font-geist-mono), monospace"
    fontSize: "13px"
    lineHeight: 1.85
rounded:
  tag: "4px"
  small: "5px"
  control: "6px"
  panel: "8px"
  dialog: "12px"
spacing:
  tight: "8px"
  control-gap: "10px"
  compact: "16px"
  inset: "20px"
  section: "24px"
  panel: "28px"
  reading: "30px"
components:
  button-primary:
    backgroundColor: "{colors.foreground}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "10px 18px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.control}"
    padding: "10px 18px"
  question-navigation:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted}"
    rounded: "{rounded.small}"
    width: "44px"
  status-pill:
    rounded: "{rounded.tag}"
    padding: "2px 8px"
  sheet:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
  answer-option:
    rounded: "{rounded.control}"
    padding: "16px 18px"
  checkbox-control:
    width: "17px"
    height: "17px"
---

# Design System: SQLD 연습

## Overview

**Creative North Star: "밝고 차분한 학습 노트"**

사용자가 선택한 학습 노트의 세계를 밝은 무채색 바탕, 흰 종이 면, 짙은 잉크와 낮은 대비의 구분선으로 구현한다. `achromatic-ledger` 방향을 바탕으로 읽기와 조작이 중심인 Operate 화면을 유지한다. 작은 설명과 문항 번호가 작업 위치를 안내하고, 문제 본문은 여유 있는 행간으로 구분한다.

색은 현재 위치·키보드 포커스·선택 컨트롤과 정오답·검수 대기 같은 상태를 설명한다. 화면 진입 연출 없이 버튼의 짧은 상태 피드백만 사용하며, SQL과 그림의 원래 구조를 보존한다. 디자인 예시는 합성 문항을 사용한다.

**Key Characteristics:**

- 밝은 무채색 바탕과 그림자 없는 종이 면.
- 문제 본문과 조작부를 구분하는 글자 크기와 여백.
- 번호·상태 문구·색을 함께 쓰는 작업 안내.
- 작은 화면에서 접히는 문항 목록과 내부에서 스크롤하는 SQL·확대 그림.

## Colors

짙은 잉크를 주조색으로 삼고, 상태를 나타내는 작은 색 영역을 밝은 중립색 면 위에 둔다. 값은 위 frontmatter와 `frontend/app/globals.css`의 실제 선언을 따른다.

### Primary

- **본문 잉크 — foreground:** 본문·제목·주요 버튼의 배경.
- **현재 위치 파랑 — blue:** 현재 문항 경계, 포커스 외곽선, 네이티브 선택 컨트롤.
- **정답 초록 — positive / 오답 빨강 — negative:** 채점 결과와 해설 제목. 정오답 문구를 함께 표시한다.

### Neutral

- **노트 바탕 — background / 종이 면 — surface:** 전체 바탕과 패널.
- **보조 잉크 — muted:** 설명, 저장 상태, 문항 키, 하단 안내.
- **구분선 — border / 입력 경계 — control:** 면의 경계와 조작 가능한 요소.
- **낮은 면 — subdued / SQL 면 — code-surface:** 범위 탭 바탕과 코드 읽기 영역.

검수 대기 태그는 현재 구현의 옅은 황색 바탕과 갈색 글자를 사용한다. 정답·오답 태그 역시 별도의 옅은 상태 바탕을 가진다. 이 국소 상태색은 sidecar의 실제 컴포넌트 CSS로 보존한다.

**The State Pair Rule.** 정오답과 검수 대기는 색과 문구를 함께 표시한다.

## Typography

**Display Font:** 별도 장식용 서체 없이 본문 산세리프를 공유한다.

**Body Font:** 기존 `next/font`의 Geist 변수와 한국어 시스템 대체 서체(Apple SD Gothic Neo, Malgun Gothic, sans-serif).

**Label/Mono Font:** SQL과 문항 키는 Geist Mono 변수와 monospace 대체 서체.

**Character:** 제목은 절제된 굵기, 본문은 넉넉한 행간을 사용한다. 개수·정답률·문항 번호는 고정폭 숫자로 정렬한다.

### Hierarchy

- **Headline:** 홈의 큰 제목. 작은 화면에서는 크기를 줄인다.
- **Title:** 일반 절 제목. 학습 문항 제목은 데스크톱과 휴대폰에서 별도로 조정된다.
- **Body:** 조작부와 일반 안내.
- **Reading:** 문제 본문. 최대 줄 길이는 `75ch`; 보기·해설은 더 작은 본문 크기를 사용한다.
- **Label / SQL:** 보조 상태와 코드. 휴대폰에서는 SQL 크기를 한 단계 줄인다.

**The Content Shape Rule.** SQL의 줄바꿈·공백을 보존하고, 한국어 문장은 단어 단위 줄바꿈과 긴 문자열의 넘침 방지를 함께 적용한다.

## Layout

홈은 최대 `1080px` 안에서 범위 선택과 짧은 안내를 나란히 둔다. 문제풀이 작업영역은 최대 `1160px`이며, 문항 목록 `204px`와 간격 `28px`, 남은 가변 폭 본문으로 구성한다. 결과 화면은 최대 `880px`이다. 본문 면의 내부 여백은 데스크톱 `30px`, 홈과 결과 패널은 `28px`을 사용한다.

- **1240px 이하:** 주요 컨테이너의 좌우 바깥 여백이 `32px`이 된다.
- **980px 이하:** 학습 목록은 `176px`, 간격은 `22px`로 줄고 번호 격자는 세 열이 된다. 문제·보기·해설의 좌우 여백은 `24px`로 줄인다.
- **820px 이하:** 작업영역이 한 열로 쌓인다. 옆 문항 목록 대신 상단 `details` 목록을 사용하고, 홈의 보조 안내와 브랜드 부제를 감춘다.
- **560px 이하:** 바깥 여백은 `16px`, 문제·해설 내부는 주로 `20px`이다. 문항 조작부는 화면 아래에 sticky로 남는다.

SQL은 내부 가로 스크롤을 허용한다. 그림 미리보기는 가용 폭에 맞추고, 확대 대화상자의 스크롤 영역에서 원본을 확인한다. 확대 그림의 최소 폭은 `640px`이다.

## Elevation & Depth

일반 패널에는 그림자가 없다. 흰 면과 낮은 대비의 선으로 정보 덩어리를 구분한다. 현재 문항의 안쪽 선은 위치 표시이며 떠 있는 면을 만들지 않는다. 종료 확인과 그림 확대 대화상자에만 실제 그림자와 배경 덮개를 사용한다. 정확한 그림자 값은 sidecar에 보존한다.

**The Flat Sheet Rule.** 일반 학습 면의 깊이는 면색과 경계로 표현한다. 대화상자의 깊이 표현을 일반 패널에 확장하지 않는다.

## Shapes

패널·조작부·작은 번호·상태 태그는 frontmatter의 관찰된 모서리 단계로 구분한다. 선택지 번호와 채점 표시점만 원형이다. 기본 경계는 얇은 선이며, 포커스는 파란 외곽선(`2px`)과 바깥 간격(`4px`)을 가진다. 선택지 포커스는 행 전체에 바깥 간격 `3px`, 범위 탭은 `2px`를 적용한다.

## Components

### Buttons

짙은 주 행동과 경계가 있는 보조 행동을 구분한다. 기본 최소 높이는 `44px`이며 색·경계 변화만 `150ms` 전환한다. 주요 버튼은 hover에서 잉크가 옅어지고, 보조 버튼은 바탕이 옅어지며, 비활성 버튼은 불투명도 `.44`와 금지 커서를 사용한다. 작은 변형과 휴대폰 변형은 기존 CSS의 여백을 따른다.

### Chips

작은 사각 태그는 미채점·검수 대기·정답·오답을 짧은 문구로 표시한다. 상태 배경과 글자색을 함께 바꾸며 클릭 동작은 없다.

### Cards / Containers

같은 흰 종이 면과 경계를 홈 범위 선택, 학습 본문, 결과 요약과 목록에 재사용한다. 내부 여백은 내용별로 달라지며, 본문·보기·저장 상태·해설·이동 영역은 한 면 안에서 구분된다.

### Inputs / Fields

체크박스는 네이티브 컨트롤(`17px`)을 유지하며 검수 대기 선택의 라벨 행은 최소 높이 `44px`이다. 범위 탭은 라디오 컨트롤을 감싼 라벨로, 선택 시 흰 면과 짙은 글자를 쓴다. 숨겨진 컨트롤에도 키보드 포커스가 보이도록 부모 행에 표시한다.

### Navigation

상단 브랜드는 홈으로, 보조 링크는 학습 목록으로 연결된다. 번호 버튼의 기본 폭은 `44px`; 현재 위치는 파란 경계와 안쪽 선, 답안·채점 완료는 중립색 면으로 표시한다. 채점 완료 표시점을 별도로 제공하며 채점 전 정오답색은 사용하지 않는다. 작은 화면의 목록 접기·펼치기는 네이티브 `details`이다.

### Answer Options

선택지 행 전체가 라디오 라벨이다. 선택 시 행의 경계·바탕과 원형 번호의 대비가 바뀐다. 채점 후 정답 문구, 정오답 번호색, 해설 제목을 함께 표시한다. 보기는 번호·본문·결과 표식으로 구성하고 SQL·그림이 길어져도 본문 열이 줄어들 수 있게 한다.

버튼·번호·선택지의 포커스와 비활성 상태를 유지한다. `prefers-reduced-motion: reduce`에서는 전환·애니메이션 시간을 `.01ms`로 낮추고 부드러운 스크롤을 해제한다.

## Do's and Don'ts

### Do:

- **Do** 밝은 무채색 종이 면과 짙은 잉크의 위계를 유지한다.
- **Do** 정오답과 검수 대기에 색과 상태 문구를 함께 제공한다.
- **Do** SQL의 공백·줄바꿈과 그림의 확대 확인 경로를 보존한다.
- **Do** 숨겨진 라디오를 포함한 조작부의 키보드 포커스를 표시한다.
- **Do** 디자인 예시에는 별도의 합성 문항을 사용한다.

### Don't:

- **Don't** 일반 학습 패널에 대화상자 그림자를 적용한다.
- **Don't** 채점 전 문항 목록에 정오답색을 표시한다.
- **Don't** 실제 교재 본문·그림을 공개 코드나 디자인 예시에 복사한다.
- **Don't** 장식용 차트·사진·허구 통계나 화면 진입 연출을 추가한다.
