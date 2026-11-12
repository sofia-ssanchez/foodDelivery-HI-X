"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

type Delivery = {
  id: number;
  restaurant_name: string;
  customer_name: string;
  courier_id: number | null;
  status: string;
  created_at: string;
  latitude: string;
  longitude: string;
  lines: { id: number; name: string; quantity: number }[];
};
const tabs = ["Available", "My deliveries", "History"] as const;
type Tab = (typeof tabs)[number];
const active = (order: Delivery) => ["ready", "picked_up"].includes(order.status);
const labels: Record<string, string> = {
  ready: "Awaiting pickup", picked_up: "Out for delivery", delivered: "Delivered",
  cancelled: "Cancelled", partially_refunded: "Partially refunded", refunded: "Refunded",
};

export default function CourierDashboard() {
  const [orders, setOrders] = useState<Delivery[]>([]);
  const [tab, setTab] = useState<Tab>("Available");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pending, setPending] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const busy = useRef(false);

  const loadOrders = useCallback(async () => {
    const response = await apiFetch("/api/courier/orders/");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load deliveries.");
    setOrders(data);
  }, []);

  const refresh = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setRefreshing(true);
    try {
      await loadOrders();
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load deliveries.");
    } finally {
      busy.current = false;
      setLoading(false);
      setRefreshing(false);
    }
  }, [loadOrders]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function act(order: Delivery, action: "claim" | "deliver") {
    if (busy.current) return;
    busy.current = true;
    setPending(order.id);
    setError("");
    setNotice("");
    try {
      const response = await apiFetch(`/api/courier/orders/${order.id}/action/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not update this delivery.");
      setOrders((current) => current.map((item) => item.id === order.id ? data : item));
      setNotice(action === "claim" ? `Order #${order.id} is now assigned to you.` : `Order #${order.id} marked delivered.`);
      setTab(action === "claim" ? "My deliveries" : "History");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update this delivery.");
    } finally {
      try { await loadOrders(); } catch { /* Retain the last successful board and action message. */ }
      busy.current = false;
      setPending(null);
    }
  }

  const groups: Record<Tab, Delivery[]> = {
    Available: orders.filter((order) => order.courier_id === null && active(order)),
    "My deliveries": orders.filter((order) => order.courier_id !== null && active(order)),
    History: orders.filter((order) => order.courier_id !== null && !active(order)).reverse(),
  };
  const hasActiveDelivery = groups["My deliveries"].length > 0;
  const disabled = refreshing || pending !== null;

  return (
    <main className="page-container botanical-background" style={{ alignItems: "flex-start" }}>
      <section className="w-full max-w-[1440px] mx-auto">
        <header className="flex flex-wrap items-end justify-between gap-4 mb-8">
          <div>
            <p className="eyebrow">Five Leaf Clover · Courier</p>
            <h1 className="page-title mt-3">Your delivery dashboard</h1>
            <p className="body-text mt-3">Find a delivery, collect the order, and bring it to its customer.</p>
          </div>
          <button type="button" className="btn btn-secondary" disabled={disabled} onClick={() => void refresh()}>
            {refreshing ? "Refreshing…" : "Refresh deliveries"}
          </button>
        </header>
        <nav aria-label="Delivery categories" className="grid gap-4 sm:grid-cols-3 mb-6">
          {tabs.map((item) => (
            <button key={item} type="button" aria-pressed={tab === item} onClick={() => setTab(item)}
              className={`rounded-2xl border p-5 text-left ${tab === item ? "bg-[var(--color-forest)] text-white" : "bg-[var(--color-surface)] border-[var(--color-border)]"}`}>
              <span className="block text-sm font-semibold">{item}</span>
              <span className="block mt-2 text-3xl font-semibold">{loading ? "—" : groups[item].length}</span>
            </button>
          ))}
        </nav>
        {tab === "Available" && hasActiveDelivery && <p role="status" className="body-text mb-4">Finish your current delivery before claiming another order.</p>}
        {error && <p role="alert" className="message message-error mb-4">{error}</p>}
        {notice && <p role="status" className="message message-success mb-4">{notice}</p>}
        <div className="flex flex-wrap justify-between gap-2 mb-4">
          <h2 className="section-title">{tab}</h2>
          <p className="body-text text-sm">Updates every 15 seconds</p>
        </div>
        {loading ? <p role="status" className="form-card">Loading deliveries…</p> : groups[tab].length === 0 ? (
          <div className="form-card text-center py-12">
            <h3 className="section-title">{tab === "Available" ? "No deliveries available yet" : tab === "My deliveries" ? "You're ready for your next delivery" : "No delivery history yet"}</h3>
            <p className="body-text mt-3">{tab === "Available" ? "Orders appear here when restaurants mark them ready." : tab === "My deliveries" ? "Claim an available order to get started." : "Completed and cancelled assignments will appear here."}</p>
          </div>
        ) : (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {groups[tab].map((order) => (
              <article key={order.id} className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 flex flex-col">
                <div className="flex justify-between items-center gap-3">
                  <p className="eyebrow">Order #{order.id}</p>
                  <span className="rounded-full bg-[var(--color-sage-light)] text-[var(--color-forest)] px-3 py-1 text-xs font-semibold">{labels[order.status] || order.status}</span>
                </div>
                <h3 className="section-title mt-4">{order.restaurant_name}</h3>
                <p className="body-text mt-2">Customer: {order.customer_name}</p>
                <p className="body-text text-sm mt-1">Placed {new Date(order.created_at).toLocaleString()}</p>
                <p className="body-text text-sm mt-2">Pickup coordinates: {order.latitude}, {order.longitude}</p>
                <ul className="my-5 border-y border-[var(--color-border)] py-4 space-y-2">
                  {order.lines.map((line) => <li key={line.id}>{line.quantity} × {line.name}</li>)}
                </ul>
                <div className="mt-auto">
                  {tab === "Available" && <button type="button" className="btn btn-primary btn-full" disabled={disabled || hasActiveDelivery} onClick={() => void act(order, "claim")}>{pending === order.id ? "Claiming…" : hasActiveDelivery ? "Finish current delivery first" : "Claim delivery"}</button>}
                  {tab === "My deliveries" && (order.status === "ready" ? <p className="body-text">Collect the order at the restaurant. The restaurant will confirm pickup.</p> : <button type="button" className="btn btn-primary btn-full" disabled={disabled} onClick={() => void act(order, "deliver")}>{pending === order.id ? "Updating…" : "Confirm delivered"}</button>)}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
