"use client";

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { api, keys, questionLabel } from '@/lib/api';
import type { Catalog, MockHistoryResponse, SessionResponse, StatsResponse, StudyFilter, WrongAnswersResponse } from '@/lib/types';
import { AppHeader, Arrow, ErrorNotice, LoadingPanel } from './ui';

const formatDate = (value: string) => new Intl.DateTimeFormat('ko-KR', {
  month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Seoul',
}).format(new Date(value));

export function RecordsScreen() {
  const router = useRouter();
  const client = useQueryClient();
  const [subject, setSubject] = useState(0);
  const [chapter, setChapter] = useState(0);
  const [includeDrafts, setIncludeDrafts] = useState(false);
  const creation = useRef<{ id: string; fingerprint: string } | null>(null);
  const inFlight = useRef(false);
  const catalog = useQuery({ queryKey: keys.catalog, queryFn: ({ signal }) => api<Catalog>('/catalog', { signal }) });
  const stats = useQuery({ queryKey: ['records', 'stats'], queryFn: ({ signal }) => api<StatsResponse>('/me/stats', { signal }) });
  const filters = new URLSearchParams();
  if (subject) filters.set('subject_id', String(subject));
  if (chapter) filters.set('chapter_id', String(chapter));
  const wrong = useQuery({ queryKey: ['records', 'wrong', subject, chapter],
    queryFn: ({ signal }) => api<WrongAnswersResponse>('/me/wrong-answers' + (filters.toString() ? '?' + filters.toString() : ''), { signal }) });
  const history = useQuery({ queryKey: ['records', 'history'], queryFn: ({ signal }) => api<MockHistoryResponse>('/me/mock-sessions', { signal }) });
  const create = useMutation({
    mutationFn: ({ id, body }: { id: string; body: StudyFilter }) => api<SessionResponse>(`/study-sessions/${id}`, { method: 'PUT', body }),
    onSuccess: data => {
      client.setQueryData(keys.session(data.session.id), data);
      void client.invalidateQueries({ queryKey: keys.active });
      router.push(`/study/${data.session.id}`);
    },
    onSettled: () => { inFlight.current = false; },
  });
  const wrongCount = wrong.data?.items.filter(item => includeDrafts || item.available).length ?? 0;
  const chapters = catalog.data?.subjects.filter(s => !subject || s.id === subject).flatMap(s => s.chapters) ?? [];
  function reviewWrong() {
    if (inFlight.current || !wrongCount) return;
    const body: StudyFilter = { scope: 'wrong_answers', include_drafts: includeDrafts,
      ...(subject ? { subject_ids: [subject] } : {}), ...(chapter ? { chapter_ids: [chapter] } : {}) };
    const fingerprint = JSON.stringify(body);
    if (creation.current?.fingerprint !== fingerprint) creation.current = { id: crypto.randomUUID(), fingerprint };
    inFlight.current = true;
    create.mutate({ id: creation.current.id, body });
  }
  return <><AppHeader><Link className="header-link" href="/">학습 목록<Arrow direction="left"/></Link></AppHeader><main id="main" className="records-main">
    <div className="page-heading"><h1>내 기록</h1><p>같은 문항은 가장 최근에 채점한 결과로 한 번만 집계합니다.</p></div>
    {!stats.data ? stats.error ? <ErrorNotice error={stats.error} onRetry={() => void stats.refetch()}/> : <LoadingPanel label="학습 기록을 불러오는 중"/>
      : <><section className="result-summary sheet" aria-labelledby="record-summary-title"><div className="summary-intro"><div><h2 id="record-summary-title">{stats.data.overall.total_question_count}문항 중 {stats.data.overall.graded_question_count}문항 학습</h2><p>저장된 채점 기록 기준 · 진행 중인 시험과 포기한 시험은 제외</p></div><div className="accuracy"><span>정답률</span><strong>{stats.data.overall.accuracy_percent}<small>%</small></strong></div></div>
        <dl className="result-counts"><div><dt>정답</dt><dd className="correct-ink">{stats.data.overall.correct_question_count}</dd></div><div><dt>오답</dt><dd className="incorrect-ink">{stats.data.overall.wrong_question_count}</dd></div><div><dt>아직 미채점</dt><dd>{stats.data.overall.ungraded_question_count}</dd></div></dl>
      </section>
      <section className="records-section" aria-labelledby="subject-record-title"><h2 id="subject-record-title">과목·단원별 기록</h2><div className="sheet records-groups">{stats.data.subjects.map(s => <div key={s.id} className="records-subject"><div className="section-heading"><h3>{s.id}과목 · {s.name}</h3><span>{s.graded_question_count} / {s.total_question_count}문항 · {s.accuracy_percent}%</span></div><table className="score-table"><thead><tr><th scope="col">단원</th><th scope="col">채점</th><th scope="col">정답</th><th scope="col">오답</th></tr></thead><tbody>{stats.data!.chapters.filter(c => c.subject_id === s.id).map(c => <tr key={c.id}><th scope="row">{c.name}</th><td>{c.graded_question_count} / {c.total_question_count}</td><td>{c.correct_question_count}</td><td>{c.wrong_question_count}</td></tr>)}</tbody></table></div>)}</div></section>
      {stats.error && <ErrorNotice error={stats.error} onRetry={() => void stats.refetch()}/>}</>}
    <section className="records-section" aria-labelledby="wrong-title"><div className="section-heading"><h2 id="wrong-title">오답 복습</h2><span className="muted">마지막 채점이 오답인 문항</span></div>
      <div className="sheet study-form"><div className="record-filters"><label>과목<select value={subject} onChange={e => { setSubject(Number(e.target.value)); setChapter(0); }}><option value={0}>전체 과목</option>{catalog.data?.subjects.map(s => <option value={s.id} key={s.id}>{s.id}과목 · {s.name}</option>)}</select></label><label>단원<select value={chapter} onChange={e => setChapter(Number(e.target.value))}><option value={0}>전체 단원</option>{chapters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label></div>
        <div className="review-choice"><label className="checkbox-label"><input type="checkbox" checked={includeDrafts} onChange={e => setIncludeDrafts(e.target.checked)}/><span>검수 대기 문항 포함</span></label><p>검수 대기 문항을 복습하려면 선택해 주세요.</p></div>
        {wrong.isPending ? <LoadingPanel label="오답을 불러오는 중"/> : wrong.error ? <ErrorNotice error={wrong.error} onRetry={() => void wrong.refetch()}/>
          : wrong.data?.items.length ? <div className="record-wrong-list">{wrong.data.items.map(item => <div className="result-row" key={item.question_id}><div><strong>{questionLabel(item.question_key)}</strong><span>{item.chapter_name} · {formatDate(item.last_graded_at)}</span></div><span className={`status-pill ${item.available ? 'incorrect' : 'warning'}`}>{item.available ? '오답' : '검수 대기'}</span></div>)}</div> : <p className="empty-hint">선택한 범위에 오답이 없습니다.</p>}
        {catalog.error && <ErrorNotice error={catalog.error} onRetry={() => void catalog.refetch()}/>}
        {create.error && <ErrorNotice error={create.error}/>}
        <div className="start-row"><p>복습할 문항 <strong>{wrongCount}개</strong></p><button className="button primary" disabled={!wrongCount || create.isPending} onClick={reviewWrong}>{create.isPending ? '복습을 준비하는 중' : '오답 다시 풀기'}<Arrow/></button></div>
      </div>
    </section>
    <section className="records-section" aria-labelledby="mock-history-title"><div className="section-heading"><h2 id="mock-history-title">지난 모의고사</h2><Link className="text-button" href="/#mock-start-title">새 시험 시작<Arrow/></Link></div>
      {history.isPending ? <LoadingPanel label="시험 이력을 불러오는 중"/> : history.error ? <ErrorNotice error={history.error} onRetry={() => void history.refetch()}/>
        : history.data?.items.length ? <div className="session-list">{history.data.items.map(item => {
          const content = <><div className="session-identity"><strong>{formatDate(item.session.started_at)} 모의고사</strong><span>{item.session.status === 'abandoned' ? '직접 포기' : item.session.finish_reason === 'timeout' ? '시간 만료' : '제출 완료'}{item.session.study_filter?.include_drafts && ' · 검수 대기 포함'}</span></div><span className="session-progress">{item.summary ? `${item.summary.score}점 · ${item.summary.passed ? '합격' : '불합격'}` : '채점하지 않음'}</span>{item.summary && <Arrow/>}</>;
          return item.summary ? <Link className="session-row" key={item.session.id} href={`/mock/${item.session.id}/result`}>{content}</Link> : <div className="session-row" key={item.session.id}>{content}</div>;
        })}</div> : <div className="empty-panel"><p>아직 종료한 모의고사가 없습니다.</p><span>시험을 제출하거나 시간이 끝나면 이곳에서 결과를 다시 볼 수 있습니다.</span></div>}
    </section>
  </main></>;
}
