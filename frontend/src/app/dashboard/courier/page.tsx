"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import SignedInAccount from "@/components/signed-in-account";
import MontrealMap from "@/components/montreal-map";

type Delivery = {
  id: number;
  restaurant_name: string;
  customer_name: string;
  order_id: number;
  delivery_address: string;
  delivery_unit: string;
  order_status: string;
  picked_up_at: string | null;
  delivered_at: string | null;
  status: string;
  created_at: string;
  restaurant_latitude: string;
  restaurant_longitude: string;
  lines: { id: number; name: string; quantity: number }[];
};
type Courier = { status: "offline" | "idle" | "assigned" | "carrying" };
type Activity = { courier: Courier; offers: Delivery[]; active_assignment: Delivery | null; history: Delivery[] };
const tabs = ["Offers", "My deliveries", "History"] as const;
type Tab = (typeof tabs)[number];
const labels: Record<string, string> = {
  ready: "Awaiting pickup", picked_up: "Out for delivery", delivered: "Delivered",
  offered: "Delivery offer", accepted: "Accepted", completed: "Completed", declined: "Declined", reassigned: "Reassigned",
  cancelled: "Cancelled", partially_refunded: "Partially refunded", refunded: "Refunded",
};

export default function CourierDashboard() {
  const [activity, setActivity] = useState<Activity | null>(null);
  const [tab, setTab] = useState<Tab | "Map">("Offers");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pending, setPending] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const busy = useRef(false);

  const loadOrders = useCallback(async () => {
    const response = await apiFetch("/api/delivery/me/");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load deliveries.");
    setActivity(data);
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

  async function mutate(url: string, method: string, body: object | undefined, message: string, nextTab?: Tab, id = -1) {
    if (busy.current) return;
    busy.current = true;
    setPending(id);
    setError("");
    setNotice("");
    try {
      const response = await apiFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : typeof data[0] === "string" ? data[0] : "Could not update delivery activity.");
      setNotice(message);
      if (nextTab) setTab(nextTab);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update delivery activity.");
    } finally {
      try { await loadOrders(); } catch {
        setError("Could not refresh delivery activity. Refresh before taking another action.");
      }
      busy.current = false;
      setPending(null);
    }
  }

  function act(order: Delivery, action: "accept" | "decline" | "pickup" | "deliver") {
    const resource = action === "accept" || action === "decline" ? "offers" : "assignments";
    const messages = { accept: "accepted", decline: "declined", pickup: "picked up", deliver: "delivered" };
    void mutate(`/api/delivery/${resource}/${order.id}/${action}/`, "POST", undefined,
      `Order #${order.order_id} ${messages[action]}.`,
      action === "accept" || action === "pickup" ? "My deliveries" : "Offers", order.id);
  }

  const groups: Record<Tab, Delivery[]> = {
    Offers: activity?.offers ?? [],
    "My deliveries": activity?.active_assignment ? [activity.active_assignment] : [],
    History: activity?.history ?? [],
  };
  const hasActiveDelivery = groups["My deliveries"].length > 0;
  const disabled = loading || refreshing || pending !== null || !activity;
  const courierStatus = activity?.courier.status;

  return (
    <main className="page-container botanical-background" style={{ alignItems: "flex-start" }}>
      <section className="w-full max-w-[1440px] mx-auto">
        <header className="flex flex-wrap items-end justify-between gap-4 mb-8">
          <div>
            <p className="eyebrow">Five Leaf Clover · Courier</p>
            <h1 className="page-title mt-3">Your delivery dashboard</h1>
          <SignedInAccount />
          </div>
          <button type="button" className="btn btn-secondary" disabled={disabled} onClick={() => void refresh()}>
            {refreshing ? "Refreshing…" : "Refresh deliveries"}
          </button>
        </header>
        <div className="flex flex-wrap items-center gap-4 mb-6">
          <p role="status" className="body-text">Courier status: <strong>{courierStatus === "idle" ? "Online · Available" : courierStatus === "assigned" ? "Assigned" : courierStatus === "carrying" ? "Carrying an order" : courierStatus === "offline" ? "Offline" : "Loading…"}</strong></p>
          <button type="button" className="btn btn-secondary" disabled={disabled || courierStatus === "carrying"}
            onClick={() => void mutate("/api/delivery/duty/", "PATCH", { on_duty: courierStatus === "offline" }, courierStatus === "offline" ? "You are online." : "You are offline.")}>
            {pending === -1 ? "Updating…" : courierStatus === "offline" ? "Go online" : "Go offline"}
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-[200px_minmax(0,1fr)] gap-6 items-start">
          <nav aria-label="Courier dashboard menu" className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 flex flex-col gap-3 md:sticky md:top-5">
            <p className="eyebrow px-2 mb-2">Courier menu</p>
            {(["Map", ...tabs] as const).map((item) => <button key={item} type="button" aria-pressed={tab === item} onClick={() => setTab(item)}
              className={`btn btn-full flex justify-between gap-3 ${tab === item ? "btn-primary" : "btn-secondary"}`}>
              <span>{item}</span>{item !== "Map" && <span>{loading ? "—" : groups[item].length}</span>}
            </button>)}
          </nav>
          <div className="min-w-0">
        {error && <p role="alert" className="message message-error mb-4">{error}</p>}
        {notice && <p role="status" className="message message-success mb-4">{notice}</p>}
        <div className="flex flex-wrap justify-between gap-2 mb-4">
          <h2 className="section-title">{tab}</h2>
        </div>
        {tab === "Map" ? <MontrealMap /> : loading ? <p role="status" className="form-card">Loading deliveries…</p> : groups[tab].length === 0 ? (
          <div className="form-card text-center py-12">
            <h3 className="section-title">{tab === "Offers" ? "No delivery offers yet" : tab === "My deliveries" ? "You're ready for your next delivery" : "No delivery history yet"}</h3>
          </div>
        ) : (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {groups[tab].map((order) => (
              <article key={order.id} className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 flex flex-col">
                <div className="flex justify-between items-center gap-3">
                  <p className="eyebrow">Order #{order.order_id}</p>
                  <span className="rounded-full bg-[var(--color-sage-light)] text-[var(--color-forest)] px-3 py-1 text-xs font-semibold">{order.status === "accepted" ? labels[order.order_status] || order.order_status : labels[order.status] || order.status}</span>
                </div>
                <h3 className="section-title mt-4">{order.restaurant_name}</h3>
                <p className="body-text mt-2">Customer: {order.customer_name}</p>
                {order.delivery_address && <p className="body-text mt-2">Deliver to: {order.delivery_address}{order.delivery_unit ? ` · Unit ${order.delivery_unit}` : ""}</p>}
                <p className="body-text text-sm mt-1">Placed {new Date(order.created_at).toLocaleString()}</p>
                <p className="body-text text-sm mt-2">Pickup coordinates: {order.restaurant_latitude}, {order.restaurant_longitude}</p>
                <ul className="my-5 border-y border-[var(--color-border)] py-4 space-y-2">
                  {order.lines.map((line) => <li key={line.id}>{line.quantity} × {line.name}</li>)}
                </ul>
                <div className="mt-auto">
                  {tab === "Offers" && <div className="flex flex-wrap gap-2">
                    <button type="button" className="btn btn-primary" disabled={disabled || hasActiveDelivery || courierStatus !== "idle"} onClick={() => act(order, "accept")}>{pending === order.id ? "Updating…" : "Accept offer"}</button>
                    <button type="button" className="btn btn-secondary" disabled={disabled} onClick={() => act(order, "decline")}>Decline</button>
                  </div>}
                  {tab === "My deliveries" && (courierStatus === "offline" ? <p className="body-text">Go online to continue this delivery.</p> : <button type="button" className="btn btn-primary btn-full" disabled={disabled} onClick={() => act(order, order.order_status === "ready" ? "pickup" : "deliver")}>{pending === order.id ? "Updating…" : order.order_status === "ready" ? "Confirm pickup" : "Confirm delivered"}</button>)}
                  {order.picked_up_at && <p className="body-text text-sm mt-3">Picked up: {new Date(order.picked_up_at).toLocaleString()}</p>}
                  {order.delivered_at && <p className="body-text text-sm mt-2">Delivered: {new Date(order.delivered_at).toLocaleString()}</p>}
                </div>
              </article>
            ))}
          </div>
        )}
          </div>
        </div>
      </section>
    </main>
  );
}
