
"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

type RefundEntry = {
  refund_id: number;
  refund_request_id: number;
  amount: string;
  created_at: string;
  operator: string | null;
};

type LedgerEntry = {
  order_id: number;
  restaurant: string;
  final_state: string;
  current_order_status: string;
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
  refunds: RefundEntry[];
  total_refunded: string;
  net_charge: string;
};

const statuses = [
  ["all", "All orders"],
  ["delivered", "Delivered"],
  ["partially_refunded", "Partially refunded"],
  ["refunded", "Refunded"],
  ["rejected", "Rejected"],
  ["cancelled", "Cancelled"],
];

const money = (value: string | number) =>
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
    partially_refunded: "bg-amber-100 text-amber-800",
    refunded: "bg-blue-100 text-blue-800",
    rejected: "bg-red-100 text-red-800",
    cancelled: "bg-gray-100 text-gray-700",
  };

  const labels: Record<string, string> = {
    partially_refunded: "Partially Refunded",
  };

  const label =
    labels[value] ||
    value.charAt(0).toUpperCase() + value.slice(1);

  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${
        styles[value] ?? "bg-gray-100 text-gray-700"
      }`}
    >
      {label}
    </span>
  );
}

export default function LedgerPage() {
  const [entries, setEntries] = useState<LedgerEntry[]>([]);
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
        : entries.filter(
            (entry) => entry.current_order_status === filter
          ),
    [entries, filter]
  );

  const totalCharges = entries.reduce(
    (sum, entry) => sum + Number(entry.total_charge),
    0
  );

  const totalRefunds = entries.reduce(
    (sum, entry) => sum + Number(entry.total_refunded),
    0
  );

  const netCharges = entries.reduce(
    (sum, entry) => sum + Number(entry.net_charge),
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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">

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
              Original charges
            </h2>

            <p className="text-3xl font-bold text-[var(--color-forest)] mt-4 tabular-nums">
              {money(totalCharges)}
            </p>
          </section>

          <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
            <h2 className="text-sm font-semibold text-[var(--color-muted)]">
              Total refunds
            </h2>

            <p className="text-3xl font-bold text-red-700 mt-4 tabular-nums">
              {money(totalRefunds)}
            </p>
          </section>

          <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
            <h2 className="text-sm font-semibold text-[var(--color-muted)]">
              Net charges
            </h2>

            <p className="text-3xl font-bold text-[var(--color-forest)] mt-4 tabular-nums">
              {money(netCharges)}
            </p>
          </section>

        </div>

        {/* Filter */}
        <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 mb-6">
          <label
            htmlFor="ledger-filter"
            className="block text-sm font-semibold mb-2"
          >
            Filter by current order status
          </label>

          <select
            id="ledger-filter"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            className="w-full sm:w-64 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
          >
            {statuses.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </section>

        {/* Ledger entries */}
        <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">

          <h2 className="section-title mb-6">
            Ledger entries
          </h2>

          {loading && (
            <p role="status" className="body-text">
              Loading ledger entries…
            </p>
          )}

          {!loading && filteredEntries.length === 0 && (
            <p className="form-help">
              No ledger entries found.
            </p>
          )}

          {!loading && filteredEntries.length > 0 && (
            <div className="space-y-4">

              {filteredEntries.map((entry) => (
                <details
                  key={entry.order_id}
                  className="rounded-2xl border border-[var(--color-border)] overflow-hidden"
                >

                  {/* Order heading */}
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

                      <div className="flex flex-wrap items-center gap-3">
                        <StatusLabel value={entry.current_order_status} />

                        <span className="font-bold tabular-nums">
                          {money(entry.net_charge)}
                        </span>

                        <span aria-hidden="true">⌄</span>
                      </div>

                    </div>
                  </summary>

                  {/* Expanded details */}
                  <div className="border-t border-[var(--color-border)] p-5">

                    {/* Status information */}
                    <div className="mb-6 rounded-xl bg-[var(--color-sage-light)]/30 p-4">
                      <p className="text-sm font-semibold mb-3">
                        Order status history
                      </p>

                      <div className="flex flex-wrap gap-3 items-center">
                        <div>
                          <p className="form-help mb-1">
                            Original final state
                          </p>
                          <StatusLabel value={entry.final_state} />
                        </div>

                        <div>
                          <p className="form-help mb-1">
                            Current status
                          </p>
                          <StatusLabel value={entry.current_order_status} />
                        </div>
                      </div>
                    </div>

                    {/* Order items */}
                    <h3 className="font-semibold mb-4">
                      Order items
                    </h3>

                    <div className="space-y-3">
                      {entry.items.map((item, index) => (
                        <div
                          key={`${item.name}-${index}`}
                          className="flex justify-between gap-4 text-sm"
                        >
                          <div>
                            <p className="font-medium">
                              {item.name}
                            </p>

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

                    {/* Original charge breakdown */}
                    <div className="border-t border-[var(--color-border)] mt-5 pt-5 space-y-3 text-sm">

                      <h3 className="font-semibold mb-3">
                        Original charge
                      </h3>

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
                        <span className="form-help">
                          Small-order surcharge
                        </span>
                        <span>{money(entry.small_order_surcharge)}</span>
                      </div>

                      <div className="flex justify-between gap-4 border-t border-[var(--color-border)] pt-4">
                        <span className="font-bold">
                          Original total charge
                        </span>

                        <span className="text-lg font-bold text-[var(--color-forest)] tabular-nums">
                          {money(entry.total_charge)}
                        </span>
                      </div>

                    </div>

                    {/* Separate refund transactions */}
                    <div className="border-t border-[var(--color-border)] mt-6 pt-5">

                      <h3 className="font-semibold mb-4">
                        Refund transactions
                      </h3>

                      {entry.refunds.length === 0 ? (
                        <p className="form-help">
                          No refunds have been recorded for this order.
                        </p>
                      ) : (
                        <div className="space-y-3">

                          {entry.refunds.map((refund) => (
                            <div
                              key={refund.refund_id}
                              className="rounded-xl border border-red-200 bg-red-50 p-4"
                            >

                              <div className="flex flex-wrap justify-between gap-3">
                                <div>
                                  <p className="font-semibold text-red-800">
                                    Refund #{refund.refund_id}
                                  </p>

                                  <p className="text-xs text-red-700 mt-1">
                                    Refund request #{refund.refund_request_id}
                                  </p>
                                </div>

                                <p className="font-bold text-red-800 tabular-nums">
                                  −{money(refund.amount)}
                                </p>
                              </div>

                              <div className="mt-3 space-y-1">
                                <p className="text-xs text-red-700">
                                  Recorded: {date(refund.created_at)}
                                </p>

                                <p className="text-xs text-red-700">
                                  Approved by: {refund.operator || "Unknown"}
                                </p>
                              </div>

                            </div>
                          ))}

                        </div>
                      )}

                    </div>

                    {/* Net financial position */}
                    <div className="border-t border-[var(--color-border)] mt-6 pt-5 space-y-3">

                      <h3 className="font-semibold mb-3">
                        Financial summary
                      </h3>

                      <div className="flex justify-between gap-4 text-sm">
                        <span className="form-help">
                          Original charge
                        </span>

                        <span className="font-semibold tabular-nums">
                          {money(entry.total_charge)}
                        </span>
                      </div>

                      <div className="flex justify-between gap-4 text-sm">
                        <span className="form-help">
                          Total refunded
                        </span>

                        <span className="font-semibold text-red-700 tabular-nums">
                          −{money(entry.total_refunded)}
                        </span>
                      </div>

                      <div className="border-t border-[var(--color-border)] pt-4 flex justify-between gap-4">
                        <span className="font-bold">
                          Net charge
                        </span>

                        <span className="text-xl font-bold text-[var(--color-forest)] tabular-nums">
                          {money(entry.net_charge)}
                        </span>
                      </div>

                    </div>

                    {/* Dates */}
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
      </div>
    </main>
  );
}
