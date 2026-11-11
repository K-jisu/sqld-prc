"use client";

import { AppHeader, ErrorNotice } from "@/components/ui";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return <><AppHeader/><main id="main" className="loading-main"><h1>화면을 불러오지 못했습니다</h1><ErrorNotice error={null} onRetry={reset}/></main></>;
}
