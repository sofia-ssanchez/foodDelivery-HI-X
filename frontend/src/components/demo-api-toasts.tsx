"use client";

import { useEffect, useSyncExternalStore } from "react";
import { dismissToast, getServerToasts, getToasts, restoreToasts, subscribeToasts } from "@/lib/demo-toasts";

export default function DemoApiToasts() {
  const toasts = useSyncExternalStore(subscribeToasts, getToasts, getServerToasts);
  useEffect(() => { restoreToasts(); }, []);
  useEffect(() => {
    const timers = toasts.map((toast) => setTimeout(() => dismissToast(toast.id), Math.max(0, toast.expiresAt - Date.now())));
    return () => timers.forEach(clearTimeout);
  }, [toasts]);

  return <aside aria-label="Demo API responses" aria-live="polite" aria-relevant="additions" className="fixed bottom-4 right-4 z-[100] w-[calc(100%-2rem)] max-w-md max-h-[80vh] overflow-y-auto space-y-3">
    {toasts.map((toast) => <section key={toast.id} className={`rounded-2xl border-l-4 bg-[var(--color-surface)] p-4 shadow-xl ${toast.status !== null && toast.status < 400 ? "border-green-600" : "border-red-600"}`}>
      <div className="flex items-start justify-between gap-3">
        <div><p className="text-xs text-[var(--color-muted)]">Demo · API response</p><p className="font-bold">{toast.status ?? "No HTTP status"} · {toast.label}</p></div>
        <button type="button" className="px-2 py-1 rounded-lg hover:bg-[var(--color-sage-light)]" aria-label={`Dismiss ${toast.method} ${toast.path} response`} onClick={() => dismissToast(toast.id)}>✕</button>
      </div>
      <p className="text-xs font-mono break-all mt-2">{toast.method} {toast.path}</p>
      <details className="mt-3" open={toast.status === null || toast.status >= 400}>
        <summary className="cursor-pointer text-sm font-semibold">Response body</summary>
        <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-[var(--color-cream)] p-3 text-xs">{toast.body}</pre>
      </details>
    </section>)}
  </aside>;
}
