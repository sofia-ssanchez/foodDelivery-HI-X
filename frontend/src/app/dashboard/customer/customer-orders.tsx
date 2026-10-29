"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

type Order = {
  id: number;
  restaurant_name: string;
  status: string;
  created_at: string;
  total: string;
  lines: { id: number; name: string; quantity: number; unit_price: string }[];
};
const pastStatuses = new Set(["delivered", "rejected", "cancelled"]);
const statusLabels: Record<string, string> = {
  placed: "Placed · Waiting for approval", accepted: "Accepted", preparing: "Preparing",
  ready: "Ready for pickup", picked_up: "Out for delivery", delivered: "Delivered",
  rejected: "Declined", cancelled: "Cancelled",
};
const money = (value: string | number) => new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" }).format(Number(value));

export default function CustomerOrders({ category }: { category: "active" | "past" }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const busy = useRef(false);
  const mounted = useRef(false);

  const refresh = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    try {
      const response = await apiFetch("/api/customer/orders/");
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load your orders.");
      if (mounted.current) { setOrders(data); setError(""); setUpdatedAt(new Date()); }
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : "Could not load your orders.");
    } finally {
      busy.current = false;
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    const initial = setTimeout(() => void refresh(), 0);
    return () => { mounted.current = false; clearTimeout(initial); };
  }, [refresh]);

  const visibleOrders = orders.filter((order) => pastStatuses.has(order.status) === (category === "past"));
  return <section>
    <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
      <div><h2 className="section-title">{category === "active" ? "Active orders" : "Past orders"}</h2><p className="form-help mt-2">{category === "active" ? "Track your orders from approval to delivery." : "Your delivered, declined, and cancelled orders."}</p></div>
      <button type="button" className="btn btn-secondary" disabled={loading} onClick={() => { if (!busy.current) { setLoading(true); void refresh(); } }}>{loading ? "Refreshing…" : "Refresh orders"}</button>
    </div>
    {error && <p role="alert" className="message message-error mb-5">{error}{updatedAt ? " Showing the last successful update." : ""}</p>}
    {loading && !updatedAt && <p role="status" className="body-text">Loading your orders…</p>}
    {updatedAt && !visibleOrders.length && <div className="form-card"><h3 className="font-semibold">{category === "active" ? "No active orders" : "No past orders yet"}</h3><p className="form-help mt-2">{category === "active" ? "Choose Order food in the sidebar to place an order." : "Finished orders will appear here."}</p></div>}
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
      {visibleOrders.map((order) => <article key={order.id} className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
        <div className="flex flex-wrap justify-between items-start gap-3"><div><h3 className="text-lg font-bold text-[var(--color-forest)]">{order.restaurant_name}</h3><p className="form-help mt-1">Order #{order.id}</p></div><span className="rounded-full bg-[var(--color-sage-light)] px-3 py-2 text-sm font-semibold">{statusLabels[order.status] ?? order.status}</span></div>
        <time className="block form-help mt-3" dateTime={order.created_at}>{new Date(order.created_at).toLocaleString("en-CA")}</time>
        <ul className="my-5 py-4 border-y border-[var(--color-border)] space-y-3">{order.lines.map((line) => <li key={line.id} className="flex justify-between gap-4 text-sm"><span>{line.quantity} × {line.name}</span><span className="shrink-0">{money(Number(line.unit_price) * line.quantity)}</span></li>)}</ul>
        <div className="flex justify-between font-bold"><span>Total</span><span>{money(order.total)}</span></div>
      </article>)}
    </div>
  </section>;
}
