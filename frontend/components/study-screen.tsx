"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { api, keys, questionLabel } from "@/lib/api";
import type { ItemResponse, ItemsResponse, ResultResponse, SessionResponse } from "@/lib/types";
import { useStudyProgress, type StudyProgress } from "@/lib/use-study-progress";
import { AppHeader, Arrow, ErrorNotice, LoadingPanel } from "./ui";
import { ContentBlocks } from "./content-blocks";

function QuestionNav({ data, position, blocked, onNavigate }: { data: SessionResponse; position: number; blocked: boolean; onNavigate: (position: number) => void }) {
  const content = <><div className="nav-count"><strong>{data.session.graded_item_count}</strong><span> / {data.session.item_count}문항 채점</span></div><div className="nav-grid">{data.items.map((row) => <button key={row.item_id} type="button" disabled={blocked} aria-label={`${row.position}번 문항`} aria-current={position === row.position ? 'step' : undefined}
    className={`nav-number ${position === row.position ? 'current' : ''} ${row.graded ? 'graded' : row.answered ? 'answered' : ''}`} onClick={() => onNavigate(row.position)}>{row.position}{row.graded && <span className="graded-dot" aria-label="채점 완료"/>}</button>)}</div>
    <div className="nav-legend"><span><i className="legend-dot"/>채점 완료</span><span>채점 전에는 정오답을 표시하지 않습니다</span></div></>;
  return <aside className="study-sidebar"><div className="desktop-question-nav"><h2>문항 목록</h2>{content}</div><details className="mobile-question-nav"><summary aria-label="문항 목록">문항 목록<span>{position} / {data.session.item_count}</span></summary><div className="mobile-nav-content">{content}</div></details></aside>;
}

