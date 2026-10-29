export type DemoToast = {
  id: string;
  method: string;
  path: string;
  status: number | null;
  label: string;
  body: string;
  expiresAt: number;
};

const storageKey = "demo-api-toasts";
const empty: DemoToast[] = [];
let toasts: DemoToast[] = empty;
const listeners = new Set<() => void>();

export const getToasts = () => toasts;
export const getServerToasts = () => empty;
export function subscribeToasts(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
function update(next: DemoToast[]) {
  toasts = next;
  try { sessionStorage.setItem(storageKey, JSON.stringify(toasts)); } catch { /* Storage may be unavailable. */ }
  listeners.forEach((listener) => listener());
}
export function dismissToast(id: string) {
  update(toasts.filter((toast) => toast.id !== id));
}
export function restoreToasts() {
  try {
    const saved: DemoToast[] = JSON.parse(sessionStorage.getItem(storageKey) || "[]");
    update([...saved.filter((toast) => toast.expiresAt > Date.now() && !toasts.some((current) => current.id === toast.id)), ...toasts].slice(-5));
  } catch { /* Ignore unavailable or invalid saved notifications. */ }
}

/** Demo-only response reporting; clone bodies so callers can still consume them. */
export async function demoFetch(input: string | URL, init: RequestInit = {}): Promise<Response> {
  const method = (init.method || "GET").toUpperCase();
  const path = new URL(input.toString()).pathname;
  const publish = (status: number | null, label: string, body: string) => {
    update([...toasts, { id: crypto.randomUUID(), method, path, status, label, body, expiresAt: Date.now() + 15000 }].slice(-5));
  };
  let response: Response;
  try {
    response = await fetch(input, init);
  } catch (error) {
    publish(null, "Network error", error instanceof Error ? error.message : "No response received.");
    throw error;
  }
  let body = "Empty response body";
  try {
    const text = await response.clone().text();
    if (text) {
      try { body = JSON.stringify(JSON.parse(text), null, 2); }
      catch { body = text; }
    }
  } catch { body = "Response body could not be read."; }
  publish(response.status, response.statusText || (response.ok ? "Success" : "Request failed"), body);
  return response;
}
