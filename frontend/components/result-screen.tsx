"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { api, keys, questionLabel } from "@/lib/api";
import type { ResultResponse, SessionResponse } from "@/lib/types";
import { AppHeader, Arrow, ErrorNotice, LoadingPanel } from "./ui";

export function ResultScreen({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const creationId = useRef<string | null>(null);
  const result = useQuery({ queryKey: keys.result(sessionId), queryFn: ({ signal }) => api<ResultResponse>(`/quiz-sessions/${sessionId}/result`, { signal }) });
  const restart = useMutation({
    mutationFn: () => {
      creationId.current ??= crypto.randomUUID();
      return api<SessionResponse>(`/study-sessions/${creationId.current}`, { method: 'PUT', body: {
        scope: 'previous_session', previous_session_id: sessionId, include_drafts: result.data?.result.session.study_filter.include_drafts ?? false,
      } });
    },
    onSuccess: async (data) => {
      client.setQueryData(keys.session(data.session.id), data);
      await client.invalidateQueries({ queryKey: keys.active });
      router.push(`/study/${data.session.id}`);
    },
  });
  if (!result.data) return <><AppHeader/><main id="main" className="loading-main">{result.error ? <><ErrorNotice error={result.error} onRetry={() => void result.refetch()}/><Link className="text-button" href={`/study/${sessionId}`}>학습으로 돌아가기</Link></> : <LoadingPanel label="학습 결과를 불러오는 중"/>}</main></>;
  const { summary, items, session } = result.data.result;
  return <><AppHeader><Link className="header-link" href="/">학습 목록<Arrow direction="left"/></Link></AppHeader><main id="main" className="result-main">
    <div className="page-heading"><h1>학습 결과</h1><p>마지막으로 채점한 답안을 기준으로 정리했습니다.</p></div>
    <section className="result-summary sheet" aria-labelledby="summary-title"><div className="summary-intro"><div><h2 id="summary-title">{summary.graded_item_count ? `${summary.graded_item_count}문항을 풀었습니다` : '아직 채점한 문항이 없습니다'}</h2><p>전체 {summary.item_count}문항{session.study_filter.include_drafts && ' · 검수 대기 포함'}</p></div><div className="accuracy"><span>채점 문항 정답률</span><strong>{summary.accuracy_percent.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}<small>%</small></strong></div></div>
      <dl className="result-counts"><div><dt>정답</dt><dd className="correct-ink">{summary.correct_item_count}<span>문항</span></dd></div><div><dt>오답</dt><dd className="incorrect-ink">{summary.incorrect_item_count}<span>문항</span></dd></div><div><dt>미채점</dt><dd>{summary.ungraded_item_count}<span>문항</span></dd></div></dl>
      <p className="result-note">미채점 문항은 오답에 포함하지 않습니다. 다시 풀기를 시작했어도 이전에 채점한 답안이 있으면 그 결과를 사용합니다.</p>
    </section>
    <section className="result-list-section" aria-labelledby="review-list-title"><div className="section-heading"><h2 id="review-list-title">문항별 결과</h2><span className="muted">문항을 누르면 풀이를 다시 볼 수 있습니다</span></div><div className="result-list sheet">
      {items.map((item) => <Link href={`/study/${sessionId}?item=${item.item_id}`} key={item.item_id} className="result-row"><div><strong>{questionLabel(item.question_key)}</strong><span className="question-key">{item.question_key}</span></div><span className={`status-pill ${item.outcome ? item.outcome.is_correct ? 'correct' : 'incorrect' : ''}`}>{item.outcome ? item.outcome.is_correct ? '정답' : '오답' : '미채점'}</span><Arrow/></Link>)}
    </div></section>
    {result.error && <ErrorNotice error={result.error} onRetry={() => void result.refetch()}/>}
    {restart.error && <ErrorNotice error={restart.error}/>}
    <div className="result-actions"><Link className="button secondary" href="/">학습 목록으로</Link><button className="button primary" disabled={restart.isPending} onClick={() => restart.mutate()}>{restart.isPending ? '새 학습을 준비하는 중' : '같은 범위 다시 학습'}<Arrow/></button></div>
  </main></>;
}