function QuestionWorkspace({ data, sessionData, onNavigate, progress }: { data: ItemResponse; sessionData: SessionResponse; onNavigate: (position: number) => void; progress: StudyProgress }) {
  const router = useRouter();
  const client = useQueryClient();
  const dialog = useRef<HTMLDialogElement>(null);
  const { item, session_id: sessionId } = data;
  const closed = sessionData.session.status !== 'active';
  const finish = useMutation({ mutationKey: ['study-action', sessionId], scope: { id: `action:${sessionId}` },
    mutationFn: async () => {
      progress.gradeAll();
      await progress.flush();
      return api<ResultResponse>(`/study-sessions/${sessionId}/finish`, { method: 'POST', body: {} });
    },
    onSuccess: async (response) => {
      client.setQueryData(keys.result(sessionId), response);
      client.setQueryData<SessionResponse>(keys.session(sessionId), (cached) => cached && {
        ...cached, server_now: response.server_now, session: response.result.session,
      });
      client.removeQueries({ queryKey: ['item', sessionId] });
      client.removeQueries({ queryKey: keys.items(sessionId) });
      await client.invalidateQueries({ queryKey: keys.active });
      dialog.current?.close(); router.push(`/study/${sessionId}/result`);
    },
  });
  const blocked = finish.isPending;
  const canEdit = !closed && item.attempt.status === 'draft' && !blocked;
  const selectedOption = item.attempt.selected_option_id;
  const review = item.review;
  const correctNumber = review && item.question.options.find((o) => o.id === review.correct_option_id)?.option_number;
  return <><AppHeader blocked={blocked}><Link className="header-link" href="/" aria-disabled={blocked || undefined} onClick={(event) => { if (blocked) event.preventDefault(); }}>학습 목록<Arrow direction="left"/></Link></AppHeader>
    <main id="main" className="study-main"><div className="study-title"><div><h1>{questionLabel(item.question.question_key)}</h1><p><span className="question-key">{item.question.question_key}</span><span>{closed ? '학습 복습' : `${item.position} / ${sessionData.session.item_count}문항`}</span>{item.question.status === 'draft' && <span className="status-pill warning">검수 대기</span>}</p></div>
      {closed ? <Link className="button secondary" href={`/study/${sessionId}/result`}>결과 보기</Link> : <div className="dialog-actions"><button className="button secondary" disabled={blocked} onClick={() => progress.gradeAll()}>일괄 채점</button><button className="button secondary" disabled={blocked} onClick={() => dialog.current?.showModal()}>학습 종료</button></div>}
    </div><div className="study-grid"><QuestionNav data={sessionData} position={item.position} blocked={blocked} onNavigate={onNavigate}/>
      <div className="question-column"><article className="question-sheet sheet"><div className="question-content"><ContentBlocks blocks={item.question.content_blocks}/></div>
        <fieldset className="options"><legend className="sr-only">보기 선택</legend>{item.question.options.map((option) => {
          const selected = selectedOption === option.id;
          return <label key={option.id} className={`option-row ${selected ? 'selected' : ''} ${review?.correct_option_id === option.id ? 'is-correct' : review && selected && !review.is_correct ? 'is-wrong' : ''}`}>
            <input className="sr-only" type="radio" name={`answer-${item.id}`} aria-label={`${option.option_number}번 보기`} checked={selected} disabled={!canEdit} onChange={() => progress.select(item.id, option.id)}/>
            <span className="option-number">{option.option_number}</span><div className="option-body"><ContentBlocks blocks={option.content_blocks}/></div>
            {review?.correct_option_id === option.id && <span className="option-tag">정답</span>}
          </label>;
        })}</fieldset>
        <div className="answer-toolbar"><span className={`save-status ${progress.error ? 'failed' : ''}`} role="status">{progress.error ? '기록 저장 실패' : progress.saving ? '기록 저장 중…' : progress.unsaved ? '기록 저장 대기 중…' : item.attempt.status === 'graded' ? `${item.attempt.attempt_number}번째 풀이 · 채점 완료` : selectedOption ? '저장됨' : '보기를 선택해 주세요'}</span>
          {canEdit && <button className="text-button" disabled={selectedOption === null} onClick={() => progress.select(item.id, null)}>선택 해제</button>}
        </div>
        {!!progress.error && <div className="save-error"><ErrorNotice error={progress.error} onRetry={() => { void progress.flush().catch(() => {}); }} retryLabel="기록 다시 저장"/></div>}
        {review && <section className={`review-section ${review.is_correct ? 'correct' : 'incorrect'}`} aria-labelledby="review-title"><div className="review-heading"><h2 id="review-title">{review.is_correct ? '정답입니다' : '다시 확인해 보세요'}</h2><span>정답 {correctNumber}번</span></div><ContentBlocks blocks={review.explanation_blocks}/></section>}
        <div className="question-actions"><div className="question-pagination"><button className="button secondary" aria-label="이전 문항" disabled={blocked || item.position === 1} onClick={() => onNavigate(item.position - 1)}><Arrow direction="left"/><span>이전</span></button><button className="button secondary" aria-label="다음 문항" disabled={blocked || item.position === sessionData.session.item_count} onClick={() => onNavigate(item.position + 1)}><span>다음</span><Arrow/></button></div>
          {!closed && (item.attempt.status === 'graded' ? <button className="button primary" disabled={blocked} onClick={() => progress.retry(item.id)}>다시 풀기</button>
            : <button className="button primary" disabled={blocked || selectedOption === null || !item.solution} onClick={() => progress.grade(item.id)}>정답 확인</button>)}
        </div>
      </article><p className="question-footnote">{closed ? '종료한 학습입니다. 당시 채점 기록과 현재 정답·해설을 확인할 수 있습니다.' : '채점과 해설 확인은 즉시 반영됩니다. 답만 고른 뒤 일괄 채점하거나 학습을 종료할 수도 있습니다.'}</p></div>
    </div></main>
    <dialog ref={dialog} className="confirm-dialog" aria-labelledby="finish-title"><h2 id="finish-title">채점하고 학습을 종료할까요?</h2><p>선택한 답안을 한 번에 채점하고 기록을 저장합니다.<br/>답을 고르지 않은 문항은 채점하지 않습니다.</p><p className="muted">종료 후에도 결과와 해설을 확인하거나 같은 범위로 새 학습을 시작할 수 있습니다.</p>{finish.error && <ErrorNotice error={finish.error}/>}
      <div className="dialog-actions"><button className="button secondary" disabled={finish.isPending} onClick={() => dialog.current?.close()}>계속 풀기</button><button className="button primary" disabled={finish.isPending} onClick={() => finish.mutate()}>{finish.isPending ? '기록 저장 후 종료하는 중' : '전체 채점하고 결과 보기'}</button></div>
    </dialog>
  </>;
}

