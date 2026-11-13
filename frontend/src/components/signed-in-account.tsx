"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export default function SignedInAccount() {
  const [username, setUsername] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let disposed = false;
    let inFlight = false;
    async function refresh() {
      if (inFlight) return;
      inFlight = true;
      try {
        const response = await apiFetch("/api/accounts/me/");
        if (!response.ok) throw new Error("Could not load account.");
        const account = await response.json();
        if (!disposed) { setUsername(account.username); setError(false); }
      } catch {
        if (!disposed) { setUsername(null); setError(true); }
      } finally { inFlight = false; }
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    window.addEventListener("focus", refresh);
    return () => {
      disposed = true;
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, []);

  return <p className="body-text mt-2">
    {username ? <>Signed in as <strong>{username}</strong></> : error ? "Could not load account name." : "Loading account…"}
  </p>;
}
