import { Suspense } from "react";
import { StudyScreen } from "@/components/study-screen";
import { LoadingPanel } from "@/components/ui";

async function Content({ params, searchParams }: PageProps<"/study/[sessionId]">) {
  const [{ sessionId }, search] = await Promise.all([params, searchParams]);
  return <StudyScreen sessionId={sessionId} reviewItemId={typeof search.item === 'string' ? search.item : undefined}/>;
}

export default function Page(props: PageProps<"/study/[sessionId]">) {
  return <Suspense fallback={<main id="main" className="loading-main"><LoadingPanel/></main>}><Content {...props}/></Suspense>;
}
