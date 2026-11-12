import { Suspense } from 'react';
import { ResultScreen } from '@/components/result-screen';
import { LoadingPanel } from '@/components/ui';

async function Content({ params }: PageProps<'/mock/[sessionId]/result'>) {
  const { sessionId } = await params;
  return <ResultScreen mode="mock" sessionId={sessionId}/>;
}

export default function Page(props: PageProps<'/mock/[sessionId]/result'>) {
  return <Suspense fallback={<main id="main" className="loading-main"><LoadingPanel label="시험 결과를 불러오는 중"/></main>}><Content {...props}/></Suspense>;
}
