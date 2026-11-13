import Link from 'next/link';
import { AppHeader, Arrow } from '@/components/ui';

export const metadata = { title: '학습 자료 | SQLD 연습' };

const materials = [
  { id: 'data-modeling', title: '데이터 모델링', pages: 11,
    description: '식별자·관계·정규화·NULL을 정리하고, 수강 모델과 SQL 결과를 함께 설명합니다.' },
  { id: 'sql', title: 'SQL 핵심', pages: 24,
    description: '기본 함수부터 조인·윈도우 함수·PIVOT까지, 작은 데이터와 결과표로 복습합니다.' },
];

export default function Page() {
  return <><AppHeader><Link className="header-link" href="/">학습 홈<Arrow/></Link></AppHeader>
    <main id="main" className="result-main">
      <div className="page-heading"><h1>학습 자료</h1><p>문제를 풀며 헷갈린 개념을 교정·보충본에서 찾아보세요.</p></div>
      <ul className="materials-list sheet" aria-label="교정·보충 PDF">
        {materials.map((material) => <li className="material-row" key={material.id}>
          <div className="material-description"><h2>{material.title}</h2>
            <p className="muted">{material.pages}쪽 · 교정·보충본 · 2026.11.13</p>
            <p>{material.description}</p></div>
          <div className="study-toolbar material-actions">
            <a className="button" href={`/api/v1/study-materials/${material.id}`} target="_blank" rel="noopener noreferrer">PDF 열기<span className="sr-only"> (새 탭)</span></a>
            <a className="button secondary" href={`/api/v1/study-materials/${material.id}?download=true`}>내려받기</a>
          </div>
        </li>)}
      </ul>
      <p className="materials-note muted">교정 내역과 참고 문서는 각 PDF의 마지막에 있습니다. 새 탭에서 열리지 않으면 내려받아 확인해 주세요.</p>
    </main></>;
}
