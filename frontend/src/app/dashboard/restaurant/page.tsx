"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

type Restaurant = {
  id: number;
  name: string;
  status: "open" | "paused" | "closed";
};

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
  { status: "placed", title: "Placed", description: "Approval queue · Accept or decline oldest first", action: "Accept order", next: "accepted", empty: "New orders will appear here.", color: "#E7D5A5" },
  { status: "accepted", title: "Accepted", description: "Prep queue · Oldest order starts first", action: "Start preparing", next: "preparing", empty: "Accepted orders will appear here.", color: "#B9D987" },
  { status: "preparing", title: "Preparing", description: "In the kitchen", action: "Mark ready for pick up", next: "ready", empty: "Orders being prepared will appear here.", color: "#43834A" },
  { status: "ready", title: "Waiting for pick up", description: "Ready and awaiting collection", action: "", next: "", empty: "Orders waiting for pick up will appear here.", color: "#285638" },
  { status: "picked_up", title: "Picked up", description: "Collected from the restaurant", action: "", next: "", empty: "Collected orders will appear here.", color: "#777C65" },
];
const money = (value: string | number) => new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" }).format(Number(value));

export default function RestaurantDashboard() {
  const [selectedStage, setSelectedStage] = useState("all");
  const [orders, setOrders] = useState<Order[]>([]);
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [notice, setNotice] = useState("");
  const [noticePaused, setNoticePaused] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [pending, setPending] = useState<number | null>(null);
  const [pendingRestaurant, setPendingRestaurant] = useState<number | null>(null);
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
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function advance(order: Order, next: string, title: string) {
    if (busy.current) return;
    busy.current = true;
    setPending(order.id);
    setError("");
    setNotice("");
    setNoticePaused(false);
    try {
      const response = await apiFetch(`/api/restaurant/orders/${order.id}/status/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next, expected_status: order.status }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not update this order.");
      setOrders((current) => current.map((item) => item.id === order.id ? data : item));
      setNotice(next === "rejected" ? `Order #${order.id} declined.` : `Order #${order.id} moved to ${title}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update this order.");
    } finally {
      busy.current = false;
      setPending(null);
    }
  }

  async function toggleActivity(restaurant: Restaurant) {
    if (busy.current || restaurant.status === "closed") return;
    busy.current = true;
    setPendingRestaurant(restaurant.id);
    setError("");
    setNotice("");
    setNoticePaused(false);
    try {
      const response = await apiFetch(`/api/restaurants/${restaurant.id}/toggle-activity/`, {
        method: "POST",
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not update restaurant activity.");
      setRestaurants((current) => current.map((item) => item.id === restaurant.id ? data : item));
      setNotice(`${data.name} is now ${data.status}.`);
      setNoticePaused(data.status === "paused");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update restaurant activity.");
    } finally {
      busy.current = false;
      setPendingRestaurant(null);
    }
  }

  const sortedOrders = [...orders].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || a.id - b.id);
  const queueKey = (order: Order) => `${order.restaurant_id}:${order.status}`;
  const queueHeads = new Map<string, number>();
  sortedOrders
    .filter((order) => order.status === "placed" || order.status === "accepted")
    .forEach((order) => {
      if (!queueHeads.has(queueKey(order))) queueHeads.set(queueKey(order), order.id);
    });

  const isWaiting = (order: Order) => (order.status === "placed" || order.status === "accepted") && queueHeads.get(queueKey(order)) !== order.id;

  return (
    <main className="page-container botanical-background" style={{ alignItems: "flex-start" }}>
      <section className="w-full max-w-[1600px] mx-auto">
        <header className="mb-8">
          <p className="eyebrow">Five Leaf Clover</p>
          <h1 className="page-title mt-3">{restaurants.length ? restaurants.map((restaurant) => restaurant.name).join(" · ") : "Your restaurant"}</h1>
          <div className="mt-4 flex flex-wrap gap-3">
            {restaurants.map((restaurant) => (
              <div key={restaurant.id} className="flex flex-wrap items-center gap-3">
                <span>{restaurant.name} · {restaurant.status}</span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={loading || refreshing || pending !== null || pendingRestaurant !== null || restaurant.status === "closed"}
                  onClick={() => void toggleActivity(restaurant)}
                  aria-label={`${restaurant.status === "paused" ? "Resume" : "Pause"} activity for ${restaurant.name}`}
                >
                  {pendingRestaurant === restaurant.id ? "Updating…" : restaurant.status === "closed" ? "Closed" : restaurant.status === "paused" ? "Resume activity" : "Pause activity"}
                </button>
              </div>
            ))}
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-[200px_minmax(0,1fr)] gap-6 items-start">
          <nav aria-label="Restaurant order views" className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 flex flex-col gap-3 md:sticky md:top-5">
            <p className="eyebrow px-2 mb-2">Orders</p>
            {[{ status: "all", title: "All orders" }, ...stages].map((item) => {
              const count = orders.filter((order) => item.status === "all" ? stages.some((stage) => stage.status === order.status) : order.status === item.status).length;
              return <button key={item.status} type="button" aria-pressed={selectedStage === item.status} className={`btn btn-full flex justify-between gap-3 ${selectedStage === item.status ? "btn-primary" : "btn-secondary"}`} onClick={() => setSelectedStage(item.status)}>
                <span className="flex-1 text-left">{item.title}</span><span className="tabular-nums shrink-0 text-right" aria-label={`${count} orders`}>{loaded ? count : "—"}</span>
              </button>;
            })}
          </nav>
          <div className="min-w-0">
        <div className="flex items-center justify-between gap-3 mb-5">
          <div role="status" aria-live="polite" className="flex-1 min-w-0">{notice && <p className={`message ${noticePaused ? "message-warning" : "message-success"}`}>{notice}</p>}</div>
          <button type="button" className="btn btn-secondary shrink-0" disabled={loading || refreshing || pending !== null || pendingRestaurant !== null} onClick={requestRefresh}>{refreshing ? "Refreshing…" : "Refresh orders"}</button>
        </div>
        {error && <p role="alert" className="message message-error mb-5">{error}</p>}
        {loading && <p role="status" className="body-text mb-5">Loading your orders…</p>}
        {loaded && !restaurants.length && <p className="message mb-5">No restaurant is linked to your account yet.</p>}
        
          {loaded && <div className={selectedStage === "all" ? "grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-5 items-start" : "grid grid-cols-1 gap-5"}>
            {stages.map((stage, index) => {
              if (selectedStage !== "all" && selectedStage !== stage.status) return null;
              const items = sortedOrders.filter((order) => order.status === stage.status);
              return (
                <section key={stage.status} className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)]/70 p-4 min-w-0" aria-labelledby={`heading-${stage.status}`}>
                  <div className="h-1 rounded-full mb-4" style={{ background: stage.color }} />
                  <div className="flex items-center justify-between gap-3 mb-5">
                    <h3 id={`heading-${stage.status}`} className="text-lg font-bold text-[var(--color-forest)]">{stage.title}</h3>
                    <span className="rounded-full bg-[var(--color-sage-light)] px-3 py-1 text-sm font-semibold" aria-label={`${items.length} orders`}>{items.length}</span>
                  </div>
                  <div className={selectedStage === "all" ? "flex flex-col gap-4" : "grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 items-start"}>
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
                        {stage.next ? <button type="button" className="btn btn-primary btn-full" disabled={pending !== null || pendingRestaurant !== null || refreshing || isWaiting(order)} onClick={() => void advance(order, stage.next, stages[index + 1].title)} aria-label={`${isWaiting(order) ? "Waiting for earlier orders" : stage.action} for order ${order.id}`}>{pending === order.id ? "Updating…" : isWaiting(order) ? "Waiting in queue" : `${stage.action} →`}</button> : <p className="rounded-xl bg-[var(--color-sage-light)] text-[var(--color-forest)] py-3 text-center text-sm font-semibold">{order.status === "ready" ? "Awaiting courier pickup confirmation" : "✓ Picked up"}</p>}
                        {order.status === "placed" && <button type="button" className="btn btn-secondary btn-full mt-2" disabled={pending !== null || pendingRestaurant !== null || refreshing || isWaiting(order)} onClick={() => void advance(order, "rejected", "Declined")} aria-label={`Decline order ${order.id}`}>Decline order</button>}
                      </article>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>}
          </div>
        </div>
      </section>
    </main>
  );
}
