"use client";

import { useIsMutating, useMutation, useMutationState, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, ApiError, keys } from './api';
import type { ItemResponse, ItemsResponse, SessionResponse } from './types';
import { cacheQuestionImages } from './question-images';

type Entry = {
  item_id: string; attempt_id: string; attempt_number: number; selected_option_id: string | null;
  graded: boolean; graded_at: string | null; change_id: string;
};
type Pending = Record<string, Entry>;
const timers = new Map<string, ReturnType<typeof setTimeout>>();
const progressKey = (id: string) => ['study-progress', id] as const;
const storageKey = (id: string) => `sqld-study-progress:${id}`;

export function useStudyProgress(sessionId: string, mode: 'study' | 'mock' = 'study') {
  const client = useQueryClient();
  const [storageError, setStorageError] = useState<unknown>(null);
  const saving = useIsMutating({ mutationKey: ['study-sync', sessionId] }) > 0;
  const writes = useMutationState({ filters: { mutationKey: ['study-sync', sessionId] },
    select: m => ({ status: m.state.status, error: m.state.error }) });
  const sync = useMutation({
    mutationKey: ['study-sync', sessionId], scope: { id: `study-sync:${sessionId}` }, gcTime: Infinity,
    mutationFn: (entries: Entry[]) => api<{ server_now: string; saved_attempt_ids: string[] }>(`/${mode === 'mock' ? 'mock' : 'study'}-sessions/${sessionId}/progress`, {
      method: 'POST', body: { answers: entries.map(e => ({ item_id: e.item_id, attempt_id: e.attempt_id,
        attempt_number: e.attempt_number, selected_option_id: e.selected_option_id, graded: e.graded })) },
    }),
    onSuccess: (_, entries) => {
      const remaining = { ...pending() };
      for (const entry of entries) if (remaining[entry.attempt_id]?.change_id === entry.change_id) delete remaining[entry.attempt_id];
      persist(remaining);
      if (!Object.keys(remaining).length) setStorageError(null);
      void client.invalidateQueries({ queryKey: ['records'] });
    },
  });

  function pending(): Pending {
    const cached = client.getQueryData<Pending>(progressKey(sessionId));
    if (cached) return cached;
    let value: Pending = {};
    try { value = JSON.parse(localStorage.getItem(storageKey(sessionId)) ?? '{}') as Pending; }
    catch { value = {}; }
    client.setQueryData(progressKey(sessionId), value);
    return value;
  }

  function persist(value: Pending) {
    client.setQueryData(progressKey(sessionId), value);
    try {
      if (Object.keys(value).length) localStorage.setItem(storageKey(sessionId), JSON.stringify(value));
      else localStorage.removeItem(storageKey(sessionId));
      setStorageError(null);
    } catch { setStorageError(new ApiError('LOCAL_SAVE_FAILED', '기기에 기록을 저장하지 못했습니다. 기록 저장을 다시 시도해 주세요.')); }
  }

  function schedule() {
    clearTimeout(timers.get(sessionId));
    timers.set(sessionId, setTimeout(() => {
      timers.delete(sessionId);
      const entries = Object.values(pending());
      if (entries.length) sync.mutate(entries);
    }, 1000));
  }

  function overlaySession(data: SessionResponse): SessionResponse {
    if (data.session.status !== 'active') return data;
    const entries = Object.values(pending());
    const items = data.items.map(row => {
      const cached = client.getQueryData<ItemResponse>(keys.item(sessionId, row.item_id));
      const local = entries.filter(e => e.item_id === row.item_id).sort((a, b) => b.attempt_number - a.attempt_number);
      return { ...row, answered: cached ? cached.item.attempt.selected_option_id !== null : local[0] ? local[0].selected_option_id !== null : row.answered,
        graded: row.graded || cached?.item.attempt.status === 'graded' || local.some(e => e.graded) };
    });
    return { ...data, items, session: { ...data.session, answered_item_count: items.filter(i => i.answered).length,
      graded_item_count: items.filter(i => i.graded).length } };
  }

  function hydrate(response: ItemsResponse): ItemsResponse {
    cacheQuestionImages(response.assets ?? {});
    client.setQueryDefaults(['item', sessionId], { staleTime: Infinity, gcTime: Infinity });
    const entries = Object.values(pending());
    const items = response.items.map(original => {
      let item = original;
      if (response.session_status === 'active') {
        const local = entries.filter(e => e.item_id === item.id).sort((a, b) => b.attempt_number - a.attempt_number)[0];
        if (local && local.attempt_number >= item.attempt.attempt_number
          && !(item.attempt.status === 'graded' && local.attempt_id === item.attempt.id)) {
          item = { ...item, attempt: { id: local.attempt_id, attempt_number: local.attempt_number,
            selected_option_id: local.selected_option_id, status: local.graded ? 'graded' : 'draft', graded_at: local.graded_at },
            review: local.graded && item.solution ? { ...item.solution, is_correct: local.selected_option_id === item.solution.correct_option_id } : null };
        }
      }
      client.setQueryData<ItemResponse>(keys.item(sessionId, item.id), { server_now: response.server_now,
        session_id: sessionId, session_status: response.session_status, item });
      return item;
    });
    client.setQueryData<SessionResponse>(keys.session(sessionId), previous => previous && overlaySession(previous));
    if (mode === 'mock' && response.session_status !== 'active') persist({});
    if (response.session_status === 'active' && entries.length) schedule();
    return { ...response, items };
  }

  function change(item: ItemResponse['item']) {
    const entry: Entry = { item_id: item.id, attempt_id: item.attempt.id, attempt_number: item.attempt.attempt_number,
      selected_option_id: item.attempt.selected_option_id, graded: item.attempt.status === 'graded',
      graded_at: item.attempt.graded_at, change_id: crypto.randomUUID() };
    persist({ ...pending(), [entry.attempt_id]: entry });
    client.setQueryData<ItemResponse>(keys.item(sessionId, item.id), previous => previous && { ...previous, item });
    client.setQueryData<ItemsResponse>(keys.items(sessionId), previous => previous && {
      ...previous, items: previous.items.map(row => row.id === item.id ? item : row),
    });
    client.setQueryData<SessionResponse>(keys.session(sessionId), previous => previous && overlaySession(previous));
    schedule();
  }

  function select(itemId: string, optionId: string | null) {
    const data = client.getQueryData<ItemResponse>(keys.item(sessionId, itemId));
    if (!data || data.session_status !== 'active' || data.item.attempt.status !== 'draft') return;
    change({ ...data.item, attempt: { ...data.item.attempt, selected_option_id: optionId } });
  }

  function grade(itemId: string) {
    if (mode !== 'study') return;
    const data = client.getQueryData<ItemResponse>(keys.item(sessionId, itemId));
    if (!data || data.session_status !== 'active' || data.item.attempt.status !== 'draft'
      || !data.item.attempt.selected_option_id || !data.item.solution) return;
    change({ ...data.item, attempt: { ...data.item.attempt, status: 'graded', graded_at: new Date().toISOString() },
      review: { ...data.item.solution, is_correct: data.item.attempt.selected_option_id === data.item.solution.correct_option_id } });
  }

  function retry(itemId: string) {
    if (mode !== 'study') return;
    const data = client.getQueryData<ItemResponse>(keys.item(sessionId, itemId));
    if (!data || data.session_status !== 'active' || data.item.attempt.status !== 'graded') return;
    change({ ...data.item, attempt: { id: crypto.randomUUID(), attempt_number: data.item.attempt.attempt_number + 1,
      selected_option_id: null, status: 'draft', graded_at: null }, review: null });
  }

  function gradeAll() {
    if (mode !== 'study') return;
    const data = client.getQueryData<SessionResponse>(keys.session(sessionId));
    if (data?.session.status === 'active') for (const item of data.items) grade(item.item_id);
  }

  async function flush() {
    clearTimeout(timers.get(sessionId));
    timers.delete(sessionId);
    let entries = Object.values(pending());
    while (entries.length) {
      await sync.mutateAsync(entries);
      entries = Object.values(pending());
    }
  }

  return { hydrate, overlaySession, select, grade, retry, gradeAll, flush, saving, discard: () => persist({}),
    unsaved: Object.keys(client.getQueryData<Pending>(progressKey(sessionId)) ?? {}).length > 0,
    error: storageError ?? (writes.at(-1)?.status === 'error' ? writes.at(-1)?.error : null) };
}

export type StudyProgress = ReturnType<typeof useStudyProgress>;
