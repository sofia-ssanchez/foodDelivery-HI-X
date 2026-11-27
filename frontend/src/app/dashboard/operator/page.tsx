"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import MontrealMap from "@/components/montreal-map";

type Overview = {
  total_users: number;
  active_users: number;
  total_restaurants: number;
  total_orders: number;
  active_orders: number;
  users_by_role: Record<string, number>;
  restaurants_by_status: Record<string, number>;
  orders_by_status: Record<string, number>;
  updated_at: string;
};

type Operations = {
  restaurants: { id: number; name: string; status: "open" | "paused" | "closed" }[];
  available_couriers: { id: number; username: string }[];
  offline_assignments: {
    assignment_id: number;
    order_id: number;
    restaurant_name: string;
    customer_name: string;
    courier_name: string;
    created_at: string;
    items: { name: string; quantity: number }[];
  }[];
};

const roles = [["customer", "Customers"], ["restaurant", "Restaurant accounts"], ["courier", "Couriers"], ["operator", "Operators"]];
const restaurantStatuses = [["open", "Open"], ["paused", "Paused"], ["closed", "Closed"]];
const orderStatuses = [["placed", "Placed"], ["accepted", "Accepted"], ["preparing", "Preparing"], ["ready", "Ready for pickup"], ["picked_up", "Out for delivery"], ["delivered", "Delivered"], ["rejected", "Declined"], ["cancelled", "Cancelled"]];
const number = (value: number) => value.toLocaleString("en-CA");

function Breakdown({ title, labels, counts, total }: {
  title: string; labels: string[][]; counts: Record<string, number>; total: number;
}) {
  return (
    <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
      <h2 className="section-title">{title}</h2>

      <dl className="space-y-5">
        {labels.map(([key, label]) => {
          const count = counts[key] ?? 0;
          return <div key={key}>
            <div className="flex justify-between gap-4 text-sm mb-2"><dt>{label}</dt><dd className="font-bold tabular-nums">{number(count)}</dd></div>
            <div aria-hidden="true" className="h-2 rounded-full bg-[var(--color-sage-light)] overflow-hidden">
              <div className="h-full rounded-full bg-[var(--color-leaf)]" style={{ width: `${total ? count / total * 100 : 0}%` }} />
            </div>
          </div>;
        })}
      </dl>
      {total === 0 && <p className="form-help mt-5">No records yet.</p>}
    </section>
  );
}

