"use client";

import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import MontrealMap from "@/components/montreal-map";

type Restaurant = {
  id: number;
  name: string;
  address: string;
  status: "open" | "paused" | "closed";
};

type Order = {
  id: number;
  restaurant_id: number;
  restaurant_name: string;
  customer_name: string;
  status: string;
  rejection_reason: string;
  created_at: string;
  total: string;
  lines: { id: number; name: string; quantity: number; unit_price: string }[];
};

type MenuItem = {
  id: number;
  restaurant: number;
  name: string;
  price: string;
  status: "available" | "sold_out";
};

type Promotion = {
  id: number;
  restaurant_id: number;
  code: string;
  discount_type: "fixed" | "percentage";
  discount: string;
  minimum_order: string;
  expires_at: string;
  is_active: boolean;
};

type PromotionDraft = Omit<Promotion, "id" | "restaurant_id">;

const stages = [
  { status: "placed", title: "Placed", action: "Accept order", next: "accepted", color: "#E7D5A5" },
  { status: "accepted", title: "Accepted", action: "Start preparing", next: "preparing", color: "#B9D987" },
  { status: "preparing", title: "Preparing", action: "Mark ready for pick up", next: "ready", color: "#43834A" },
  { status: "ready", title: "Waiting for pick up", action: "", next: "", color: "#285638" },
  { status: "picked_up", title: "Picked up", action: "", next: "", color: "#777C65" },
];
const money = (value: string | number) => new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD" }).format(Number(value));
const localDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
};

