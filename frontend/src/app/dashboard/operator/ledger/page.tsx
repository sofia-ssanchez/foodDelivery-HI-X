
"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

type LedgerEntry = {
  order_id: number;
  restaurant: string;
  final_state: string;
  order_created_at: string;
  finalized_at: string;
  items: {
    name: string;
    quantity: number;
    unit_price: string;
    line_total: string;
  }[];
  subtotal: string;
  delivery_fee: string;
  service_fee: string;
  small_order_surcharge: string;
  total_charge: string;
};

const statuses = [
  ["all", "All orders"],
  ["delivered", "Delivered"],
  ["rejected", "Rejected"],
  ["cancelled", "Cancelled"],
];

const money = (value: string) =>
  Number(value).toLocaleString("en-CA", {
    style: "currency",
    currency: "CAD",
  });

const date = (value: string) =>
  new Date(value).toLocaleString("en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
  });

function StatusLabel({ value }: { value: string }) {
  const styles: Record<string, string> = {
    delivered:
      "bg-[var(--color-sage-light)] text-[var(--color-forest)]",
    rejected: "bg-red-100 text-red-800",
    cancelled: "bg-amber-100 text-amber-800",
  };

  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${
        styles[value] ?? "bg-gray-100 text-gray-700"
      }`}
    >
      {value.charAt(0).toUpperCase() + value.slice(1)}
    </span>
  );
}

export default function LedgerPage() {
  const [entries, setEntries] = useState<LedgerEntry[]>([]);
  const [selected, setSelected] = useState<LedgerEntry | null>(null);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let disposed = false;

    async function loadLedger() {
      try {
        const response = await apiFetch("/api/pricing/ledger/");
        const result = await response.json();

        if (!response.ok) {
          throw new Error(
            result.detail || "Could not load the order ledger."
          );
        }

        if (!Array.isArray(result)) {
          throw new Error("Unexpected ledger response.");
        }

        if (!disposed) {
          setEntries(result);
          setError("");
        }
      } catch (err) {
        if (!disposed) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not load the order ledger."
          );
        }
      } finally {
        if (!disposed) setLoading(false);
      }
    }

    void loadLedger();

    return () => {
      disposed = true;
    };
  }, []);

  const filteredEntries = useMemo(
    () =>
      filter === "all"
        ? entries
        : entries.filter((entry) => entry.final_state === filter),
    [entries, filter]
  );

  const totalCharges = entries.reduce(
    (sum, entry) => sum + Number(entry.total_charge),
    0
  );

  return (
    <main
      className="page-container botanical-background"
      style={{ alignItems: "flex-start" }}
    >
      <div className="w-full max-w-[1280px] mx-auto">

        {/* Header */}
        <header className="flex flex-wrap justify-between items-start gap-5 mb-9">
          <div>
            <p className="eyebrow">
              Five Leaf Clover · Platform operator
            </p>
            <h1 className="page-title mt-3">Order ledger</h1>
            <p className="form-help mt-3">
              Financial records for finalized orders.
            </p>
          </div>

          <Link
            href="/dashboard/operator"
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-3 text-sm font-semibold hover:opacity-80 transition"
          >
            ← Back to overview
          </Link>
        </header>

        {/* Error */}
        {error && (
          <div role="alert" className="message message-error mb-6">
            {error}
          </div>
        )}

        {/* Summary cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-8">
          <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
            <h2 className="text-sm font-semibold text-[var(--color-muted)]">
              Finalized orders
            </h2>
            <p className="text-4xl font-bold text-[var(--color-forest)] mt-4 tabular-nums">
              {entries.length.toLocaleString("en-CA")}
            </p>
          </section>

          <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
            <h2 className="text-sm font-semibold text-[var(--color-muted)]">
              Total recorded charges
            </h2>
            <p className="text-4xl font-bold text-[var(--color-forest)] mt-4 tabular-nums">
              {money(totalCharges.toFixed(2))}
            </p>
          </section>
        </div>

        {/* Filter */}
        <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 mb-6">
          <label
            htmlFor="ledger-filter"
            className="block text-sm font-semibold mb-2"
          >
            Filter by final state
          </label>

          <select
            id="ledger-filter"
            value={filter}
            onChange={(event) => {
              setFilter(event.target.value);
              setSelected(null);
            }}
            className="w-full sm:w-64 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
          >
            {statuses.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </section>

        {/* Ledger table */}
        <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        <h2 className="section-title mb-6">Ledger entries</h2>

        {loading && (
            <p role="status" className="body-text">
            Loading ledger entries…
            </p>
        )}

        {!loading && filteredEntries.length === 0 && (
            <p className="form-help">No ledger entries found.</p>
        )}

        {!loading && filteredEntries.length > 0 && (
            <div className="space-y-4">
            {filteredEntries.map((entry) => (
                <details
                key={entry.order_id}
                className="rounded-2xl border border-[var(--color-border)] overflow-hidden"
                >
                <summary className="cursor-pointer list-none p-5 hover:bg-[var(--color-sage-light)]/30 transition">
                    <div className="flex flex-wrap justify-between items-center gap-4">
                    <div>
                        <p className="font-bold text-[var(--color-forest)]">
                        Order #{entry.order_id}
                        </p>
                        <p className="form-help mt-1">
                        {entry.restaurant} · {date(entry.finalized_at)}
                        </p>
                    </div>

                    <div className="flex items-center gap-4">
                        <StatusLabel value={entry.final_state} />
                        <span className="font-bold tabular-nums">
                        {money(entry.total_charge)}
                        </span>
                        <span aria-hidden="true">⌄</span>
                    </div>
                    </div>
                </summary>

                <div className="border-t border-[var(--color-border)] p-5">
                    <h3 className="font-semibold mb-4">Order items</h3>

                    <div className="space-y-3">
                    {entry.items.map((item, index) => (
                        <div
                        key={`${item.name}-${index}`}
                        className="flex justify-between gap-4 text-sm"
                        >
                        <div>
                            <p className="font-medium">{item.name}</p>
                            <p className="form-help">
                            {item.quantity} × {money(item.unit_price)}
                            </p>
                        </div>
                        <p className="font-semibold tabular-nums">
                            {money(item.line_total)}
                        </p>
                        </div>
                    ))}
                    </div>

                    <div className="border-t border-[var(--color-border)] mt-5 pt-5 space-y-3 text-sm">
                    <div className="flex justify-between gap-4">
                        <span className="form-help">Subtotal</span>
                        <span>{money(entry.subtotal)}</span>
                    </div>

                    <div className="flex justify-between gap-4">
                        <span className="form-help">Delivery fee</span>
                        <span>{money(entry.delivery_fee)}</span>
                    </div>

                    <div className="flex justify-between gap-4">
                        <span className="form-help">Service fee</span>
                        <span>{money(entry.service_fee)}</span>
                    </div>

                    <div className="flex justify-between gap-4">
                        <span className="form-help">Small-order surcharge</span>
                        <span>{money(entry.small_order_surcharge)}</span>
                    </div>

                    <div className="flex justify-between gap-4 border-t border-[var(--color-border)] pt-4">
                        <span className="font-bold">Total charge</span>
                        <span className="text-lg font-bold text-[var(--color-forest)] tabular-nums">
                        {money(entry.total_charge)}
                        </span>
                    </div>
                    </div>

                    <div className="border-t border-[var(--color-border)] mt-5 pt-4 space-y-2">
                    <p className="form-help">
                        Created: {date(entry.order_created_at)}
                    </p>
                    <p className="form-help">
                        Finalized: {date(entry.finalized_at)}
                    </p>
                    </div>
                </div>
                </details>
            ))}
            </div>
        )}
        </section>

        {/* Selected order details */}
        {selected && (
          <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 mt-6">
            <div className="flex flex-wrap justify-between items-center gap-3 mb-6">
              <div>
                <p className="eyebrow">Financial breakdown</p>
                <h2 className="section-title mt-2">
                  Order #{selected.order_id}
                </h2>
              </div>

              <StatusLabel value={selected.final_state} />
            </div>

            <div className="space-y-4 text-sm">
              <div className="flex justify-between gap-4">
                <span className="form-help">Subtotal</span>
                <span className="font-semibold tabular-nums">
                  {money(selected.subtotal)}
                </span>
              </div>

              <div className="flex justify-between gap-4">
                <span className="form-help">Delivery fee</span>
                <span className="font-semibold tabular-nums">
                  {money(selected.delivery_fee)}
                </span>
              </div>

              <div className="flex justify-between gap-4">
                <span className="form-help">Service fee</span>
                <span className="font-semibold tabular-nums">
                  {money(selected.service_fee)}
                </span>
              </div>

              <div className="flex justify-between gap-4">
                <span className="form-help">Small-order surcharge</span>
                <span className="font-semibold tabular-nums">
                  {money(selected.small_order_surcharge)}
                </span>
              </div>

              <div className="border-t border-[var(--color-border)] pt-4 flex justify-between gap-4">
                <span className="font-bold">Total charge</span>
                <span className="text-xl font-bold text-[var(--color-forest)] tabular-nums">
                  {money(selected.total_charge)}
                </span>
              </div>
            </div>

            <div className="border-t border-[var(--color-border)] mt-6 pt-5 space-y-2">
              <p className="form-help">
                Created: {date(selected.order_created_at)}
              </p>
              <p className="form-help">
                Finalized: {date(selected.finalized_at)}
              </p>
            </div>

            <button
              type="button"
              onClick={() => setSelected(null)}
              className="mt-6 text-sm font-semibold text-[var(--color-forest)] hover:underline"
            >
              Close details
            </button>
          </section>
        )}
      </div>
    </main>
  );
}
