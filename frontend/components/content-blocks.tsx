"use client";

/* eslint-disable @next/next/no-img-element -- 교재 이미지는 보호된 API로 직접 요청한다. */

import { useRef } from "react";
import type { Block } from "@/lib/types";

function ContentImage({ src, alt }: { src: string; alt: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  if (!/^\/api\/v1\/question-assets\/S[12]-Q\d{3}\/[A-Za-z0-9_-][A-Za-z0-9_.-]*\.(svg|png|jpg|jpeg|webp)$/.test(src)) return <p className="muted">그림 경로를 확인할 수 없습니다.</p>;
  return <figure className="content-image">
    <button type="button" className="image-preview" onClick={() => dialog.current?.showModal()} aria-label={`그림 크게 보기: ${alt}`}>
      {/* 보호된 API 이미지를 Next 이미지 캐시로 복사하지 않는다. */}
      <img src={src} alt={alt} loading="lazy"/>
      <span className="image-hint">그림 크게 보기</span>
    </button>
    <dialog ref={dialog} className="image-dialog" aria-label={alt}><div className="dialog-heading"><h2>{alt}</h2><button className="button secondary" onClick={() => dialog.current?.close()}>닫기</button></div>
      <div className="image-scroll"><img src={src} alt={alt}/></div>
    </dialog>
  </figure>;
}

export function ContentBlocks({ blocks }: { blocks: Block[] }) {
  return <div className="content-blocks">{blocks.map((block, index) => block.type === "image"
    ? <ContentImage key={`${index}:${block.src}`} src={block.src} alt={block.alt}/>
    : block.type === "sql" ? <pre className="sql-block" key={index}><code>{block.text}</code></pre>
      : <p className="text-block" key={index}>{block.text}</p>)}</div>;
}
