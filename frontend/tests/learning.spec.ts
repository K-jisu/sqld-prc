import { expect, test } from "@playwright/test";
import { installApi, sessionId } from "./api-fixture";

test("범위와 검수 대기 포함을 선택해 학습을 시작한다", async ({ page }) => {
  const api = await installApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "학습하기", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "2문항 학습 시작" })).toBeEnabled();
  await page.getByLabel("검수 대기 문항 포함").check();
  await page.getByRole("button", { name: "3문항 학습 시작" }).click();
  await expect(page).toHaveURL(/\/study\/[\da-f-]+$/, { timeout: 15_000 });
  await expect(page.getByText("합성 문항 1:", { exact: false })).toBeVisible();
  expect(api.creates).toEqual([{ scope: "all", include_drafts: true }]);
});

test("빠른 선택을 직렬 저장하고 대기 중 채점과 이동을 막는다", async ({ page }) => {
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  let releaseSecond!: () => void;
  const second = new Promise<void>((resolve) => { releaseSecond = resolve; });
  const api = await installApi(page, { beforeSave: async (_, count) => { if (count === 1) await held; if (count === 2) await second; } });
  await page.goto(`/study/${sessionId}`);
  await page.getByRole("radio", { name: "1번 보기" }).check();
  await page.getByRole("radio", { name: "2번 보기" }).check();
  await page.getByRole("radio", { name: "3번 보기" }).check();
  await expect(page.getByRole("radio", { name: "3번 보기" })).toBeChecked();
  await expect(page.getByRole("button", { name: "정답 확인", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "다음 문항" })).toBeDisabled();
  expect(api.saveCalls).toHaveLength(1);
  release();
  try {
    await expect.poll(() => api.saveCalls.length).toBe(2);
    await expect(page.getByRole("radio", { name: "3번 보기" })).toBeChecked();
  } finally { releaseSecond(); }
  await expect(page.getByText("저장됨", { exact: true })).toBeVisible();
  expect(api.saveCalls.map((v) => v.selected_option_id)).toEqual(api.optionIds.slice(0, 3));
  await expect(page.getByRole("radio", { name: "3번 보기" })).toBeChecked();
});

test("저장 실패를 표시하고 사용자가 재시도해야 채점할 수 있다", async ({ page }) => {
  const api = await installApi(page, { beforeSave: async (_, count) => count === 1 });
  await page.goto(`/study/${sessionId}`);
  await page.getByRole("radio", { name: "2번 보기" }).check();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("저장하지 못했습니다");
  await expect(page.getByRole("button", { name: "정답 확인", exact: true })).toBeDisabled();
  expect(api.saveCalls).toHaveLength(1);
  await page.getByRole("button", { name: "다시 저장" }).click();
  await expect(page.getByText("저장됨", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "정답 확인", exact: true })).toBeEnabled();
  expect(api.saveCalls).toHaveLength(2);
});

test("다른 기기에서 같은 답안을 채점하면 서버의 선택과 채점 결과를 표시한다", async ({ page }) => {
  const server = await installApi(page, { beforeSave: async () => {
    const item = server.sessions.get(sessionId)!.items[0];
    Object.assign(item.attempts[0], { selected_option_id: item.question.options[1].id,
      status: "graded", graded_at: "2026-11-11T03:00:00Z", correct: true });
  } });
  await page.goto(`/study/${sessionId}`);
  await page.getByRole("radio", { name: "1번 보기" }).check();
  await expect(page.getByText("정답입니다", { exact: true })).toBeVisible();
  await expect(page.getByRole("radio", { name: "2번 보기" })).toBeChecked();
  await expect(page.getByRole("radio", { name: "1번 보기" })).not.toBeChecked();
  await expect(page.getByRole("button", { name: "다시 풀기", exact: true })).toBeEnabled();
});

