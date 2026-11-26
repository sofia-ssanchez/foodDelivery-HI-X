
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

type OrderItem = {
  name: string;
  quantity: number;
  unit_price: string;
  line_total: string;
};

type OrderEvent = {
  event_id: string;
  transition_number: number;
  from_status: string;
  to_status: string;
  timestamp: string;
  actor_username: string;
  actor_role: string;
};

type Order = {
  id: number;
  customer_name: string;
  restaurant_name: string;
  status: string;
  created_at: string;
  items: OrderItem[];
  events: OrderEvent[];
};

type Filter = "all" | "placed" | "active" | "completed" | "refunded";

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    placed: "bg-amber-100 text-amber-800",
    accepted: "bg-blue-100 text-blue-800",
    preparing: "bg-blue-100 text-blue-800",
    ready: "bg-blue-100 text-blue-800",
    picked_up: "bg-blue-100 text-blue-800",
    delivered: "bg-green-100 text-green-800",
    refunded: "bg-green-100 text-green-800",
    partially_refunded: "bg-amber-100 text-amber-800",
    rejected: "bg-red-100 text-red-800",
    cancelled: "bg-red-100 text-red-800",
  };

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
        styles[status] || "bg-gray-100 text-gray-700"
      }`}
    >
      {formatStatus(status)}
    </span>
  );
}

function SummaryCard({
  label,
  count,
}: {
  label: string;
  count: number;
}) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:p-5">
      <p className="text-2xl font-bold text-[var(--color-forest)] sm:text-3xl">
        {count}
      </p>
      <p className="mt-1 text-sm text-[var(--color-muted)]">{label}</p>
    </div>
  );
}

export default function OperatorOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [expandedOrder, setExpandedOrder] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadOrders = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const response = await apiFetch("/api/operator/orders/");
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Unable to load order history.");
      }

      const orderList: Order[] = Array.isArray(data)
        ? data
        : data.results ?? [];

      orderList.sort(
        (a, b) =>
          new Date(b.created_at).getTime() -
          new Date(a.created_at).getTime()
      );

      setOrders(orderList);
    } catch (err) {
      console.error(err);
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load order history."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  const placedCount = orders.filter(
    (order) => order.status === "placed"
  ).length;

  const activeCount = orders.filter((order) =>
    ["accepted", "preparing", "ready", "picked_up"].includes(order.status)
  ).length;

  const completedCount = orders.filter((order) =>
    ["delivered", "rejected", "cancelled"].includes(order.status)
  ).length;

  const refundedCount = orders.filter((order) =>
    ["partially_refunded", "refunded"].includes(order.status)
  ).length;

  const filteredOrders = useMemo(() => {
    return orders.filter((order) => {
      let matchesFilter = true;

      if (filter === "placed") {
        matchesFilter = order.status === "placed";
      } else if (filter === "active") {
        matchesFilter = [
          "accepted",
          "preparing",
          "ready",
          "picked_up",
        ].includes(order.status);
      } else if (filter === "completed") {
        matchesFilter = [
          "delivered",
          "rejected",
          "cancelled",
        ].includes(order.status);
      } else if (filter === "refunded") {
        matchesFilter = [
          "partially_refunded",
          "refunded",
        ].includes(order.status);
      }

      const searchText = search.trim().toLowerCase();

      const matchesSearch =
        !searchText ||
        String(order.id).includes(searchText) ||
        order.customer_name.toLowerCase().includes(searchText) ||
        order.restaurant_name.toLowerCase().includes(searchText);

      return matchesFilter && matchesSearch;
    });
  }, [orders, filter, search]);

  return (
    <main className="page-container botanical-background flex w-full flex-col">
      {/* HEADER */}
      <header className="mb-8 flex w-full items-center justify-between gap-4">
        <div>
          <p className="eyebrow">Operator Dashboard</p>
          <h1 className="page-title">Order History</h1>
          <p className="form-help mt-2">
            View all orders and review their recorded status transitions.
          </p>
        </div>

        <Link
          href="/dashboard/operator"
          className="shrink-0 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 text-sm font-semibold text-[var(--color-forest)] transition hover:bg-[var(--color-sage-light)]"
        >
          ← Back to Overview
        </Link>
      </header>

      {/* SUMMARY NUMBERS */}
      <section className="mb-10 flex w-full flex-row flex-wrap items-stretch gap-4">
        <div className="min-w-[130px] flex-1">
          <SummaryCard label="Total Orders" count={orders.length} />
        </div>

        <div className="min-w-[130px] flex-1">
          <SummaryCard label="Placed" count={placedCount} />
        </div>

        <div className="min-w-[130px] flex-1">
          <SummaryCard label="Active" count={activeCount} />
        </div>

        <div className="min-w-[130px] flex-1">
          <SummaryCard label="Completed" count={completedCount} />
        </div>

        <div className="min-w-[130px] flex-1">
          <SummaryCard label="Refunded" count={refundedCount} />
        </div>
      </section>

      {/* ORDER HISTORY */}
      <section className="flex w-full flex-col">
        <div className="mb-5">
          <h2 className="section-title">All Orders</h2>
          <p className="form-help mt-1">
            Select an order to review its details and event history.
          </p>
        </div>

        {/* SEARCH */}
        <div className="mb-5">
          <input
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by order number, customer, or restaurant..."
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-forest)] placeholder:text-[var(--color-muted)]"
          />
        </div>

        {/* FILTERS */}
        <div className="mb-6 flex flex-wrap gap-2">
          {(
            ["all", "placed", "active", "completed", "refunded"] as Filter[]
          ).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilter(value)}
              className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                filter === value
                  ? "bg-[var(--color-forest)] text-white"
                  : "border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-muted)] hover:bg-[var(--color-sage-light)]"
              }`}
            >
              {value === "all"
                ? "All Orders"
                : value === "active"
                  ? "Active"
                  : formatStatus(value)}
            </button>
          ))}
        </div>

        {/* ERROR */}
        {error && (
          <div className="message message-error mb-5">
            {error}
          </div>
        )}

        {/* ORDER LIST */}
        {loading ? (
          <p className="body-text">Loading order history...</p>
        ) : filteredOrders.length === 0 ? (
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-center">
            <h3 className="font-semibold text-[var(--color-forest)]">
              No orders found
            </h3>
            <p className="form-help mt-2">
              There are no orders matching your search or selected filter.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            {filteredOrders.map((order) => {
              const isExpanded = expandedOrder === order.id;

              const sortedEvents = [...(order.events ?? [])].sort(
                (a, b) => a.transition_number - b.transition_number
              );

              return (
                <article
                  key={order.id}
                  className="block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-sm sm:p-6"
                >
                  {/* ORDER HEADER */}
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedOrder(isExpanded ? null : order.id)
                    }
                    className="flex w-full flex-wrap items-center justify-between gap-4 text-left"
                  >
                    <div>
                      <p className="eyebrow">Order #{order.id}</p>
                      <h3 className="mt-1 text-lg font-semibold text-[var(--color-forest)]">
                        {order.restaurant_name}
                      </h3>
                      <p className="mt-1 text-sm text-[var(--color-muted)]">
                        Customer: {order.customer_name}
                      </p>
                      <p className="mt-1 text-xs text-[var(--color-muted)]">
                        Created: {formatDate(order.created_at)}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <StatusBadge status={order.status} />

                      <span className="text-sm font-medium text-[var(--color-forest)]">
                        {sortedEvents.length} event
                        {sortedEvents.length === 1 ? "" : "s"}
                      </span>

                      <span className="text-lg text-[var(--color-forest)]">
                        {isExpanded ? "−" : "+"}
                      </span>
                    </div>
                  </button>

                  {/* EXPANDED DETAILS */}
                  {isExpanded && (
                    <div className="mt-6 border-t border-[var(--color-border)] pt-5">
                      <div className="flex flex-col gap-6">
                        {/* ORDER INFORMATION */}
                        <div>
                          <h4 className="mb-3 font-semibold text-[var(--color-forest)]">
                            Order Information
                          </h4>

                          <div className="flex flex-col gap-3 text-sm">
                            <div>
                              <p className="text-[var(--color-muted)]">
                                Customer
                              </p>
                              <p className="font-medium">
                                {order.customer_name}
                              </p>
                            </div>

                            <div>
                              <p className="text-[var(--color-muted)]">
                                Restaurant
                              </p>
                              <p className="font-medium">
                                {order.restaurant_name}
                              </p>
                            </div>

                            <div>
                              <p className="text-[var(--color-muted)]">
                                Current order status
                              </p>
                              <div className="mt-1">
                                <StatusBadge status={order.status} />
                              </div>
                            </div>
                          </div>

                          {/* ITEMS */}
                          <div className="mt-5">
                            <h4 className="mb-3 font-semibold text-[var(--color-forest)]">
                              Order Items
                            </h4>

                            {order.items?.length ? (
                              <div className="flex flex-col gap-2">
                                {order.items.map((item, index) => (
                                  <div
                                    key={`${item.name}-${index}`}
                                    className="flex justify-between gap-4 border-b border-[var(--color-border)] pb-2 text-sm last:border-0"
                                  >
                                    <span>
                                      {item.quantity} × {item.name}
                                    </span>
                                    <span className="font-medium">
                                      ${Number(item.line_total).toFixed(2)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="form-help">
                                No item details available.
                              </p>
                            )}
                          </div>
                        </div>

                        {/* EVENT HISTORY */}
                        <div className="border-t border-[var(--color-border)] pt-5">
                          <h4 className="mb-2 font-semibold text-[var(--color-forest)]">
                            Status Event History
                          </h4>

                          <p className="form-help mb-4">
                            Each event records a successful order status
                            transition.
                          </p>

                          {sortedEvents.length === 0 ? (
                            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-sage-light)] p-4">
                              <p className="font-medium text-[var(--color-forest)]">
                                No events recorded
                              </p>
                              <p className="form-help mt-1">
                                This order does not currently have any
                                recorded status events. Orders created before
                                event tracking was introduced will need a
                                historical backfill if you want them included.
                              </p>
                            </div>
                          ) : (
                            <div className="flex flex-col gap-3">
                              {sortedEvents.map((event) => (
                                <div
                                  key={event.event_id}
                                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
                                >
                                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                                    <span className="font-mono text-sm font-bold text-[var(--color-forest)]">
                                      {event.event_id}
                                    </span>

                                    <span className="text-xs text-[var(--color-muted)]">
                                      Transition #{event.transition_number}
                                    </span>
                                  </div>

                                  <p className="font-medium text-[var(--color-forest)]">
                                    {event.from_status
                                      ? formatStatus(event.from_status)
                                      : "Order placed"}
                                    {" → "}
                                    {formatStatus(event.to_status)}
                                  </p>

                                  <div className="mt-3 flex flex-col gap-2 text-sm">
                                    <div>
                                      <p className="text-[var(--color-muted)]">
                                        Timestamp
                                      </p>
                                      <p>{formatDate(event.timestamp)}</p>
                                    </div>

                                    <div>
                                      <p className="text-[var(--color-muted)]">
                                        Actor
                                      </p>
                                      <p>
                                        {event.actor_username || "System"}
                                        {event.actor_role
                                          ? ` (${event.actor_role})`
                                          : ""}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
