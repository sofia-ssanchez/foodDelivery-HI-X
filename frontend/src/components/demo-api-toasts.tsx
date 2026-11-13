"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";
import { clearToasts, getServerToasts, getToasts, restoreToasts, subscribeToasts } from "@/lib/demo-toasts";
import { apiFetch } from "@/lib/api";

export default function DemoApiToasts() {
  const entries = useSyncExternalStore(subscribeToasts, getToasts, getServerToasts);
  const [open, setOpen] = useState(true);
  const [reads, setReads] = useState(false);
  const [operator, setOperator] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState("");
  const pathname = usePathname();
  useEffect(() => { restoreToasts(); }, []);
  useEffect(() => {
    let cancelled = false;
    if (process.env.NODE_ENV !== "production" && pathname.startsWith("/dashboard")) {
      apiFetch("/api/accounts/me/").then(async (response) => {
        const account = response.ok ? await response.json() : null;
        if (!cancelled) setOperator(account?.role === "operator");
      }).catch(() => { if (!cancelled) setOperator(false); });
    }
    return () => { cancelled = true; };
  }, [pathname]);
  if (process.env.NODE_ENV === "production") return null;
  const visible = entries.filter((entry) => reads || entry.method !== "GET" || entry.status === null || entry.status >= 400);
  async function reset() {
    if (!window.confirm("Reset demo? All orders, deliveries, refunds, and extra accounts will be removed.")) return;
    setResetting(true);
    setError("");
    try {
      const response = await apiFetch("/api/demo/reset/", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Reset failed.");
      clearToasts();
      window.location.reload();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Reset failed.");
      setResetting(false);
    }
  }
  return <aside aria-label="Demo console" className="fixed bottom-3 right-3 z-[2000] w-[320px] max-w-[calc(100vw-24px)] overflow-hidden rounded-lg border border-slate-600 bg-slate-950 text-slate-100 shadow-xl text-xs">
    <div className="flex items-center justify-between gap-2 px-3 py-2">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="font-bold">{open ? "−" : "+"} Console ({visible.length})</button>
      <div className="flex gap-3">
        {operator && pathname.startsWith("/dashboard") && <button disabled={resetting} onClick={reset} className="text-amber-300 disabled:opacity-50">{resetting ? "Resetting…" : "Reset demo"}</button>}
        <button onClick={clearToasts}>Clear</button>
      </div>
    </div>
    {error && <p role="alert" className="px-3 pb-2 text-red-300">{error}</p>}
    {open && <>
      <label className="flex items-center gap-2 px-3 pb-2"><input type="checkbox" checked={reads} onChange={(event) => setReads(event.target.checked)} />Show GET requests</label>
      <div className="max-h-[180px] overflow-y-auto border-t border-slate-700">
        {visible.length === 0 && <p className="p-3">No commands yet.</p>}
        {[...visible].reverse().map((entry) => <details key={entry.id} className="border-b border-slate-800 px-3 py-2">
          <summary className="cursor-pointer break-all font-mono"><span className={entry.status !== null && entry.status < 400 ? "text-green-300" : "text-red-300"}>{entry.status ?? "ERR"}</span> {entry.method} {entry.path}</summary>
          <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap break-all">{entry.body}</pre>
        </details>)}
      </div>
    </>}
  </aside>;
}
