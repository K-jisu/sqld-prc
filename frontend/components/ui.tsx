"use client";

import Link from "next/link";
import { ApiError, errorMessage } from "@/lib/api";

export function AppHeader({ children, blocked = false }: { children?: React.ReactNode; blocked?: boolean }) {
  return <header className="app-header"><div className="header-inner">
    <Link className="brand" href="/" aria-label="SQLD 연습 홈" aria-disabled={blocked || undefined} onClick={(event) => { if (blocked) event.preventDefault(); }}>
      <svg width="29" height="29" viewBox="0 0 29 29" fill="none" aria-hidden="true"><path d="M5 4.5h15a3 3 0 0 1 3 3v17H8a3 3 0 0 1-3-3v-17Z" stroke="currentColor" strokeWidth="1.6"/><path d="M5 20.5h18M9.5 9h9M9.5 13h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>
      <span>SQLD 연습</span><span className="brand-caption">내 학습 노트</span>
    </Link>{children}
  </div></header>;
}

export function LoadingPanel({ label = "학습 내용을 불러오는 중" }: { label?: string }) {
  return <div className="loading-panel" aria-busy="true" role="status"><span>{label}</span><div className="skeleton-line"/><div className="skeleton-line short"/><div className="skeleton-line"/></div>;
}

export function ErrorNotice({ error, onRetry, retryLabel = "다시 불러오기" }: { error: unknown; onRetry?: () => void; retryLabel?: string }) {
  const access = error instanceof ApiError && error.code === "ACCESS_CONFIRMATION_REQUIRED";
  return <div className="error-notice" role="alert"><p>{errorMessage(error)}</p>
    {access ? <button className="button secondary small" onClick={() => window.location.reload()}>화면 새로고침</button>
      : onRetry && <button className="button secondary small" onClick={onRetry}>{retryLabel}</button>}
  </div>;
}

export function Arrow({ direction = "right" }: { direction?: "left" | "right" }) {
  return <svg className={direction === "left" ? "arrow left" : "arrow"} width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m7.5 5 5 5-5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}