export function StudyScreen({ sessionId, reviewItemId }: { sessionId: string; reviewItemId?: string }) {
  const client = useQueryClient();
  const router = useRouter();
  const navigationVersion = useRef(0);
  const progress = useStudyProgress(sessionId);
  const session = useQuery({ queryKey: keys.session(sessionId), queryFn: async ({ signal }) => progress.overlaySession(await api<SessionResponse>(`/quiz-sessions/${sessionId}`, { signal })) });
  const bank = useQuery({ queryKey: keys.items(sessionId), staleTime: Infinity, refetchOnWindowFocus: 'always', refetchOnReconnect: 'always',
    queryFn: async () => {
      const response = await api<ItemsResponse>(`/quiz-sessions/${sessionId}/items`);
      return progress.hydrate(response);
    } });
  const currentItem = session.data?.session.status === 'completed' && reviewItemId
    ? session.data.items.find((i) => i.item_id === reviewItemId) : session.data?.items.find((i) => i.position === session.data.session.current_position);
  const item = useQuery({ queryKey: keys.item(sessionId, currentItem?.item_id ?? ''), enabled: false,
    staleTime: Infinity,
    queryFn: ({ signal }) => api<ItemResponse>(`/quiz-sessions/${sessionId}/items/${currentItem!.item_id}`, { signal }) });
  const position = useMutation({ scope: { id: `position:${sessionId}` },
    mutationFn: (value: { position: number; version: number }) => api<SessionResponse>(`/quiz-sessions/${sessionId}`, { method: 'PATCH', body: { current_position: value.position } }),
    onSuccess: (data, value) => {
      if (value.version !== navigationVersion.current) return;
      client.setQueryData<SessionResponse>(keys.session(sessionId), cached => cached && { ...cached,
        session: { ...cached.session, current_position: data.session.current_position } });
    } });
  function navigate(value: number) {
    if (session.data?.session.status === 'completed') {
      const target = session.data.items.find((i) => i.position === value);
      if (target) router.replace(`/study/${sessionId}?item=${target.item_id}`);
    } else {
      client.setQueryData<SessionResponse>(keys.session(sessionId), cached => cached && { ...cached,
        session: { ...cached.session, current_position: value } });
      position.mutate({ position: value, version: ++navigationVersion.current });
    }
  }
  async function refresh() {
    const [checked, loaded] = await Promise.all([session.refetch(), bank.refetch()]);
    return !checked.isError && !loaded.isError;
  }
  if (!session.data || !item.data) return <><AppHeader/><main id="main" className="loading-main">{session.error || item.error || bank.error ? <ErrorNotice error={session.error ?? item.error ?? bank.error} onRetry={() => { void bank.refetch(); void refresh(); }}/>
    : session.data && !currentItem ? <div className="empty-panel"><h1>문항을 찾을 수 없습니다</h1><Link className="button secondary" href={`/study/${sessionId}`}>학습으로 돌아가기</Link></div> : <LoadingPanel/>}</main></>;
  return <><QuestionWorkspace key={`${item.data.item.id}:${item.data.item.attempt.id}`} data={item.data} sessionData={session.data} onNavigate={navigate} progress={progress}/>
    {(position.error || session.error || item.error || bank.error) && <div className="floating-error"><ErrorNotice error={position.error ?? session.error ?? item.error ?? bank.error} onRetry={() => { position.reset(); void refresh(); }}/></div>}</>;
}
