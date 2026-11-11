"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useIsMutating, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, keys, questionLabel } from "@/lib/api";
import type { GradeResponse, ItemResponse, ResultResponse, RetryResponse, SessionResponse } from "@/lib/types";
import { useAnswerSave } from "@/lib/use-answer-save";
import { AppHeader, Arrow, ErrorNotice, LoadingPanel } from "./ui";
import { ContentBlocks } from "./content-blocks";

function QuestionNav({ data, position, blocked, onNavigate }: { data: SessionResponse; position: number; blocked: boolean; onNavigate: (position: number) => void }) {
  const content = <><div className="nav-count"><strong>{data.session.graded_item_count}</strong><span> / {data.session.item_count}문항 채점</span></div><div className="nav-grid">{data.items.map((row) => <button key={row.item_id} type="button" disabled={blocked} aria-label={`${row.position}번 문항`} aria-current={position === row.position ? 'step' : undefined}
    className={`nav-number ${position === row.position ? 'current' : ''} ${row.graded ? 'graded' : row.answered ? 'answered' : ''}`} onClick={() => onNavigate(row.position)}>{row.position}{row.graded && <span className="graded-dot" aria-label="채점 완료"/>}</button>)}</div>
    <div className="nav-legend"><span><i className="legend-dot"/>채점 완료</span><span>채점 전에는 정오답을 표시하지 않습니다</span></div></>;
  return <aside className="study-sidebar"><div className="desktop-question-nav"><h2>문항 목록</h2>{content}</div><details className="mobile-question-nav"><summary aria-label="문항 목록">문항 목록<span>{position} / {data.session.item_count}</span></summary><div className="mobile-nav-content">{content}</div></details></aside>;
}