test("저장 위치와 답안은 새로고침 후 유지되고 채점·재풀이·결과가 연결된다", async ({ page }) => {
  await installApi(page);
  await page.goto(`/study/${sessionId}`);
  await page.getByRole("radio", { name: "2번 보기" }).check();
  await expect(page.getByText("저장됨", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("radio", { name: "2번 보기" })).toBeChecked();
  await page.getByRole("button", { name: "정답 확인", exact: true }).click();
  await expect(page.getByText("정답입니다", { exact: true })).toBeVisible();
  await expect(page.getByText("합성 해설:", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "다시 풀기", exact: true }).click();
  await expect(page.getByText("합성 해설:", { exact: false })).toHaveCount(0);
  await expect(page.getByRole("radio", { name: "2번 보기" })).not.toBeChecked();
  await page.getByRole("radio", { name: "1번 보기" }).check();
  await expect(page.getByText("저장됨", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "정답 확인", exact: true }).click();
  await expect(page.getByText("다시 확인해 보세요", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "다음 문항" }).click();
  await expect(page.getByText("합성 문항 2:", { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByText("합성 문항 2:", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "학습 종료", exact: true }).click();
  await page.getByRole("button", { name: "종료하고 결과 보기" }).click();
  await expect(page.getByRole("heading", { name: "학습 결과", exact: true })).toBeVisible();
  await expect(page.getByText("미채점", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "같은 범위 다시 학습" }).click();
  await expect(page).toHaveURL(/\/study\/[\da-f-]+$/);
});

test("접근 확인 HTML 응답을 학습 데이터나 저장 성공으로 취급하지 않는다", async ({ page }) => {
  await installApi(page, { html: true });
  await page.goto("/");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("접속 확인이 필요합니다");
  await expect(page.getByRole("button", { name: /문항 학습 시작/ })).toHaveCount(0);
});

test("빈 범위에서는 0문항을 표시하고 학습 생성을 막는다", async ({ page }) => {
  await installApi(page, { empty: true });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "0문항 학습 시작" })).toBeDisabled();
  await expect(page.getByText("선택한 범위에 학습할 문항이 없습니다", { exact: false })).toBeVisible();
});

test("모바일에서 SQL과 그림을 읽고 번호 목록을 열 수 있으며 가로 넘침이 없다", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installApi(page);
  await page.goto(`/study/${sessionId}`);
  await expect(page.getByText("합성 문항 1:", { exact: false })).toBeVisible();
  await expect(page.getByText("SELECT department_id", { exact: false })).toBeVisible();
  await page.getByLabel("문항 목록", { exact: true }).click();
  await expect(page.getByRole("button", { name: "2번 문항" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("서버 답안 복원이 끝나기 전에는 캐시 답안으로 채점할 수 없다", async ({ page }) => {
  let holdRead = false;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const server = await installApi(page, {
    beforeSave: async (body, count) => {
      if (count === 2) {
        server.sessions.get(sessionId)!.items[0].attempts[0].selected_option_id = body.selected_option_id;
        return true;
      }
    },
    beforeRequest: async (path, method) => { if (holdRead && method === 'GET' && path.includes('/items/')) await gate; },
  });
  await page.goto(`/study/${sessionId}`);
  await page.getByRole('radio', { name: '1번 보기' }).check();
  await expect(page.getByText('저장됨', { exact: true })).toBeVisible();
  await page.getByRole('radio', { name: '2번 보기' }).check();
  await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
  holdRead = true;
  await page.getByRole('button', { name: '서버 답안 다시 확인' }).click();
  try {
    await expect(page.getByRole('button', { name: '정답 확인', exact: true })).toBeDisabled();
    await expect(page.getByRole('button', { name: '다음 문항' })).toBeDisabled();
  } finally { release(); }
  await expect(page.getByText('저장됨', { exact: true })).toBeVisible();
  await expect(page.getByRole('radio', { name: '2번 보기' })).toBeChecked();
});

for (const operation of ['grade', 'retry'] as const) {
  test(`${operation} 성공 후 재조회가 실패해도 이전 상태로 조작하지 못한다`, async ({ page }) => {
    let failRead = false;
    let armed = false;
    await installApi(page, { beforeRequest: async (path, method) => {
      if (armed && method === 'POST' && path.endsWith('/' + operation)) failRead = true;
      return failRead && method === 'GET' && path.includes('/items/');
    } });
    await page.goto(`/study/${sessionId}`);
    await page.getByRole('radio', { name: '2번 보기' }).check();
    await expect(page.getByText('저장됨', { exact: true })).toBeVisible();
    if (operation === 'retry') {
      await page.getByRole('button', { name: '정답 확인', exact: true }).click();
      await expect(page.getByText('정답입니다', { exact: true })).toBeVisible();
    }
    armed = true;
    await page.getByRole('button', { name: operation === 'grade' ? '정답 확인' : '다시 풀기', exact: true }).click();
    await expect(page.getByRole('alert').filter({ hasText: '서버 상태를 확인하지 못했습니다' })).toBeVisible();
    await expect(page.getByRole('radio', { name: '1번 보기' })).toBeDisabled();
    if (operation === 'retry') await expect(page.getByText('정답입니다', { exact: true })).toHaveCount(0);
    failRead = false;
    await page.getByRole('button', { name: '다시 불러오기' }).click();
    await expect(page.getByRole('button', { name: operation === 'grade' ? '다시 풀기' : '정답 확인', exact: true })).toBeVisible();
  });
}

test('종료 직후 재조회가 실패해도 결과의 문항 링크는 읽기 전용이다', async ({ page }) => {
  let closed = false;
  await installApi(page, { beforeRequest: async (path, method) => {
    if (method === 'POST' && path.endsWith('/finish')) closed = true;
    return closed && method === 'GET' && path === `/quiz-sessions/${sessionId}`;
  } });
  await page.goto(`/study/${sessionId}`);
  await page.getByRole('button', { name: '학습 종료', exact: true }).click();
  await page.getByRole('button', { name: '종료하고 결과 보기' }).click();
  await expect(page.getByRole('heading', { name: '학습 결과', exact: true })).toBeVisible();
  await page.getByRole('link').filter({ hasText: '2과목 1번' }).click();
  await expect(page.getByText('합성 문항 2:', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: '정답 확인', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '학습 종료', exact: true })).toHaveCount(0);
});

test('브라우저 뒤로 가기 후에도 저장 실패한 선택과 복구 동작을 보존한다', async ({ page }) => {
  await installApi(page, { beforeSave: async () => true });
  await page.goto('/');
  await page.getByRole('link').filter({ hasText: '전체 범위 · 2문항' }).click();
  await page.getByRole('radio', { name: '2번 보기' }).check();
  await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: '학습하기', exact: true })).toBeVisible();
  await page.getByRole('link').filter({ hasText: '전체 범위 · 2문항' }).click();
  await expect(page.getByRole('radio', { name: '2번 보기' })).toBeChecked();
  await expect(page.getByRole('button', { name: '다시 저장' })).toBeVisible();
  await expect(page.getByRole('button', { name: '정답 확인', exact: true })).toBeDisabled();
});

