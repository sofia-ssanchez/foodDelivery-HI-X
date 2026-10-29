"use client";

import { useState, type ReactNode } from "react";
import { logout } from "@/lib/api";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function handleLogout() {
    if (pending) return;
    setPending(true);
    setError("");
    try {
      await logout();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not log out. Please try again.");
      setPending(false);
    }
  }

  return <>
    <div className="border-b border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-3">
      <div className="w-full flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-[var(--color-forest)]">
          <svg viewBox="0 0 64 72" aria-hidden="true" className="h-12 w-11 sm:h-14 sm:w-12 shrink-0">
            <path d="M32 34 C30 48 40 56 46 67" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
            {[0, 72, 144, 216, 288].map((angle) => (
              <path key={angle} transform={`rotate(${angle} 32 31)`} d="M32 31 C28 26 17 20 20 12 C22 6 29 7 32 12 C35 7 42 6 44 12 C47 20 36 26 32 31Z" fill={angle % 144 === 0 ? "var(--color-leaf)" : "var(--color-forest)"} stroke="var(--color-surface)" strokeWidth="1" />
            ))}
            <circle cx="32" cy="31" r="3" fill="var(--color-sage)" />
          </svg>
          <p className="text-2xl sm:text-3xl font-semibold tracking-tight" style={{ fontFamily: "Georgia, 'Times New Roman', serif" }}>Five Leaf Clover</p>
        </div>
        <button type="button" className="btn btn-secondary" disabled={pending} onClick={() => void handleLogout()}>{pending ? "Logging out…" : "Log out"}</button>
      </div>
      {error && <p role="alert" className="message message-error max-w-[1440px] mx-auto mt-3">{error}</p>}
    </div>
    {children}
  </>;
}
