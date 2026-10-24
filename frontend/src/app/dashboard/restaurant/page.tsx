"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

type Order = {
  id: number;
  restaurant_id: number;
  restaurant_name: string;
  customer_name: string;
  status: string;
  created_at: string;
  total: string;
  lines: { id: number; name: string; quantity: number; unit_price: string }[];
};

const stages = [
  { status: "placed", title: "Placed", description: "Pending your approval", action: "Accept order", next: "accepted", empty: "New orders will appear here.", color: "#E7D5A5" },
  { status: "accepted", title: "Accepted", description: "Prep queue · Oldest order starts first", action: "Start preparing", next: "preparing", empty: "Accepted orders will appear here.", color: "#B9D987" },
  { status: "preparing", title: "Preparing", description: "In the kitchen", action: "Mark as done", next: "ready", empty: "Orders being prepared will appear here.", color: "#43834A" },
  { status: "ready", title: "Done", description: "Ready for pickup", action: "", next: "", empty: "Finished orders will appear here.", color: "#285638" },
];
const money = (value: string | number) => new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" }).format(Number(value));

export default function RestaurantDashboard() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [restaurants, setRestaurants] = useState<{ id: number; name: string }[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [pending, setPending] = useState<number | null>(null);
  const busy = useRef(false);

  const refresh = useCallback(() => {
    if (busy.current) return;
    busy.current = true;
    void apiFetch("/api/restaurant/orders/")
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not load your orders.");
        return data;
      })
      .then((data) => {
        setRestaurants(data.restaurants);
        setOrders(data.orders);
        setLoaded(true);
        setError("");
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Could not load your orders.");
      })
      .finally(() => {
        busy.current = false;
        setLoading(false);
        setRefreshing(false);
      });
  }, []);

  const requestRefresh = useCallback(() => {
    if (busy.current) return;
    setRefreshing(true);
    void refresh();
  }, [refresh]);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => { if (!document.hidden) requestRefresh(); }, 15000);
    return () => clearInterval(timer);
  }, [refresh, requestRefresh]);

  async function advance(order: Order, next: string, title: string) {
    if (busy.current) return;
    busy.current = true;
    setPending(order.id);
    setError("");
    setNotice("");
    try {
      const response = await apiFetch(`/api/restaurant/orders/${order.id}/status/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next, expected_status: order.status }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not update this order.");
      setOrders((current) => current.map((item) => item.id === order.id ? data : item));
      setNotice(`Order #${order.id} moved to ${title}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update this order.");
    } finally {
      busy.current = false;
      setPending(null);
    }
  }

  const queueHeads = new Map<number, number>();
  [...orders]
    .filter((order) => order.status === "accepted")
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || a.id - b.id)
    .forEach((order) => {
      if (!queueHeads.has(order.restaurant_id)) queueHeads.set(order.restaurant_id, order.id);
    });

  const isWaiting = (order: Order) => order.status === "accepted" && queueHeads.get(order.restaurant_id) !== order.id;

  return (
    <main className="page-container botanical-background" style={{ alignItems: "flex-start" }}>
      <section className="w-full max-w-[1440px] mx-auto">
        <header className="mb-8">
          <p className="eyebrow">Five Leaf Clover</p>
          <h1 className="page-title mt-3">{restaurants.length ? restaurants.map((restaurant) => restaurant.name).join(" · ") : "Your restaurant"}</h1>
        </header>

        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <div><h2 className="section-title">Order board</h2><p className="form-help mt-1">Oldest orders first · Refreshes every 15 seconds</p></div>
          <button type="button" className="btn btn-secondary" disabled={loading || refreshing || pending !== null} onClick={requestRefresh}>{refreshing ? "Refreshing…" : "Refresh orders"}</button>
        </div>
        {error && <p role="alert" className="message message-error mb-5">{error}</p>}
        {loading && <p role="status" className="body-text mb-5">Loading your orders…</p>}
        {loaded && !restaurants.length && <p className="message mb-5">No restaurant is linked to your account yet.</p>}
        <div role="status" aria-live="polite">{notice && <p className="message message-success mb-5">{notice}</p>}</div>
        
          {loaded && <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5 items-start">
            {stages.map((stage, index) => {
              const items = orders.filter((order) => order.status === stage.status);
              return (
                <section key={stage.status} className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)]/70 p-4 min-w-0" aria-labelledby={`heading-${stage.status}`}>
                  <div className="h-1 rounded-full mb-4" style={{ background: stage.color }} />
                  <div className="flex items-center justify-between gap-3">
                    <h3 id={`heading-${stage.status}`} className="text-lg font-bold text-[var(--color-forest)]">{stage.title}</h3>
                    <span className="rounded-full bg-[var(--color-sage-light)] px-3 py-1 text-sm font-semibold" aria-label={`${items.length} orders`}>{items.length}</span>
                  </div>
                  <p className="form-help mt-1 mb-5">{stage.description}</p>
                  <div className="flex flex-col gap-4">
                    {!items.length && <div className="rounded-2xl border border-dashed border-[var(--color-border)] p-6 text-center"><p className="text-sm font-semibold">All clear here</p><p className="form-help mt-2">{stage.empty}</p></div>}
                    {items.map((order) => (
                      <article key={order.id} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-sm">
                        <div className="flex justify-between items-start gap-2"><h4 className="font-bold text-[var(--color-forest)]">Order #{order.id}</h4><time className="form-help text-right" dateTime={order.created_at}>{new Date(order.created_at).toLocaleString("en-CA", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</time></div>
                        <p className="text-sm mt-2 break-words">{order.customer_name}</p>
                        <p className="form-help mt-1 break-words">{order.restaurant_name}</p>
                        <ul className="my-4 py-3 border-y border-[var(--color-border)] space-y-3">
                          {order.lines.map((line) => <li key={line.id} className="flex justify-between gap-2 text-sm"><span className="break-words"><strong>{line.quantity} ×</strong> {line.name}</span><span className="shrink-0">{money(Number(line.unit_price) * line.quantity)}</span></li>)}
                        </ul>
                        <div className="flex justify-between text-sm font-bold mb-4"><span>Total</span><span>{money(order.total)}</span></div>
                        {stage.next ? <button type="button" className="btn btn-primary btn-full" disabled={pending !== null || refreshing || isWaiting(order)} onClick={() => void advance(order, stage.next, stages[index + 1].title)} aria-label={`${isWaiting(order) ? "Waiting for earlier orders" : stage.action} for order ${order.id}`}>{pending === order.id ? "Updating…" : isWaiting(order) ? "Waiting in queue" : `${stage.action} →`}</button> : <p className="rounded-xl bg-[var(--color-sage-light)] text-[var(--color-forest)] py-3 text-center text-sm font-semibold">✓ Ready for pickup</p>}
                      </article>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>}
      </section>
    </main>
  );
}