export default function OperatorDashboard() {
  const [section, setSection] = useState<"overview" | "map" | "operations">("overview");
  const [data, setData] = useState<Overview | null>(null);
  const [operations, setOperations] = useState<Operations | null>(null);
  const [operationsLoading, setOperationsLoading] = useState(false);
  const [operationsError, setOperationsError] = useState("");
  const [operationsNotice, setOperationsNotice] = useState("");
  const [selectedCouriers, setSelectedCouriers] = useState<Record<number, number>>({});
  const [pendingOperation, setPendingOperation] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refreshOperations = useCallback(async () => {
    setOperationsLoading(true);
    try {
      const response = await apiFetch("/api/operator/operations/");
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not load restaurant and delivery operations.");
      setOperations(result);
      setSelectedCouriers((current) => {
        const next = { ...current };
        result.offline_assignments.forEach((assignment: Operations["offline_assignments"][number]) => {
          const existing = next[assignment.assignment_id];
          if (!existing || !result.available_couriers.some((courier: Operations["available_couriers"][number]) => courier.id === existing)) {
            next[assignment.assignment_id] = result.available_couriers[0]?.id ?? 0;
          }
        });
        return next;
      });
      setOperationsError("");
    } catch (err) {
      setOperationsError(err instanceof Error ? err.message : "Could not load restaurant and delivery operations.");
    } finally {
      setOperationsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (section !== "operations") return;
    void refreshOperations();
    const timer = window.setInterval(() => void refreshOperations(), 15000);
    return () => window.clearInterval(timer);
  }, [section, refreshOperations]);

  async function toggleRestaurant(restaurant: Operations["restaurants"][number]) {
    if (pendingOperation) return;
    setPendingOperation(`restaurant:${restaurant.id}`);
    setOperationsError(""); setOperationsNotice("");
    try {
      const response = await apiFetch(`/api/operator/restaurants/${restaurant.id}/toggle-activity/`, { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not change restaurant status.");
      setOperationsNotice(`${result.name} is now ${result.status}.`);
      await refreshOperations();
    } catch (err) {
      setOperationsError(err instanceof Error ? err.message : "Could not change restaurant status.");
    } finally { setPendingOperation(null); }
  }

  async function reassignOrder(assignmentId: number) {
    const courierId = selectedCouriers[assignmentId];
    if (!courierId || pendingOperation) return;
    setPendingOperation(`assignment:${assignmentId}`);
    setOperationsError(""); setOperationsNotice("");
    try {
      const response = await apiFetch(`/api/delivery/operator/assignments/${assignmentId}/reassign/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ courier_id: courierId }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not reassign this order.");
      setOperationsNotice(`Order #${result.order_id} was offered to a new courier.`);
      await refreshOperations();
    } catch (err) {
      setOperationsError(err instanceof Error ? err.message : "Could not reassign this order.");
    } finally { setPendingOperation(null); }
  }

  useEffect(() => {
    let disposed = false;
    let inFlight = false;
    async function refresh() {
      if (inFlight) return;
      inFlight = true;
      try {
        const response = await apiFetch("/api/operator/overview/");
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Could not load platform statistics.");
        if (!disposed) { setData(result); setError(""); }
      } catch (err) {
        if (!disposed) setError(err instanceof Error ? err.message : "Could not load platform statistics.");
      } finally {
        inFlight = false;
        if (!disposed) setLoading(false);
      }
    }
    void refresh();
    return () => { disposed = true; };
  }, []);

  return (
    <main className="page-container botanical-background" style={{ alignItems: "flex-start" }}>
      <div className="w-full max-w-[1280px] mx-auto">
        <header className="mb-9">
          <div>
            <p className="eyebrow">Five Leaf Clover · Platform operator</p>
            <h1 className="page-title mt-3">Platform overview</h1>
          </div>

          <nav aria-label="Operator dashboard" className="flex flex-wrap items-center gap-3 mt-6">
            <button type="button" aria-pressed={section === "overview"} className={`btn ${section === "overview" ? "btn-primary" : "btn-secondary"}`} onClick={() => setSection("overview")}>Overview</button>
            <button type="button" aria-pressed={section === "map"} className={`btn ${section === "map" ? "btn-primary" : "btn-secondary"}`} onClick={() => setSection("map")}>Map</button>
            <button type="button" aria-pressed={section === "operations"} className={`btn ${section === "operations" ? "btn-primary" : "btn-secondary"}`} onClick={() => setSection("operations")}>Operations</button>
            <Link
              href="/dashboard/operator/orders"
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-3 text-sm font-semibold hover:opacity-80 transition"
            >
              Order history →
            </Link>

            <Link
              href="/dashboard/operator/refunds"
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-3 text-sm font-semibold hover:opacity-80 transition"
            >
              Review refund requests →
            </Link>

            <Link
              href="/dashboard/operator/ledger"
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-3 text-sm font-semibold hover:opacity-80 transition"
            >
              View order ledger →
            </Link>
          </nav>
        </header>
        {section === "map" && <MontrealMap />}
        {section === "operations" && <section aria-labelledby="operator-operations-heading">
          <div className="mb-6 flex items-center justify-between gap-4">
            <div><p className="eyebrow">Platform controls</p><h2 id="operator-operations-heading" className="section-title mt-2">Operations</h2></div>
            <button type="button" className="btn btn-secondary" disabled={operationsLoading} onClick={() => void refreshOperations()}>{operationsLoading ? "Refreshing…" : "Refresh"}</button>
          </div>
          {operationsNotice && <p role="status" className="message message-success mb-4">{operationsNotice}</p>}
          {operationsError && <p role="alert" className="message message-error mb-4">{operationsError}</p>}
          {operationsLoading && !operations && <p role="status" className="body-text">Loading operations…</p>}
          {operations && <>
            <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 mb-6" aria-labelledby="operator-restaurants-heading">
              <div className="mb-4"><h3 id="operator-restaurants-heading" className="text-xl font-bold text-[var(--color-forest)]">Restaurants</h3><p className="form-help mt-1">Pause or reopen restaurant ordering.</p></div>
              <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {operations.restaurants.map((restaurant) => <li key={restaurant.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--color-border)] p-4">
                  <div><p className="font-semibold text-[var(--color-forest)]">{restaurant.name}</p><p className="form-help mt-1 capitalize">{restaurant.status}</p></div>
                  <button type="button" className={`btn ${restaurant.status === "open" ? "btn-secondary" : "btn-primary"}`} disabled={pendingOperation !== null} onClick={() => void toggleRestaurant(restaurant)}>{pendingOperation === `restaurant:${restaurant.id}` ? "Updating…" : restaurant.status === "open" ? "Pause restaurant" : "Reopen restaurant"}</button>
                </li>)}
                {!operations.restaurants.length && <li className="form-help">No restaurants.</li>}
              </ul>
            </section>
            <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6" aria-labelledby="offline-courier-orders-heading">
              <div className="mb-4"><h3 id="offline-courier-orders-heading" className="text-xl font-bold text-[var(--color-forest)]">Orders with an offline courier</h3><p className="form-help mt-1">Ready orders assigned to a courier who went offline can be offered to an available courier.</p></div>
              <ul className="space-y-3">
                {operations.offline_assignments.map((assignment) => <li key={assignment.assignment_id} className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(220px,280px)_auto] items-center gap-4 rounded-2xl border border-[var(--color-border)] p-4">
                  <div><p className="font-bold text-[var(--color-forest)]">Order #{assignment.order_id} · {assignment.restaurant_name}</p><p className="form-help mt-1">{assignment.customer_name} · currently assigned to offline courier {assignment.courier_name}</p><p className="mt-2 text-sm">{assignment.items.map((item) => `${item.quantity} × ${item.name}`).join(", ")}</p></div>
                  <label className="form-label">Reassign to
                    <select className="form-input mt-1" value={selectedCouriers[assignment.assignment_id] ?? ""} disabled={!operations.available_couriers.length} onChange={(event) => setSelectedCouriers((current) => ({ ...current, [assignment.assignment_id]: Number(event.target.value) }))}>
                      {!operations.available_couriers.length && <option value="">No couriers available</option>}
                      {operations.available_couriers.map((courier) => <option key={courier.id} value={courier.id}>{courier.username}</option>)}
                    </select>
                  </label>
                  <button type="button" className="btn btn-primary" disabled={!operations.available_couriers.length || pendingOperation !== null} onClick={() => void reassignOrder(assignment.assignment_id)}>{pendingOperation === `assignment:${assignment.assignment_id}` ? "Reassigning…" : "Reassign order"}</button>
                </li>)}
                {!operations.offline_assignments.length && <li className="rounded-2xl border border-dashed border-[var(--color-border)] p-6 text-center text-sm">No ready orders are waiting for courier reassignment.</li>}
              </ul>
            </section>
          </>}
        </section>}
        {section === "overview" && <>
        {loading && <p role="status" className="body-text">Loading platform statistics…</p>}
        {error && <div role="alert" className="message message-error mb-6"><p>{error}</p><p className="mt-2">{data ? "Showing the last successful update. " : ""}<Link href="/login">Return to login</Link></p></div>}
        {data && <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5 mb-8">
            {[
              { label: "Total users", value: data.total_users },
              { label: "Restaurants", value: data.total_restaurants },
              { label: "Active orders", value: data.active_orders },
              { label: "Total orders", value: data.total_orders },
            ].map((stat) => <section key={stat.label} className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
              <h2 className="text-sm font-semibold text-[var(--color-muted)]">{stat.label}</h2><p className="text-4xl font-bold text-[var(--color-forest)] mt-4 tabular-nums">{number(stat.value)}</p>
            </section>)}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
            <Breakdown title="People" labels={roles} counts={data.users_by_role} total={data.total_users} />
            <Breakdown title="Restaurants" labels={restaurantStatuses} counts={data.restaurants_by_status} total={data.total_restaurants} />
            <Breakdown title="Order activity" labels={orderStatuses} counts={data.orders_by_status} total={data.total_orders} />
          </div>
        </>}
        </>}
      </div>
    </main>
  );
}
