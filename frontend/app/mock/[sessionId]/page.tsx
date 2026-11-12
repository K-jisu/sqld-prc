import { Suspense } from 'react';
import { StudyScreen } from '@/components/study-screen';
import { LoadingPanel } from '@/components/ui';

async function Content({ params, searchParams }: PageProps<'/mock/[sessionId]'>) {
  const [{ sessionId }, search] = await Promise.all([params, searchParams]);
  return <StudyScreen mode="mock" sessionId={sessionId} reviewItemId={typeof search.item === 'string' ? search.item : undefined}/>;
}

export default function Page(props: PageProps<'/mock/[sessionId]'>) {
  return <Suspense fallback={<main id="main" className="loading-main"><LoadingPanel label="모의고사를 불러오는 중"/></main>}><Content {...props}/></Suspense>;
}
