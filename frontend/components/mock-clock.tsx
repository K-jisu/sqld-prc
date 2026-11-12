"use client";

import { useEffect, useEffectEvent, useRef, useState } from 'react';

export function MockClock({ deadline, serverNow, receivedAt, onExpired, onRefresh }: {
  deadline: string; serverNow: string; receivedAt: number; onExpired: () => void; onRefresh: () => Promise<boolean>;
}) {
  const [seconds, setSeconds] = useState(Math.max(0, Math.ceil((Date.parse(deadline) - Date.parse(serverNow)) / 1000)));
  const sent = useRef(false);
  const tick = useEffectEvent(() => {
    const left = Math.max(0, Math.ceil((Date.parse(deadline) - Date.parse(serverNow) - (Date.now() - receivedAt)) / 1000));
    setSeconds(left);
    if (left === 0 && !sent.current) { sent.current = true; onExpired(); }
  });
  const refresh = useEffectEvent(() => { if (document.visibilityState === 'visible') void onRefresh(); });
  useEffect(() => {
    const timer = setInterval(() => tick(), 500);
    const focus = () => refresh();
    window.addEventListener('focus', focus);
    document.addEventListener('visibilitychange', focus);
    return () => { clearInterval(timer); window.removeEventListener('focus', focus); document.removeEventListener('visibilitychange', focus); };
  }, [deadline, serverNow, receivedAt]);
  return <span className={`mock-clock ${seconds <= 300 ? 'incorrect-ink' : ''}`} aria-label="남은 시간">남은 시간 <strong>{String(Math.floor(seconds / 60)).padStart(2, '0')}:{String(seconds % 60).padStart(2, '0')}</strong></span>;
}
