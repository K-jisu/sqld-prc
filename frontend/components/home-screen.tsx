"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, keys } from "@/lib/api";
import type { ActiveSessions, Catalog, SessionResponse, StudyFilter } from "@/lib/types";
import { AppHeader, Arrow, ErrorNotice, LoadingPanel } from "./ui";
import { MockStart } from './mock-start';

const scopeLabels = { all: "전체 범위", subjects: "선택 과목", chapters: "선택 단원", previous_session: "이전 풀이 목록", wrong_answers: "오답 복습" };

function StudyForm({ catalog }: { catalog: Catalog }) {
  const router = useRouter();
  const client = useQueryClient();
  const [scope, setScope] = useState<"all" | "subjects" | "chapters">("all");
  const [subjectIds, setSubjectIds] = useState<number[]>([]);
  const [chapterIds, setChapterIds] = useState<number[]>([]);
  const [includeDrafts, setIncludeDrafts] = useState(false);
  const creation = useRef<{ fingerprint: string; id: string } | null>(null);
  const inFlight = useRef(false);
  const create = useMutation({
    mutationFn: ({ id, body }: { id: string; body: StudyFilter }) => api<SessionResponse>(`/study-sessions/${id}`, { method: "PUT", body }),
    onSuccess: async (data) => {
      client.setQueryData(keys.session(data.session.id), data);
      await client.invalidateQueries({ queryKey: keys.active });
      router.push(`/study/${data.session.id}`);
    },
    onSettled: () => { inFlight.current = false; },
  });
  const chapters = catalog.subjects.flatMap((s) => s.chapters);
  const selected = scope === "all" ? catalog.subjects : scope === "subjects"
    ? catalog.subjects.filter((s) => subjectIds.includes(s.id)) : chapters.filter((c) => chapterIds.includes(c.id));
  const count = selected.reduce((sum, row) => sum + row.published_question_count + (includeDrafts ? row.draft_question_count : 0), 0);
  const published = catalog.subjects.reduce((sum, s) => sum + s.published_question_count, 0);
  const drafts = catalog.subjects.reduce((sum, s) => sum + s.draft_question_count, 0);
  const toggle = (ids: number[], id: number) => ids.includes(id) ? ids.filter((v) => v !== id) : [...ids, id].sort((a, b) => a - b);
  function start() {
    if (!count || inFlight.current) return;
    const body: StudyFilter = { scope, include_drafts: includeDrafts,
      ...(scope === "subjects" ? { subject_ids: subjectIds } : scope === "chapters" ? { chapter_ids: chapterIds } : {}) };
    const fingerprint = JSON.stringify(body);
    if (creation.current?.fingerprint !== fingerprint) creation.current = { fingerprint, id: crypto.randomUUID() };
    inFlight.current = true;
    create.mutate({ id: creation.current.id, body });
  }
  return <section className="study-form sheet" aria-labelledby="scope-title">
    <div className="section-heading"><h2 id="scope-title">학습 범위</h2><span className="muted">검수 완료 {published} · 대기 {drafts}</span></div>
    <fieldset className="scope-tabs"><legend className="sr-only">학습 범위 선택</legend>
      {([['all', '전체'], ['subjects', '과목별'], ['chapters', '단원별']] as const).map(([value, label]) => <label key={value} className={scope === value ? 'scope-tab selected' : 'scope-tab'}>
        <input type="radio" name="scope" value={value} checked={scope === value} onChange={() => setScope(value)} disabled={create.isPending}/>{label}
      </label>)}
    </fieldset>
    {scope === 'all' ? <div className="subject-overview">{catalog.subjects.map((subject) => <div className="subject-line" key={subject.id}><div><span className="subject-number">{subject.id}과목</span><strong>{subject.name}</strong></div><span className="count">{subject.published_question_count + (includeDrafts ? subject.draft_question_count : 0)}<span className="muted"> 문항</span></span></div>)}</div>
      : scope === 'subjects' ? <fieldset className="filter-list"><legend className="sr-only">과목 선택</legend>{catalog.subjects.map((subject) => <label className="filter-row" key={subject.id}>
        <input type="checkbox" checked={subjectIds.includes(subject.id)} onChange={() => setSubjectIds(toggle(subjectIds, subject.id))} disabled={create.isPending}/><span>{subject.id}과목 · {subject.name}</span><span className="count">{subject.published_question_count + (includeDrafts ? subject.draft_question_count : 0)}문항</span>
      </label>)}</fieldset>
        : <div className="chapter-groups">{catalog.subjects.map((subject) => <fieldset className="filter-list" key={subject.id}><legend>{subject.id}과목 · {subject.name}</legend>{subject.chapters.map((chapter) => <label className="filter-row" key={chapter.id}>
          <input type="checkbox" checked={chapterIds.includes(chapter.id)} onChange={() => setChapterIds(toggle(chapterIds, chapter.id))} disabled={create.isPending}/><span>{chapter.name}</span><span className="count">{chapter.published_question_count + (includeDrafts ? chapter.draft_question_count : 0)}문항</span>
        </label>)}</fieldset>)}</div>}
    <div className="review-choice"><label className="checkbox-label"><input type="checkbox" checked={includeDrafts} onChange={(e) => setIncludeDrafts(e.target.checked)} disabled={create.isPending}/><span>검수 대기 문항 포함</span></label>
      <p>교재와 최종 대조하기 전의 문항도 풀어봅니다. 검수 완료 상태로 바뀌지는 않습니다.</p>
    </div>
    {!count && <p className="empty-hint">선택한 범위에 학습할 문항이 없습니다.{drafts > 0 && !includeDrafts && ' 검수 대기 문항을 포함하면 문제를 풀어볼 수 있습니다.'}</p>}
    {create.isError && <ErrorNotice error={create.error}/>}
    <div className="start-row"><p><span className="muted">선택한 범위</span><strong>{count}<span>문항</span></strong></p>
      <button className="button primary" disabled={!count || create.isPending} onClick={start}>{create.isPending ? '학습을 준비하는 중' : `${count}문항 학습 시작`}<Arrow/></button>
    </div>
  </section>;
}

