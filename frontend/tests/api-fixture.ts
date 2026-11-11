import type { Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

export const sessionId = "00000000-0000-4000-8000-000000000001";
const now = "2026-11-11T03:00:00Z";
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export const catalog = {
  subjects: [
    { id: 1, name: "데이터 모델링의 이해", display_order: 1, published_question_count: 1, draft_question_count: 1,
      chapters: [{ id: 11, name: "데이터 모델링의 이해", display_order: 1, published_question_count: 1, draft_question_count: 1 }] },
    { id: 2, name: "SQL 기본 및 활용", display_order: 2, published_question_count: 1, draft_question_count: 0,
      chapters: [{ id: 21, name: "SQL 기본", display_order: 1, published_question_count: 1, draft_question_count: 0 }] },
  ],
  question_types: ["single_choice"],
};

type Save = { attempt_id: string; selected_option_id: string | null };
type Attempt = { id: string; attempt_number: number; selected_option_id: string | null; status: string; graded_at: string | null; correct: boolean };

export async function installApi(page: Page, settings: {
  beforeSave?: (body: Save, count: number) => Promise<boolean | void>;
  beforeRequest?: (path: string, method: string) => Promise<boolean | void>;
  html?: boolean;
  empty?: boolean;
} = {}) {
  const saveCalls: Save[] = [];
  const creates: Record<string, unknown>[] = [];
  const questions = [1, 2, 3].map((n) => ({
    id: id(10 + n), question_key: `S${n === 2 ? 2 : 1}-Q00${n === 3 ? 2 : 1}`,
    subject_id: n === 2 ? 2 : 1, chapter_id: n === 2 ? 21 : 11, source_number: n === 3 ? 2 : 1,
    type: "single_choice", status: n === 3 ? "draft" : "published",
    content_blocks: [{ type: "text", text: `합성 문항 ${n}: 다음 SQL의 실행 결과를 고르시오.` },
      { type: "sql", text: "SELECT department_id, COUNT(*) AS employee_count\nFROM employees\nGROUP BY department_id;" },
      { type: "image", src: "/api/v1/question-assets/S1-Q001/diagram.svg", alt: "합성 직원 테이블" }],
    options: [1, 2, 3, 4].map((o) => ({ id: id(n * 100 + o), option_number: o, content_blocks: [{ type: "text", text: `합성 보기 ${o}` }] })),
  }));
  function newSession(uuid: string, includeDrafts = false) {
    return { id: uuid, status: "active", current_position: 1, finished_at: null as string | null,
      criteria: { scope: "all", include_drafts: includeDrafts } as Record<string, unknown>,
      items: questions.slice(0, includeDrafts ? 3 : 2).map((question, index) => ({ id: randomUUID(), position: index + 1, question,
        attempts: [{ id: randomUUID(), attempt_number: 1, selected_option_id: null, status: "draft", graded_at: null, correct: false }] as Attempt[] })) };
  }
  const sessions = new Map([[sessionId, newSession(sessionId)]]);
  type Quiz = ReturnType<typeof newSession>;
  function current(quiz: Quiz, item: Quiz["items"][number]) {
    return quiz.status === "completed" ? item.attempts.filter((a) => a.status === "graded").at(-1) ?? item.attempts.at(-1)! : item.attempts.at(-1)!;
  }
  function session(quiz: Quiz) {
    return { id: quiz.id, mode: "study", status: quiz.status, current_position: quiz.current_position, item_count: quiz.items.length,
      answered_item_count: quiz.items.filter((i) => current(quiz, i).selected_option_id !== null).length,
      graded_item_count: quiz.items.filter((i) => i.attempts.some((a) => a.status === "graded")).length,
      started_at: now, deadline_at: null, finished_at: quiz.finished_at, finish_reason: quiz.finished_at ? "manual" : null, study_filter: quiz.criteria };
  }
  function sessionResponse(quiz: Quiz) {
    return { server_now: now, session: session(quiz), items: quiz.items.map((i) => ({ item_id: i.id, position: i.position,
      question_key: i.question.question_key, subject_id: i.question.subject_id, chapter_id: i.question.chapter_id,
      answered: current(quiz, i).selected_option_id !== null, graded: i.attempts.some((a) => a.status === "graded") })) };
  }
  const attempt = (a: Attempt) => ({ id: a.id, attempt_number: a.attempt_number, selected_option_id: a.selected_option_id, status: a.status, graded_at: a.graded_at });
  const review = (a: Attempt, q: typeof questions[number]) => ({ is_correct: a.correct, correct_option_id: q.options[1].id,
    explanation_blocks: [{ type: "text", text: "합성 해설: GROUP BY는 같은 부서의 행을 하나의 그룹으로 묶습니다." }] });
  function result(quiz: Quiz) {
    const done = quiz.items.flatMap((i) => i.attempts.filter((a) => a.status === "graded").slice(-1));
    const correct = done.filter((a) => a.correct).length;
    return { server_now: now, result: { mode: "study", session: session(quiz),
      summary: { item_count: quiz.items.length, graded_item_count: done.length, correct_item_count: correct,
        incorrect_item_count: done.length - correct, ungraded_item_count: quiz.items.length - done.length,
        accuracy_percent: done.length ? Math.round(correct / done.length * 1000) / 10 : 0 },
      items: quiz.items.map((i) => { const a = i.attempts.filter((v) => v.status === "graded").at(-1); return {
        item_id: i.id, position: i.position, question_key: i.question.question_key, subject_id: i.question.subject_id,
        outcome: a ? { attempt_id: a.id, selected_option_id: a.selected_option_id, correct_option_id: i.question.options[1].id, is_correct: a.correct, graded_at: a.graded_at } : null }; }) } };
  }
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    const method = route.request().method();
    const respond = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (await settings.beforeRequest?.(path, method)) return respond({ error: { code: "SERVICE_UNAVAILABLE", message: "서버 상태를 확인하지 못했습니다.", request_id: id(999), details: {} } }, 503);
    if (path.includes("question-assets")) return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="120" viewBox="0 0 640 120"><rect x="1" y="1" width="638" height="118" fill="white" stroke="#ccc"/><text x="24" y="48" font-size="18">employees</text><text x="24" y="88" font-size="16">employee_id | department_id</text></svg>' });
    if (path === "/catalog") {
      if (settings.html) return route.fulfill({ contentType: "text/html", body: "<html>Platform access confirmation</html>" });
      if (settings.empty) return respond({ ...catalog, subjects: catalog.subjects.map((s) => ({ ...s, published_question_count: 0, draft_question_count: 0, chapters: s.chapters.map((c) => ({ ...c, published_question_count: 0, draft_question_count: 0 })) })) });
      return respond(catalog);
    }
    if (path === "/quiz-sessions") return respond({ server_now: now, sessions: [...sessions.values()].filter((s) => s.status === "active").map(session) });
    const segments = path.split("/").filter(Boolean);
    if (segments[0] === "study-sessions" && method === "PUT") {
      const body = route.request().postDataJSON(); creates.push(body);
      const made = sessions.get(segments[1]) ?? newSession(segments[1], body.include_drafts === true);
      if (body.scope === 'subjects') made.items = made.items.filter((i) => body.subject_ids.includes(i.question.subject_id));
      if (body.scope === 'chapters') made.items = made.items.filter((i) => body.chapter_ids.includes(i.question.chapter_id));
      made.items.forEach((item, index) => { item.position = index + 1; });
      made.criteria = body; sessions.set(made.id, made); return respond(sessionResponse(made), 201);
    }
    const quiz = sessions.get(segments[1]);
    if (!quiz) return respond({ error: { code: "RESOURCE_NOT_FOUND", message: "학습을 찾을 수 없습니다.", request_id: id(999), details: {} } }, 404);
    if (segments[2] === "finish") { quiz.status = "completed"; quiz.finished_at = now; return respond(result(quiz)); }
    if (segments[2] === "result") return respond(result(quiz));
    if (!segments[2]) {
      if (method === "PATCH") quiz.current_position = route.request().postDataJSON().current_position;
      return respond(sessionResponse(quiz));
    }
    const item = quiz.items.find((i) => i.id === segments[3])!;
    if (!item) return respond({}, 404);
    const body = method === "GET" ? {} : route.request().postDataJSON();
    const a = item.attempts.find((v) => v.id === (body.attempt_id ?? body.previous_attempt_id)) ?? current(quiz, item);
    if (segments[4] === "answer") {
      saveCalls.push(body);
      if (await settings.beforeSave?.(body, saveCalls.length)) return respond({ error: { code: "SERVICE_UNAVAILABLE", message: "일시적으로 답안을 저장하지 못했습니다.", request_id: id(999), details: {} } }, 503);
      if (a.status === "graded") return respond({ error: { code: "ANSWER_ALREADY_GRADED", message: "이미 채점한 답안입니다.", request_id: id(999), details: {} } }, 409);
      a.selected_option_id = body.selected_option_id;
    }
    if (segments[4] === "grade") {
      a.status = "graded"; a.graded_at = now; a.correct = a.selected_option_id === item.question.options[1].id;
      return respond({ server_now: now, session_id: quiz.id, item_id: item.id, attempt: attempt(a), review: review(a, item.question) });
    }
    if (segments[4] === "retry") {
      const next = { id: randomUUID(), attempt_number: a.attempt_number + 1, selected_option_id: null, status: "draft", graded_at: null, correct: false };
      item.attempts.push(next);
      return respond({ server_now: now, session_id: quiz.id, item_id: item.id, attempt: attempt(next) }, 201);
    }
    const visible = current(quiz, item);
    return respond({ server_now: now, session_id: quiz.id, session_status: quiz.status,
      item: { id: item.id, position: item.position, question: item.question, attempt: attempt(visible), review: visible.status === "graded" ? review(visible, item.question) : null } });
  });
  return { saveCalls, creates, sessions, optionIds: questions[0].options.map((o) => o.id) };
}