test('키보드로 보기를 선택하고 그림 확대를 닫을 수 있다', async ({ page }) => {
  await installApi(page);
  await page.goto(`/study/${sessionId}`);
  await page.getByRole('radio', { name: '1번 보기' }).focus();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('radio', { name: '2번 보기' })).toBeChecked();
  await expect(page.getByText('저장됨', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '그림 크게 보기: 합성 직원 테이블' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('복원 조회가 실패하면 미저장 상태를 유지하고 복원 성공 후에만 해제한다', async ({ page }) => {
  let failRead = false;
  await installApi(page, { beforeSave: async () => true,
    beforeRequest: async (path, method) => failRead && method === 'GET' && path.includes('/items/') });
  await page.goto(`/study/${sessionId}`);
  await page.getByRole('radio', { name: '2번 보기' }).check();
  await expect(page.getByRole('button', { name: '다시 저장' })).toBeVisible();
  failRead = true;
  await page.getByRole('button', { name: '서버 답안 다시 확인' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('서버 상태를 확인하지 못했습니다');
  await expect(page.getByRole('button', { name: '정답 확인', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: '다음 문항' })).toBeDisabled();
  failRead = false;
  await page.getByRole('button', { name: '서버 답안 다시 확인' }).click();
  await expect(page.getByRole('radio', { name: '2번 보기' })).not.toBeChecked();
  await expect(page.getByRole('radio', { name: '1번 보기' })).toBeEnabled();
});

test('학습 생성 실패를 수동 재시도할 때 같은 UUID를 사용한다', async ({ page }) => {
  const requests: string[] = [];
  await installApi(page, { beforeRequest: async (path, method) => {
    if (method === 'PUT' && path.startsWith('/study-sessions/')) { requests.push(path); return requests.length === 1; }
  } });
  await page.goto('/');
  await page.getByRole('button', { name: '2문항 학습 시작' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toBeVisible();
  await page.getByRole('button', { name: '2문항 학습 시작' }).click();
  await expect(page).toHaveURL(/\/study\/[\da-f-]+$/, { timeout: 15_000 });
  expect(requests).toHaveLength(2);
  expect(requests[0]).toBe(requests[1]);
});

test('과목과 단원 필터의 문항 수와 생성 요청이 일치한다', async ({ page }) => {
  const server = await installApi(page);
  await page.goto('/');
  await page.getByText('과목별', { exact: true }).click();
  await page.getByRole('checkbox', { name: /1과목 · 데이터 모델링의 이해/ }).check();
  await expect(page.getByRole('button', { name: '1문항 학습 시작' })).toBeEnabled();
  await page.getByText('단원별', { exact: true }).click();
  await page.getByRole('checkbox', { name: /^데이터 모델링의 이해/ }).check();
  await page.getByRole('button', { name: '1문항 학습 시작' }).click();
  await expect(page).toHaveURL(/\/study\/[\da-f-]+$/, { timeout: 15_000 });
  expect(server.creates).toEqual([{ scope: 'chapters', include_drafts: false, chapter_ids: [11] }]);
});
