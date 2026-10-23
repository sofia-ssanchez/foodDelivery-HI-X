export const API_BASE = "http://localhost:8000";

let refreshRequest: Promise<void> | null = null;
let refreshGeneration = 0;

async function refreshSession(): Promise<void> {
  if (!refreshRequest) {
    refreshRequest = (async () => {
      const response = await fetch(`${API_BASE}/api/accounts/token/refresh/`, {
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
  const target = new URL(url, API_BASE);
  if (target.origin !== API_BASE) {
    throw new Error("Authenticated requests must use the API origin.");
  }
  const generation = refreshGeneration;
  const send = () => fetch(target, { ...init, credentials: "include" });

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
