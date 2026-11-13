import { demoFetch } from "./demo-toasts";

export const API_BASE = "http://localhost:8000";

let refreshRequest: Promise<void> | null = null;
let refreshGeneration = 0;
let loggingOut = false;

async function refreshSession(): Promise<void> {
  if (loggingOut) throw new Error("Logging out.");
  if (!refreshRequest) {
    refreshRequest = (async () => {
      const response = await demoFetch(`${API_BASE}/api/accounts/token/refresh/`, {
        method: "POST",
        credentials: "include",
      });
      if (response.status === 401) {
        throw new Error("Your session has expired. Please log in again.");
      }
      if (!response.ok) {
        throw new Error("Could not refresh your session. Please try again.");
      }
      refreshGeneration += 1;
    })().finally(() => { refreshRequest = null; });
  }
  return refreshRequest;
}

/** Send an authenticated request and retry once after refreshing on a 401. */
export async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  if (loggingOut) throw new Error("Logging out.");
  const target = new URL(url, API_BASE);
  if (target.origin !== API_BASE) {
    throw new Error("Authenticated requests must use the API origin.");
  }
  const generation = refreshGeneration;
  const send = () => {
    const headers = new Headers(init.headers);
    const method = (init.method ?? "GET").toUpperCase();
    if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method) && typeof document !== "undefined") {
      const cookie = document.cookie.split(";").map((part) => part.trim())
        .find((part) => part.startsWith("csrftoken="));
      if (cookie) {
        headers.set("X-CSRFToken", decodeURIComponent(cookie.slice("csrftoken=".length)));
      }
    }
    return demoFetch(target, { ...init, headers, credentials: "include" });
  };

  let response = await send();
  if (response.status === 401) {
    // Share a refresh with concurrent requests, including late 401 responses.
    if (generation === refreshGeneration) await refreshSession();
    response = await send();
    if (response.status === 401) {
      throw new Error("Your session has expired. Please log in again.");
    }
  }
  return response;
}

export async function logout(): Promise<void> {
  loggingOut = true;
  try {
    if (refreshRequest) await refreshRequest.catch(() => undefined);
    const csrf = document.cookie.split(";").map((part) => part.trim())
      .find((part) => part.startsWith("csrftoken="));
    const response = await demoFetch(`${API_BASE}/api/accounts/logout/`, {
      method: "POST",
      credentials: "include",
      headers: csrf ? { "X-CSRFToken": decodeURIComponent(csrf.slice("csrftoken=".length)) } : {},
    });
    if (!response.ok) throw new Error("Could not log out. Please try again.");
    window.location.replace("/login");
  } catch (error) {
    loggingOut = false;
    throw error;
  }
}
