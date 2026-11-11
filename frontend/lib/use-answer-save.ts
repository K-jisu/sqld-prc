"use client";

import { useIsMutating, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, ApiError, keys } from "./api";
import type { ItemResponse } from "./types";

export function useAnswerSave(data: ItemResponse) {
  const client = useQueryClient();
  const { session_id: sessionId, item } = data;
  const sequence = useRef(0);
  const [intent, setIntent] = useState<{ attemptId: string; optionId: string | null } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [restoring, setRestoring] = useState(false);
  const restoringNow = useRef(false);
  const itemKey = keys.item(sessionId, item.id);
  const saving = useIsMutating({ mutationKey: ["save", sessionId] }) > 0;
  const mutation = useMutation({
    mutationKey: ["save", sessionId, item.id], scope: { id: `answer:${sessionId}:${item.id}` },
    mutationFn: (value: { attemptId: string; optionId: string | null; sequence: number }) => api<ItemResponse>(
      `/quiz-sessions/${sessionId}/items/${item.id}/answer`, { method: "PATCH", body: { attempt_id: value.attemptId, selected_option_id: value.optionId } }),
    onSuccess: async (response, value) => {
      if (value.sequence !== sequence.current) return;
      const cached = client.getQueryData<ItemResponse>(itemKey);
      if (!cached || cached.item.attempt.id === response.item.attempt.id) client.setQueryData(itemKey, response);
      setIntent(null); setError(null);
      await Promise.all([client.invalidateQueries({ queryKey: itemKey }), client.invalidateQueries({ queryKey: keys.session(sessionId) }), client.invalidateQueries({ queryKey: keys.active })]);
    },
    onError: (failure, value) => {
      if (value.sequence !== sequence.current) return;
      setError(failure);
      if (failure instanceof ApiError && ['SESSION_CLOSED', 'ATTEMPT_NOT_CURRENT', 'ANSWER_ALREADY_GRADED'].includes(failure.code)) {
        void client.invalidateQueries({ queryKey: itemKey });
        void client.invalidateQueries({ queryKey: keys.session(sessionId) });
      }
    },
  });
  function save(optionId: string | null) {
    if (restoringNow.current) return;
    const value = { attemptId: item.attempt.id, optionId, sequence: ++sequence.current };
    setIntent(value); setError(null); mutation.mutate(value);
  }
  async function restore() {
    if (restoringNow.current || saving) return;
    restoringNow.current = true; setRestoring(true);
    try {
      await client.cancelQueries({ queryKey: itemKey, exact: true });
      await client.fetchQuery({ queryKey: itemKey, staleTime: 0,
        queryFn: ({ signal }) => api<ItemResponse>(`/quiz-sessions/${sessionId}/items/${item.id}`, { signal }) });
      setIntent(null); setError(null);
      await client.invalidateQueries({ queryKey: keys.session(sessionId) });
    } catch (failure) { setError(failure); }
    finally { restoringNow.current = false; setRestoring(false); }
  }
  const currentIntent = data.session_status === 'active' && item.attempt.status === 'draft' && intent?.attemptId === item.attempt.id ? intent : null;
  return {
    selected: currentIntent ? currentIntent.optionId : item.attempt.selected_option_id,
    saving, restoring, error: currentIntent ? error : null, unsaved: currentIntent !== null,
    save,
    retry: () => { if (currentIntent) save(currentIntent.optionId); },
    restore,
  };
}