export default function RestaurantDashboard() {
  const [selectedStage, setSelectedStage] = useState("all");
  const [orders, setOrders] = useState<Order[]>([]);
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [restaurantName, setRestaurantName] = useState("");
  const [restaurantAddressQuery, setRestaurantAddressQuery] = useState("");
  const [restaurantAddresses, setRestaurantAddresses] = useState<{ address: string; token: string }[]>([]);
  const [restaurantAddressToken, setRestaurantAddressToken] = useState("");
  const [addressTargetId, setAddressTargetId] = useState<number | null>(null);
  const [creatingRestaurant, setCreatingRestaurant] = useState(false);
  const [menuItems, setMenuItems] = useState<Record<number, MenuItem[]>>({});
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [promoDrafts, setPromoDrafts] = useState<Record<number, PromotionDraft>>({});
  const [newMenuDrafts, setNewMenuDrafts] = useState<Record<number, { name: string; price: string }>>({});
  const [pendingMenu, setPendingMenu] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [noticePaused, setNoticePaused] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [pending, setPending] = useState<number | null>(null);
  const [pendingRestaurant, setPendingRestaurant] = useState<number | null>(null);
  const [decliningOrderId, setDecliningOrderId] = useState<number | null>(null);
  const [rejectionReasons, setRejectionReasons] = useState<Record<number, string>>({});
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
      .then(async (data) => {
        const menuEntries = await Promise.all(data.restaurants.map(async (restaurant: Restaurant) => {
          const response = await apiFetch(`/api/restaurants/${restaurant.id}/menu/`);
          const menuData = await response.json();
          if (!response.ok) throw new Error(menuData.detail || `Could not load ${restaurant.name}'s menu.`);
          return [restaurant.id, Array.isArray(menuData) ? menuData : menuData.results ?? []] as const;
        }));
        const promoResponse = await apiFetch("/api/promotions/");
        const promoData = await promoResponse.json();
        if (!promoResponse.ok) throw new Error(promoData.detail || "Could not load your promo codes.");
        setRestaurants(data.restaurants);
        setOrders(data.orders);
        setMenuItems(Object.fromEntries(menuEntries));
        setPromotions(promoData);
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

  async function advance(order: Order, next: string, title: string, rejectionReason = "") {
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
        body: JSON.stringify({ status: next, expected_status: order.status, ...(next === "rejected" ? { rejection_reason: rejectionReason } : {}) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not update this order.");
      setOrders((current) => current.map((item) => item.id === order.id ? data : item));
      setDecliningOrderId(null);
      setRejectionReasons((current) => { const nextReasons = { ...current }; delete nextReasons[order.id]; return nextReasons; });
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

  async function createRestaurant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    busy.current = true;
    setCreatingRestaurant(true);
    setError("");
    setNotice("");
    try {
      const response = await apiFetch("/api/restaurants/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: restaurantName.trim(), address_token: restaurantAddressToken }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.name?.[0] || "Could not create your restaurant.");
      setRestaurants((current) => [...current, data]);
      setMenuItems((current) => ({ ...current, [data.id]: [] }));
      setRestaurantName("");
      setRestaurantAddressQuery("");
      setRestaurantAddressToken("");
      setRestaurantAddresses([]);
      setAddressTargetId(null);
      setNotice(`${data.name} created. Add your menu items below.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create your restaurant.");
    } finally {
      busy.current = false;
      setCreatingRestaurant(false);
    }
  }

  async function findRestaurantAddress() {
    setError("");
    setRestaurantAddresses([]);
    try {
      const response = await apiFetch("/api/restaurant/address-lookup/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: restaurantAddressQuery }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not find that address.");
      setRestaurantAddresses(data.results ?? []);
      if (!data.results?.length) setError("No matching Montreal address found.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not find that address.");
    }
  }

  async function setExistingRestaurantAddress(restaurant: Restaurant, addressToken: string) {
    if (busy.current) return;
    busy.current = true; setPendingRestaurant(restaurant.id); setError(""); setNotice("");
    try {
      const response = await apiFetch(`/api/restaurants/${restaurant.id}/address/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ address_token: addressToken }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save restaurant address.");
      setRestaurants((current) => current.map((item) => item.id === data.id ? data : item));
      setRestaurantAddresses([]);
      setRestaurantAddressQuery("");
      setRestaurantAddressToken("");
      setAddressTargetId(null);
      setNotice(`${data.name}'s address saved and locked.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save restaurant address."); }
    finally { busy.current = false; setPendingRestaurant(null); }
  }

  function updatePromoDraft(restaurantId: number, changes: Partial<PromotionDraft>) {
    setPromoDrafts((current) => {
      const existing = current[restaurantId] ?? { code: "", discount_type: "fixed", discount: "", minimum_order: "0", expires_at: "", is_active: true };
      return { ...current, [restaurantId]: { ...existing, ...changes } };
    });
  }

  async function saveNewPromo(restaurantId: number, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const draft = promoDrafts[restaurantId];
    if (!draft || busy.current) return;
    busy.current = true;
    setError(""); setNotice("");
    try {
      const response = await apiFetch("/api/promotions/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ restaurant_id: restaurantId, ...draft, expires_at: new Date(draft.expires_at).toISOString() }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.code?.[0] || data.discount?.[0] || data.expires_at?.[0] || "Could not create promo code.");
      setPromotions((current) => [...current, data]);
      setPromoDrafts((current) => ({ ...current, [restaurantId]: { code: "", discount_type: "fixed", discount: "", minimum_order: "0", expires_at: "", is_active: true } }));
      setNotice(`${data.code} created.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create promo code."); }
    finally { busy.current = false; }
  }

  function updatePromotion(id: number, changes: Partial<Promotion>) {
    setPromotions((current) => current.map((promotion) => promotion.id === id ? { ...promotion, ...changes } : promotion));
  }

  async function savePromotion(promotion: Promotion) {
    if (busy.current) return;
    busy.current = true; setError(""); setNotice("");
    try {
      const response = await apiFetch(`/api/promotions/${promotion.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: promotion.code, discount_type: promotion.discount_type, discount: promotion.discount, minimum_order: promotion.minimum_order, expires_at: new Date(promotion.expires_at).toISOString(), is_active: promotion.is_active }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.code?.[0] || data.discount?.[0] || data.expires_at?.[0] || "Could not update promo code.");
      setPromotions((current) => current.map((item) => item.id === data.id ? data : item));
      setNotice(`${data.code} updated.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update promo code."); }
    finally { busy.current = false; }
  }

  async function deletePromotion(promotion: Promotion) {
    if (busy.current) return;
    busy.current = true; setError(""); setNotice("");
    try {
      const response = await apiFetch(`/api/promotions/${promotion.id}/`, { method: "DELETE" });
      if (!response.ok) { const data = await response.json(); throw new Error(data.detail || "Could not delete promo code."); }
      setPromotions((current) => current.filter((item) => item.id !== promotion.id));
      setNotice(`${promotion.code} deleted.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not delete promo code."); }
    finally { busy.current = false; }
  }

  function updateMenuDraft(restaurantId: number, changes: Partial<{ name: string; price: string }>) {
    setNewMenuDrafts((current) => {
      const existing = current[restaurantId] ?? { name: "", price: "" };
      return {
        ...current,
        [restaurantId]: {
          name: changes.name ?? existing.name,
          price: changes.price ?? existing.price,
        },
      };
    });
  }

  function updateMenuItemDraft(restaurantId: number, itemId: number, changes: Partial<MenuItem>) {
    setMenuItems((current) => ({
      ...current,
      [restaurantId]: (current[restaurantId] ?? []).map((item) =>
        item.id === itemId ? { ...item, ...changes } : item
      ),
    }));
  }

  async function addMenuItem(restaurant: Restaurant, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    const draft = newMenuDrafts[restaurant.id] ?? { name: "", price: "" };
    busy.current = true;
    setPendingMenu(`new:${restaurant.id}`);
    setError("");
    setNotice("");
    try {
      const response = await apiFetch(`/api/restaurants/${restaurant.id}/menu/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: draft.name.trim(), price: draft.price }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.name?.[0] || data.price?.[0] || "Could not add this menu item.");
      setMenuItems((current) => ({
        ...current,
        [restaurant.id]: [...(current[restaurant.id] ?? []), data].sort((a, b) => a.name.localeCompare(b.name)),
      }));
      updateMenuDraft(restaurant.id, { name: "", price: "" });
      setNotice(`${data.name} added to ${restaurant.name}'s menu.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this menu item.");
    } finally {
      busy.current = false;
      setPendingMenu(null);
    }
  }

  async function saveMenuItem(restaurant: Restaurant, item: MenuItem) {
    if (busy.current) return;
    busy.current = true;
    setPendingMenu(`item:${item.id}`);
    setError("");
    setNotice("");
    try {
      const response = await apiFetch(`/api/restaurants/${restaurant.id}/menu/${item.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: item.name.trim(), price: item.price, status: item.status }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.name?.[0] || data.price?.[0] || data.status?.[0] || "Could not update this menu item.");
      setMenuItems((current) => ({
        ...current,
        [restaurant.id]: (current[restaurant.id] ?? []).map((entry) => entry.id === item.id ? data : entry),
      }));
      setNotice(`${data.name} updated.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update this menu item.");
    } finally {
      busy.current = false;
      setPendingMenu(null);
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
                <span>{restaurant.name} · {restaurant.address || "Address unavailable"} · {restaurant.status}</span>
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
            <button type="button" aria-pressed={selectedStage === "map"} className={`btn btn-full ${selectedStage === "map" ? "btn-primary" : "btn-secondary"}`} onClick={() => setSelectedStage("map")}>Map</button>
            <div className="my-2 border-t border-[var(--color-border)]" />
            <button type="button" aria-pressed={selectedStage === "manage"} className={`btn btn-full ${selectedStage === "manage" ? "btn-primary" : "btn-secondary"}`} onClick={() => setSelectedStage("manage")}>Manage restaurant</button>
          </nav>
          <div className="min-w-0">
            <div role="status" aria-live="polite" className="mb-3">{notice && <p className={`message ${noticePaused ? "message-warning" : "message-success"}`}>{notice}</p>}</div>
            {error && <p role="alert" className="message message-error mb-5">{error}</p>}
            {selectedStage === "manage" && (
        <section id="menu-management" className="mb-8 rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)]/80 p-5" aria-labelledby="menu-management-heading">
          <h2 id="menu-management-heading" className="text-xl font-bold text-[var(--color-forest)]">Manage restaurant</h2>
          <p className="form-help mt-1 mb-5">Add items, update prices, and mark items available or sold out.</p>
          {loaded && !restaurants.length && (
            <form className="mb-5 flex flex-wrap items-end gap-3" onSubmit={(event) => void createRestaurant(event)}>
              <p className="form-label w-full">Restaurant name and address · locked after linking</p>
              <label className="form-label min-w-64 flex-1">Restaurant name
                <input className="form-input mt-1" required maxLength={150} value={restaurantName} onChange={(event) => setRestaurantName(event.target.value)} />
              </label>
              <label className="form-label min-w-64 flex-1">Restaurant address
                <input className="form-input mt-1" required maxLength={250} placeholder="Search a Montreal street address" value={restaurantAddressQuery} onChange={(event) => { setRestaurantAddressQuery(event.target.value); setRestaurantAddressToken(""); setRestaurantAddresses([]); }} />
              </label>
              <button className="btn btn-secondary" type="button" disabled={restaurantAddressQuery.trim().length < 5} onClick={() => void findRestaurantAddress()}>Find address</button>
              <button className="btn btn-primary" type="submit" disabled={creatingRestaurant || !restaurantAddressToken}>{creatingRestaurant ? "Creating…" : "Create restaurant"}</button>
              {restaurantAddresses.length > 0 && <ul className="w-full space-y-2">{restaurantAddresses.map((result) => <li key={result.address}><button className="btn btn-secondary" type="button" onClick={() => { setRestaurantAddressQuery(result.address); setRestaurantAddressToken(result.token); setRestaurantAddresses([]); }}>{result.address}</button></li>)}</ul>}
            </form>
          )}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            {restaurants.map((restaurant) => (
              <article key={restaurant.id} className="rounded-2xl border border-[var(--color-border)] p-4">
                <h3 className="font-bold text-[var(--color-forest)]">{restaurant.name}</h3>
                {!restaurant.address && <div className="mt-3 rounded-xl border border-dashed border-[var(--color-border)] p-3">
                  <label className="form-label">Set restaurant address once
                    <input className="form-input mt-1" maxLength={250} placeholder="Search a Montreal street address" value={restaurantAddressQuery} onChange={(event) => { setRestaurantAddressQuery(event.target.value); setRestaurantAddressToken(""); setAddressTargetId(null); setRestaurantAddresses([]); }} />
                  </label>
                  <button className="btn btn-secondary mt-2" type="button" disabled={restaurantAddressQuery.trim().length < 5} onClick={() => void findRestaurantAddress()}>Find address</button>
                  {restaurantAddresses.length > 0 && <ul className="mt-2 space-y-2">{restaurantAddresses.map((result) => <li key={result.address}><button className={`btn btn-full text-left ${addressTargetId === restaurant.id && restaurantAddressToken === result.token ? "btn-primary" : "btn-secondary"}`} type="button" onClick={() => { setRestaurantAddressToken(result.token); setAddressTargetId(restaurant.id); }}>{result.address}</button></li>)}</ul>}
                  {addressTargetId === restaurant.id && restaurantAddressToken && <button className="btn btn-primary mt-2" type="button" disabled={pendingRestaurant === restaurant.id} onClick={() => void setExistingRestaurantAddress(restaurant, restaurantAddressToken)}>{pendingRestaurant === restaurant.id ? "Setting address…" : "Set address"}</button>}
                </div>}
                <form className="mt-4 grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_130px_auto] gap-2 items-end" onSubmit={(event) => void addMenuItem(restaurant, event)}>
                  <label className="form-label">New item
                    <input className="form-input mt-1" required maxLength={150} value={newMenuDrafts[restaurant.id]?.name ?? ""} onChange={(event) => updateMenuDraft(restaurant.id, { name: event.target.value })} />
                  </label>
                  <label className="form-label">Price (CAD)
                    <input className="form-input mt-1" required type="number" min="0.01" step="0.01" value={newMenuDrafts[restaurant.id]?.price ?? ""} onChange={(event) => updateMenuDraft(restaurant.id, { price: event.target.value })} />
                  </label>
                  <button className="btn btn-primary" type="submit" disabled={loading || pendingMenu !== null || pending !== null || pendingRestaurant !== null}>{pendingMenu === `new:${restaurant.id}` ? "Adding…" : "Add item"}</button>
                </form>
                <ul className="mt-4 space-y-3">
                  {(menuItems[restaurant.id] ?? []).map((item) => (
                    <li key={item.id} className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_120px_140px_auto] gap-2 items-end rounded-xl bg-[var(--color-sage-light)]/40 p-3">
                      <label className="form-label">Item name
                        <input className="form-input mt-1" required maxLength={150} value={item.name} onChange={(event) => updateMenuItemDraft(restaurant.id, item.id, { name: event.target.value })} />
                      </label>
                      <label className="form-label">Price (CAD)
                        <input className="form-input mt-1" required type="number" min="0.01" step="0.01" value={item.price} onChange={(event) => updateMenuItemDraft(restaurant.id, item.id, { price: event.target.value })} />
                      </label>
                      <label className="form-label">Availability
                        <select className="form-input mt-1" value={item.status} onChange={(event) => updateMenuItemDraft(restaurant.id, item.id, { status: event.target.value as MenuItem["status"] })}>
                          <option value="available">Available</option>
                          <option value="sold_out">Sold out</option>
                        </select>
                      </label>
                      <button className="btn btn-secondary" type="button" disabled={pendingMenu !== null || pending !== null || pendingRestaurant !== null} onClick={() => void saveMenuItem(restaurant, item)}>{pendingMenu === `item:${item.id}` ? "Saving…" : "Save"}</button>
                    </li>
                  ))}
                  {loaded && !(menuItems[restaurant.id] ?? []).length && <li className="form-help">No menu items yet.</li>}
                </ul>
                <section className="mt-6 border-t border-[var(--color-border)] pt-5" aria-label={`${restaurant.name} promo codes`}>
                  <h4 className="font-bold text-[var(--color-forest)]">Promo codes</h4>
                  <form className="mt-3 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2 items-end" onSubmit={(event) => void saveNewPromo(restaurant.id, event)}>
                    <label className="form-label">Code
                      <input className="form-input mt-1" required maxLength={40} value={promoDrafts[restaurant.id]?.code ?? ""} onChange={(event) => updatePromoDraft(restaurant.id, { code: event.target.value.toUpperCase() })} />
                    </label>
                    <label className="form-label">Discount type
                      <select className="form-input mt-1" value={promoDrafts[restaurant.id]?.discount_type ?? "fixed"} onChange={(event) => updatePromoDraft(restaurant.id, { discount_type: event.target.value as PromotionDraft["discount_type"] })}><option value="fixed">Amount (CAD)</option><option value="percentage">Percent</option></select>
                    </label>
                    <label className="form-label">Discount
                      <input className="form-input mt-1" required type="number" min="0.01" step="0.01" max={promoDrafts[restaurant.id]?.discount_type === "percentage" ? "100" : undefined} value={promoDrafts[restaurant.id]?.discount ?? ""} onChange={(event) => updatePromoDraft(restaurant.id, { discount: event.target.value })} />
                    </label>
                    <label className="form-label">Minimum order (CAD)
                      <input className="form-input mt-1" required type="number" min="0" step="0.01" value={promoDrafts[restaurant.id]?.minimum_order ?? "0"} onChange={(event) => updatePromoDraft(restaurant.id, { minimum_order: event.target.value })} />
                    </label>
                    <label className="form-label">Expiry date and time
                      <input className="form-input mt-1" required type="datetime-local" value={promoDrafts[restaurant.id]?.expires_at ?? ""} onChange={(event) => updatePromoDraft(restaurant.id, { expires_at: event.target.value })} />
                    </label>
                    <button className="btn btn-primary" type="submit">Create promo</button>
                  </form>
                  <ul className="mt-4 space-y-3">
                    {promotions.filter((promotion) => promotion.restaurant_id === restaurant.id).map((promotion) => (
                      <li key={promotion.id} className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-7 gap-2 items-end rounded-xl bg-[var(--color-sage-light)]/40 p-3">
                        <label className="form-label">Code<input className="form-input mt-1" required maxLength={40} value={promotion.code} onChange={(event) => updatePromotion(promotion.id, { code: event.target.value.toUpperCase() })} /></label>
                        <label className="form-label">Type<select className="form-input mt-1" value={promotion.discount_type} onChange={(event) => updatePromotion(promotion.id, { discount_type: event.target.value as Promotion["discount_type"] })}><option value="fixed">Amount</option><option value="percentage">Percent</option></select></label>
                        <label className="form-label">Discount<input className="form-input mt-1" required type="number" min="0.01" step="0.01" max={promotion.discount_type === "percentage" ? "100" : undefined} value={promotion.discount} onChange={(event) => updatePromotion(promotion.id, { discount: event.target.value })} /></label>
                        <label className="form-label">Minimum (CAD)<input className="form-input mt-1" required type="number" min="0" step="0.01" value={promotion.minimum_order} onChange={(event) => updatePromotion(promotion.id, { minimum_order: event.target.value })} /></label>
                        <label className="form-label">Expires<input className="form-input mt-1" required type="datetime-local" value={localDateTime(promotion.expires_at)} onChange={(event) => updatePromotion(promotion.id, { expires_at: event.target.value })} /></label>
                        <label className="form-label flex items-center gap-2"><input type="checkbox" checked={promotion.is_active} onChange={(event) => updatePromotion(promotion.id, { is_active: event.target.checked })} />Active</label>
                        <div className="flex gap-2"><button className="btn btn-secondary" type="button" onClick={() => void savePromotion(promotion)}>Save</button><button className="btn btn-secondary" type="button" onClick={() => void deletePromotion(promotion)}>Delete</button></div>
                      </li>
                    ))}
                    {!promotions.some((promotion) => promotion.restaurant_id === restaurant.id) && <li className="form-help">No promo codes.</li>}
                  </ul>
                </section>
              </article>
            ))}
          </div>
        </section>
            )}
            {selectedStage !== "manage" && (
              <>
        <div className="flex items-center justify-between gap-3 mb-5">
          <button type="button" className="btn btn-secondary shrink-0" disabled={loading || refreshing || pending !== null || pendingRestaurant !== null} onClick={requestRefresh}>{refreshing ? "Refreshing…" : "Refresh orders"}</button>
        </div>
        {loading && <p role="status" className="body-text mb-5">Loading your orders…</p>}
          {selectedStage === "map" && <MontrealMap />}
          {loaded && selectedStage !== "map" && <div className={selectedStage === "all" ? "grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-5 items-start" : "grid grid-cols-1 gap-5"}>
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
                    {!items.length && <div className="rounded-2xl border border-dashed border-[var(--color-border)] p-6 text-center"><p className="text-sm font-semibold">All clear here</p></div>}
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
                        {order.status === "placed" && (decliningOrderId === order.id ? (
                          <form className="mt-3 space-y-2" onSubmit={(event) => { event.preventDefault(); void advance(order, "rejected", "Declined", rejectionReasons[order.id] ?? ""); }}>
                            <label className="form-label" htmlFor={`rejection-reason-${order.id}`}>Reason for declining
                              <textarea id={`rejection-reason-${order.id}`} className="form-input mt-1 min-h-20" required minLength={3} maxLength={500} value={rejectionReasons[order.id] ?? ""} onChange={(event) => setRejectionReasons((current) => ({ ...current, [order.id]: event.target.value }))} />
                            </label>
                            <div className="flex gap-2">
                              <button type="submit" className="btn btn-secondary flex-1" disabled={pending !== null || pendingRestaurant !== null || refreshing || isWaiting(order) || !(rejectionReasons[order.id] ?? "").trim()}>{pending === order.id ? "Declining…" : "Confirm decline"}</button>
                              <button type="button" className="btn btn-secondary" disabled={pending === order.id} onClick={() => setDecliningOrderId(null)}>Cancel</button>
                            </div>
                          </form>
                        ) : <button type="button" className="btn btn-secondary btn-full mt-2" disabled={pending !== null || pendingRestaurant !== null || refreshing || isWaiting(order)} onClick={() => setDecliningOrderId(order.id)} aria-label={`Decline order ${order.id}`}>Decline order</button>)}
                      </article>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>}
              </>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
