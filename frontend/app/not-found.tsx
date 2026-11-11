import Link from "next/link";
import { AppHeader } from "@/components/ui";

export default function NotFound() {
  return <><AppHeader/><main id="main" className="loading-main"><h1>화면을 찾을 수 없습니다</h1><p className="muted">학습 목록에서 이어 풀기를 선택해 주세요.</p><Link className="button secondary" href="/">학습 목록으로</Link></main></>;
}