function QuestionWorkspace({ data, sessionData, onNavigate, navigating, syncFailed, refresh }: { data: ItemResponse; sessionData: SessionResponse; onNavigate: (position: number) => void; navigating: boolean; syncFailed: boolean; refresh: () => Promise<boolean> }) {
  const router = useRouter();
  const client = useQueryClient();
  const dialog = useRef<HTMLDialogElement>(null);
  const { item, session_id: sessionId } = data;
  const path = `/quiz-sessions/${sessionId}/items/${item.id}`;
  const saver = useAnswerSave(data);
  const actionCount = useIsMutating({ mutationKey: ['study-action', sessionId] });
  const closed = sessionData.session.status !== 'active';
  const update = async () => { await Promise.all([refresh(), client.invalidateQueries({ queryKey: keys.active })]); };
  const grade = useMutation({ mutationKey: ['study-action', sessionId], scope: { id: `action:${sessionId}` },
    mutationFn: () => api<GradeResponse>(path + '/grade', { method: 'POST', body: { attempt_id: item.attempt.id } }),
    onSuccess: async (response) => {
      client.setQueryData<ItemResponse>(keys.item(sessionId, item.id), (cached) => !cached || cached.item.attempt.id !== response.attempt.id ? cached
        : { ...cached, item: { ...cached.item, attempt: response.attempt, review: response.review } });
      await update();
    } });
  const retry = useMutation({ mutationKey: ['study-action', sessionId], scope: { id: `action:${sessionId}` },
    mutationFn: () => api<RetryResponse>(path + '/retry', { method: 'POST', body: { previous_attempt_id: item.attempt.id } }),
    onSuccess: async (response) => {
      client.setQueryData<ItemResponse>(keys.item(sessionId, item.id), (cached) => !cached || cached.item.attempt.id !== item.attempt.id ? cached
        : { ...cached, item: { ...cached.item, attempt: response.attempt, review: null } });
      await update();
    } });
  const finish = useMutation({ mutationKey: ['study-action', sessionId], scope: { id: `action:${sessionId}` },
    mutationFn: () => api<ResultResponse>(`/study-sessions/${sessionId}/finish`, { method: 'POST', body: {} }),
    onSuccess: async (response) => {
      client.setQueryData(keys.result(sessionId), response);
      client.setQueryData<SessionResponse>(keys.session(sessionId), (cached) => cached && {
        ...cached, server_now: response.server_now, session: response.result.session,
      });
      client.removeQueries({ queryKey: ['item', sessionId] });
      await client.invalidateQueries({ queryKey: keys.active });
      dialog.current?.close(); router.push(`/study/${sessionId}/result`);
    },
  });
  const failure = grade.error ?? retry.error;
  const blocked = saver.saving || saver.unsaved || saver.restoring || navigating || actionCount > 0 || syncFailed || !!failure;
  const canEdit = !closed && item.attempt.status === 'draft' && actionCount === 0 && !navigating && !saver.restoring && !syncFailed && !failure;
  async function recheck() { if (await refresh()) { grade.reset(); retry.reset(); } }
  useEffect(() => {
    if (!blocked) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [blocked]);
  const review = retry.isPending || retry.error || syncFailed ? null : item.review;
  const correctNumber = review && item.question.options.find((o) => o.id === review.correct_option_id)?.option_number;
  return <><AppHeader blocked={blocked}><Link className="header-link" href="/" aria-disabled={blocked || undefined} onClick={(event) => { if (blocked) event.preventDefault(); }}>학습 목록<Arrow direction="left"/></Link></AppHeader>
    <main id="main" className="study-main"><div className="study-title"><div><h1>{questionLabel(item.question.question_key)}</h1><p><span className="question-key">{item.question.question_key}</span><span>{closed ? '학습 복습' : `${item.position} / ${sessionData.session.item_count}문항`}</span>{item.question.status === 'draft' && <span className="status-pill warning">검수 대기</span>}</p></div>
      {closed ? <Link className="button secondary" href={`/study/${sessionId}/result`}>결과 보기</Link> : <button className="button secondary" disabled={blocked} onClick={() => dialog.current?.showModal()}>학습 종료</button>}
    </div><div className="study-grid"><QuestionNav data={sessionData} position={item.position} blocked={blocked} onNavigate={onNavigate}/>
      <div className="question-column"><article className="question-sheet sheet"><div className="question-content"><ContentBlocks blocks={item.question.content_blocks}/></div>
        <fieldset className="options"><legend className="sr-only">보기 선택</legend>{item.question.options.map((option) => {
          const selected = saver.selected === option.id;
          return <label key={option.id} className={`option-row ${selected ? 'selected' : ''} ${review?.correct_option_id === option.id ? 'is-correct' : review && selected && !review.is_correct ? 'is-wrong' : ''}`}>
            <input className="sr-only" type="radio" name={`answer-${item.id}`} aria-label={`${option.option_number}번 보기`} checked={selected} disabled={!canEdit} onChange={() => saver.save(option.id)}/>
            <span className="option-number">{option.option_number}</span><div className="option-body"><ContentBlocks blocks={option.content_blocks}/></div>
            {review?.correct_option_id === option.id && <span className="option-tag">정답</span>}
          </label>;
        })}</fieldset>
        <div className="answer-toolbar"><span className={`save-status ${saver.error ? 'failed' : ''}`} role="status">{saver.restoring ? '서버 답안 확인 중…' : saver.saving ? '저장 중…' : saver.error ? '저장되지 않음' : syncFailed ? '서버 상태를 다시 확인해 주세요' : navigating ? '서버 상태 확인 중…' : item.attempt.status === 'graded' ? `${item.attempt.attempt_number}번째 풀이 · 채점 완료` : saver.selected ? '저장됨' : '보기를 선택해 주세요'}</span>
          {canEdit && <button className="text-button" disabled={saver.saving || saver.selected === null} onClick={() => saver.save(null)}>선택 해제</button>}
        </div>
        {!!saver.error && <div className="save-error"><ErrorNotice error={saver.error} onRetry={saver.restoring ? undefined : saver.retry} retryLabel="다시 저장"/><button className="text-button" disabled={saver.restoring} onClick={() => void saver.restore()}>서버 답안 다시 확인</button></div>}
        {failure && <ErrorNotice error={failure} onRetry={() => void recheck()}/>}
        {review && <section className={`review-section ${review.is_correct ? 'correct' : 'incorrect'}`} aria-labelledby="review-title"><div className="review-heading"><h2 id="review-title">{review.is_correct ? '정답입니다' : '다시 확인해 보세요'}</h2><span>정답 {correctNumber}번</span></div><ContentBlocks blocks={review.explanation_blocks}/></section>}
        <div className="question-actions"><div className="question-pagination"><button className="button secondary" aria-label="이전 문항" disabled={blocked || item.position === 1} onClick={() => onNavigate(item.position - 1)}><Arrow direction="left"/><span>이전</span></button><button className="button secondary" aria-label="다음 문항" disabled={blocked || item.position === sessionData.session.item_count} onClick={() => onNavigate(item.position + 1)}><span>다음</span><Arrow/></button></div>
          {!closed && (item.attempt.status === 'graded' ? <button className="button primary" disabled={blocked} onClick={() => retry.mutate()}>{retry.isPending ? '새 풀이를 준비하는 중' : '다시 풀기'}</button>
            : <button className="button primary" disabled={blocked || saver.selected === null} onClick={() => grade.mutate()}>{grade.isPending ? '채점하는 중' : '정답 확인'}</button>)}
        </div>
      </article><p className="question-footnote">{closed ? '종료한 학습입니다. 당시 채점 기록과 현재 정답·해설을 확인할 수 있습니다.' : '답안 저장을 확인한 뒤 채점합니다. 마지막 문항도 직접 학습을 종료해 주세요.'}</p></div>
    </div></main>
    <dialog ref={dialog} className="confirm-dialog" aria-labelledby="finish-title"><h2 id="finish-title">학습을 종료할까요?</h2><p>{sessionData.session.item_count}문항 중 {sessionData.session.graded_item_count}문항을 채점했습니다.<br/>미채점 문항은 오답으로 처리하지 않습니다.</p><p className="muted">종료 후에도 결과와 해설을 확인하거나 같은 범위로 새 학습을 시작할 수 있습니다.</p>{finish.error && <ErrorNotice error={finish.error}/>}
      <div className="dialog-actions"><button className="button secondary" disabled={finish.isPending} onClick={() => dialog.current?.close()}>계속 풀기</button><button className="button primary" disabled={finish.isPending} onClick={() => finish.mutate()}>{finish.isPending ? '종료하는 중' : '종료하고 결과 보기'}</button></div>
    </dialog>
  </>;
}

export function StudyScreen({ sessionId, reviewItemId }: { sessionId: string; reviewItemId?: string }) {
  const client = useQueryClient();
  const router = useRouter();
  const session = useQuery({ queryKey: keys.session(sessionId), queryFn: ({ signal }) => api<SessionResponse>(`/quiz-sessions/${sessionId}`, { signal }) });
  const currentItem = session.data?.session.status === 'completed' && reviewItemId
    ? session.data.items.find((i) => i.item_id === reviewItemId) : session.data?.items.find((i) => i.position === session.data.session.current_position);
  const item = useQuery({ queryKey: keys.item(sessionId, currentItem?.item_id ?? ''), enabled: !!currentItem,
    queryFn: ({ signal }) => api<ItemResponse>(`/quiz-sessions/${sessionId}/items/${currentItem!.item_id}`, { signal }) });
  const position = useMutation({ mutationFn: (value: number) => api<SessionResponse>(`/quiz-sessions/${sessionId}`, { method: 'PATCH', body: { current_position: value } }),
    onSuccess: (data) => { client.setQueryData(keys.session(sessionId), data); } });
  function navigate(value: number) {
    if (session.data?.session.status === 'completed') {
      const target = session.data.items.find((i) => i.position === value);
      if (target) router.replace(`/study/${sessionId}?item=${target.item_id}`);
    } else position.mutate(value);
  }
  async function refresh() {
    const checked = await session.refetch();
    if (checked.isError) return false;
    if (!currentItem) return true;
    return !(await item.refetch()).isError;
  }
  if (!session.data || !item.data) return <><AppHeader/><main id="main" className="loading-main">{session.error || item.error ? <ErrorNotice error={session.error ?? item.error} onRetry={() => void refresh()}/>
    : session.data && !currentItem ? <div className="empty-panel"><h1>문항을 찾을 수 없습니다</h1><Link className="button secondary" href={`/study/${sessionId}`}>학습으로 돌아가기</Link></div> : <LoadingPanel/>}</main></>;
  return <><QuestionWorkspace key={`${item.data.item.id}:${item.data.item.attempt.id}`} data={item.data} sessionData={session.data} navigating={position.isPending || session.isFetching || item.isFetching} syncFailed={session.isError || item.isError || position.isError} onNavigate={navigate} refresh={refresh}/>
    {(position.error || session.error || item.error) && <div className="floating-error"><ErrorNotice error={position.error ?? session.error ?? item.error} onRetry={() => { position.reset(); void refresh(); }}/></div>}</>;
}
