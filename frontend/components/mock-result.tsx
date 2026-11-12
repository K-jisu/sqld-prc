"use client";

import Link from 'next/link';
import { questionLabel } from '@/lib/api';
import type { MockResult } from '@/lib/types';
import { AppHeader, Arrow, ErrorNotice } from './ui';

export function MockResultView({ data, busy, error, reloadError, onReload, onRestart }: {
  data: MockResult; busy: boolean; error: unknown; reloadError: unknown; onReload: () => void; onRestart: () => void;
}) {
  const { session, summary, items } = data;
  return <><AppHeader><nav className="study-toolbar"><Link className="header-link" href="/records">내 기록<Arrow/></Link><Link className="header-link" href="/">학습 목록<Arrow direction="left"/></Link></nav></AppHeader><main id="main" className="result-main">
    <div className="page-heading"><h1>모의고사 결과</h1><p>{session.finish_reason === 'timeout' ? '90분이 지나 시간 만료 기준으로 채점했습니다.' : '제출한 답안으로 전체 문항을 채점했습니다.'}</p></div>
    <section className="result-summary sheet" aria-labelledby="mock-result-title"><div className="summary-intro"><div><h2 id="mock-result-title" className={summary.passed ? 'correct-ink' : 'incorrect-ink'}>{summary.passed ? '합격' : '불합격'}</h2><p>50문항{session.study_filter?.include_drafts && ' · 검수 대기 포함'}</p></div><div className="accuracy"><span>총점</span><strong>{summary.score}<small> / 100</small></strong></div></div>
      <dl className="result-counts mock-result-counts"><div><dt>정답</dt><dd className="correct-ink">{summary.correct_item_count}</dd></div><div><dt>오답</dt><dd className="incorrect-ink">{summary.incorrect_item_count}</dd></div><div><dt>선택</dt><dd>{summary.answered_item_count}</dd></div><div><dt>미응답</dt><dd>{summary.unanswered_item_count}</dd></div></dl>
      <table className="score-table"><thead><tr><th scope="col">과목</th><th scope="col">정답</th><th scope="col">점수</th><th scope="col">과락</th></tr></thead><tbody>{summary.subjects.map(s => <tr key={s.subject_id}><th scope="row">{s.subject_id}과목</th><td>{s.correct_item_count} / {s.item_count}</td><td>{s.score} / {s.max_score}</td><td className={s.failed ? 'incorrect-ink' : 'correct-ink'}>{s.failed ? '과락' : '통과'}</td></tr>)}</tbody></table>
      <p className="result-note">총점 60점 이상이며 1과목 8점·2과목 32점 이상이어야 합격입니다. 미응답은 오답에 포함됩니다.</p>
    </section>
    <section className="result-list-section" aria-labelledby="mock-review-title"><div className="section-heading"><h2 id="mock-review-title">문항별 결과·해설</h2><span className="muted">문항을 눌러 복습합니다</span></div><div className="result-list sheet">{items.map(item => <Link key={item.item_id} href={`/mock/${session.id}?item=${item.item_id}`} className="result-row"><div><strong>{item.position}번 · {questionLabel(item.question_key)}</strong><span className="question-key">{item.question_key}</span></div><span className={`status-pill ${item.outcome?.is_correct ? 'correct' : 'incorrect'}`}>{item.outcome?.is_correct ? '정답' : item.outcome?.selected_option_id ? '오답' : '미응답'}</span><Arrow/></Link>)}</div></section>
    {!!reloadError && <ErrorNotice error={reloadError} onRetry={onReload}/>} {!!error && <ErrorNotice error={error}/>}
    <div className="result-actions"><Link className="button secondary" href="/">학습 목록으로</Link><button className="button primary" disabled={busy} onClick={onRestart}>{busy ? '학습을 준비하는 중' : '같은 문제로 학습'}<Arrow/></button></div>
  </main></>;
}
