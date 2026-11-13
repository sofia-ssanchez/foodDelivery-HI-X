"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";

export type CheckoutAddressValue = { token: string; unit: string; address: string };
type AddressResult = { address: string; token: string };

export default function CheckoutAddress({ value, onChange, disabled }: {
  value: CheckoutAddressValue; onChange: (value: CheckoutAddressValue) => void; disabled: boolean;
}) {
  const [query, setQuery] = useState(value.address);
  const [results, setResults] = useState<AddressResult[]>([]);
  const [selected, setSelected] = useState(value.token ? value.address : "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function search() {
    if (loading || disabled) return;
    onChange({ ...value, token: "" });
    setSelected("");
    setResults([]);
    setError("");
    setLoading(true);
    try {
      const response = await apiFetch("/api/customer/address-lookup/", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: query.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.address?.[0] || "Could not find this address.");
      setResults(data.results);
      if (!data.results.length) setError("No matching street address found. Include the building number, street, and city in the Montreal area.");
    } catch (err) { setError(err instanceof Error ? err.message : "Address lookup failed."); }
    finally { setLoading(false); }
  }

  return <fieldset disabled={disabled || loading} className="mt-5 space-y-3">
    <legend className="font-semibold">Delivery address</legend>
    <label htmlFor="delivery-street" className="block text-sm">Building number, street, and city</label>
    <input id="delivery-street" autoComplete="street-address" maxLength={250} value={query} placeholder="1455 Boulevard de Maisonneuve Ouest, Montreal"
      className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-input)] p-3"
      onChange={(event) => { setQuery(event.target.value); setSelected(""); setResults([]); setError(""); onChange({ ...value, token: "", address: event.target.value }); }}
      onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); if (query.trim().length >= 5) void search(); } }} />
    <button type="button" className="btn btn-secondary" disabled={disabled || loading || query.trim().length < 5} onClick={() => void search()}>{loading ? "Finding address…" : "Find address"}</button>
    <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className="text-xs underline">© OpenStreetMap contributors</a>
    {error && <p role="alert" className="message message-error">{error}</p>}
    {!!results.length && <div className="space-y-2"><p className="text-sm font-semibold">Select your delivery address:</p>{results.map((result) => <button type="button" key={result.token}
      aria-pressed={value.token === result.token} className={`btn btn-full text-left ${value.token === result.token ? "btn-primary" : "btn-secondary"}`}
      onClick={() => { setSelected(result.address); setQuery(result.address); onChange({ ...value, token: result.token, address: result.address }); }}>{result.address}</button>)}</div>}
    {selected && <p role="status" className="text-sm">Deliver to: <strong>{selected}</strong></p>}
    <label htmlFor="delivery-unit" className="block text-sm">Apartment / unit (optional)</label>
    <input id="delivery-unit" autoComplete="address-line2" maxLength={80} value={value.unit} className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-input)] p-3"
      onChange={(event) => onChange({ ...value, unit: event.target.value })} />
  </fieldset>;
}
