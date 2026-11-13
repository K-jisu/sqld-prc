"use client";

const images = new Map<string, string>();

export function cacheQuestionImages(assets: Record<string, string>) {
  for (const [src, data] of Object.entries(assets)) images.set(src, data);
}

export function questionImage(src: string) {
  return images.get(src) ?? src;
}