function ActivePanel() {
  const active = useQuery({ queryKey: keys.active, queryFn: ({ signal }) => api<ActiveSessions>('/quiz-sessions', { signal }) });
  return <section className="ongoing-section" id="ongoing" aria-labelledby="ongoing-title"><div className="section-heading"><h2 id="ongoing-title">이어풀기</h2>{active.data && <span className="muted">진행 중 {active.data.sessions.length}개</span>}</div>
    {active.isPending ? <LoadingPanel label="진행 중인 학습을 불러오는 중"/>
      : active.isError ? <ErrorNotice error={active.error} onRetry={() => void active.refetch()}/>
        : active.data.sessions.length === 0 ? <div className="empty-panel"><p>진행 중인 학습이 없습니다</p><span>새 학습을 시작하면 이곳에서 이어 풀 수 있습니다.</span></div>
          : <div className="session-list">{active.data.sessions.map((session) => <Link className="session-row" href={`/${session.mode === 'mock' ? 'mock' : 'study'}/${session.id}`} key={session.id}>
            <div className="session-identity"><strong>{session.mode === 'mock' ? '모의고사' : scopeLabels[session.study_filter?.scope ?? 'all']} · {session.item_count}문항</strong><span>{new Intl.DateTimeFormat('ko-KR', { month: 'long', day: 'numeric', timeZone: 'Asia/Seoul' }).format(new Date(session.started_at))} 시작{session.study_filter?.include_drafts && ' · 검수 대기 포함'}</span></div>
            <span className="session-progress">{session.mode === 'mock' ? `선택 ${session.answered_item_count}` : `채점 ${session.graded_item_count}`}/{session.item_count}<span>현재 {session.current_position}번</span></span><Arrow/>
          </Link>)}</div>}
  </section>;
}

export function HomeScreen() {
  const catalog = useQuery({ queryKey: keys.catalog, queryFn: ({ signal }) => api<Catalog>('/catalog', { signal }) });
  return <><AppHeader><nav className="study-toolbar" aria-label="학습 메뉴"><Link className="header-link" href="/materials">학습 자료</Link><Link className="header-link" href="/records">내 기록<Arrow/></Link><a className="header-link" href="#ongoing">이어풀기<Arrow/></a></nav></AppHeader><main id="main" className="home-main">
    <div className="page-heading"><h1>학습하기</h1><p>범위를 정하고, 한 문항씩 차분하게 풀어보세요.</p></div>
    <div className="home-grid"><div>{catalog.isPending ? <LoadingPanel label="문제은행을 불러오는 중"/>
      : catalog.isError ? <ErrorNotice error={catalog.error} onRetry={() => void catalog.refetch()}/>
        : <StudyForm catalog={catalog.data}/>}</div>
      <aside className="home-note"><svg width="42" height="42" viewBox="0 0 42 42" fill="none" aria-hidden="true"><path d="M9 6h21a3 3 0 0 1 3 3v27H12a3 3 0 0 1-3-3V6Z" stroke="currentColor" strokeWidth="1.4"/><path d="M15 14h12M15 20h12M15 26h7M9 31h24" stroke="currentColor" strokeWidth="1.4"/></svg>
        <h2>한 문항에 집중하기</h2><p>답안을 고르면 자동으로 저장됩니다. 정답을 확인한 뒤 해설을 읽고, 같은 문항을 다시 풀 수 있습니다.</p><p className="muted">학습을 마칠 때 직접 종료하면 지금까지의 결과를 확인할 수 있습니다.</p>
      </aside></div>
    {catalog.data && <MockStart catalog={catalog.data}/>}
    <ActivePanel/>
  </main><footer className="app-footer">나의 속도로, 한 문항씩.</footer></>;
}
