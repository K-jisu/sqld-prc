"use client";

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { api, keys } from '@/lib/api';
import type { ActiveSessions, Catalog, SessionResponse } from '@/lib/types';
import { Arrow, ErrorNotice } from './ui';

export function MockStart({ catalog }: { catalog: Catalog }) {
  const router = useRouter();
  const client = useQueryClient();
  const [includeDrafts, setIncludeDrafts] = useState(false);
  const creation = useRef<{ id: string; includeDrafts: boolean } | null>(null);
  const inFlight = useRef(false);
  const active = useQuery({ queryKey: keys.active, queryFn: ({ signal }) => api<ActiveSessions>('/quiz-sessions', { signal }) });
  const current = active.data?.sessions.find(s => s.mode === 'mock');
  const available = (id: number) => { const subject = catalog.subjects.find(s => s.id === id); return subject ? subject.published_question_count + (includeDrafts ? subject.draft_question_count : 0) : 0; };
  const enough = available(1) >= 10 && available(2) >= 40;
  const start = useMutation({
    mutationFn: ({ id, drafts }: { id: string; drafts: boolean }) => api<SessionResponse>(`/mock-sessions/${id}`, { method: 'PUT', body: { include_drafts: drafts } }),
    onSuccess: data => {
      client.setQueryData(keys.session(data.session.id), { ...data, client_received_at: Date.now() });
      void client.invalidateQueries({ queryKey: keys.active });
      router.push(`/mock/${data.session.id}`);
    },
    onError: () => { void client.invalidateQueries({ queryKey: keys.active }); },
    onSettled: () => { inFlight.current = false; },
  });
  function begin() {
    if (inFlight.current || !enough || current) return;
    if (creation.current?.includeDrafts !== includeDrafts) creation.current = { id: crypto.randomUUID(), includeDrafts };
    inFlight.current = true;
    start.mutate({ id: creation.current.id, drafts: includeDrafts });
  }
  return <section className="study-form sheet mock-start" aria-labelledby="mock-start-title">
    <div className="section-heading"><h2 id="mock-start-title">모의고사</h2><span className="muted">50문항 · 90분</span></div>
    <p>1과목 10문항과 2과목 40문항을 무작위로 출제합니다. 제출하거나 시간이 끝나면 한 번에 채점합니다.</p>
    <p className="muted">총점 60점 이상, 1과목 8점·2과목 32점 이상이면 합격입니다. 시작 버튼을 누르면 시간이 흐릅니다.</p>
    <div className="review-choice"><label className="checkbox-label"><input type="checkbox" checked={includeDrafts} disabled={start.isPending} onChange={e => setIncludeDrafts(e.target.checked)}/><span>미검수 문항도 출제</span></label><p>검수 대기 문항도 포함하며 문항의 검수 상태는 바뀌지 않습니다.</p></div>
    {current ? <div className="start-row"><p>진행 중인 모의고사가 있습니다.</p><Link className="button primary" href={`/mock/${current.id}`}>모의고사 이어풀기<Arrow/></Link></div>
      : <div className="start-row"><p className="muted">{enough ? '1과목 10문항 · 2과목 40문항' : '각 과목의 문항 수가 부족합니다. 미검수 포함 여부를 확인해 주세요.'}</p><button className="button primary" disabled={!enough || start.isPending || active.isPending || active.isError} onClick={begin}>{start.isPending ? '시험을 준비하는 중' : '50문항 모의고사 시작'}<Arrow/></button></div>}
    {start.error && <ErrorNotice error={start.error}/>}
    {active.error && <ErrorNotice error={active.error} onRetry={() => void active.refetch()}/>}
  </section>;
}
