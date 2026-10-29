"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

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

const roles = [["customer", "Customers"], ["restaurant", "Restaurant accounts"], ["courier", "Couriers"], ["operator", "Operators"]];
const restaurantStatuses = [["open", "Open"], ["paused", "Paused"], ["closed", "Closed"]];
const orderStatuses = [["placed", "Placed"], ["accepted", "Accepted"], ["preparing", "Preparing"], ["ready", "Ready for pickup"], ["picked_up", "Out for delivery"], ["delivered", "Delivered"], ["rejected", "Declined"], ["cancelled", "Cancelled"]];
const number = (value: number) => value.toLocaleString("en-CA");

function Breakdown({ title, description, labels, counts, total }: {
  title: string; description: string; labels: string[][]; counts: Record<string, number>; total: number;
}) {
  return (
    <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
      <h2 className="section-title">{title}</h2>
      <p className="form-help mt-2 mb-6">{description}</p>
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
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

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
        <header className="flex flex-wrap justify-between items-start gap-5 mb-9">
          <div><p className="eyebrow">Five Leaf Clover · Platform operator</p><h1 className="page-title mt-3">Platform overview</h1></div>
          
        </header>
        {loading && <p role="status" className="body-text">Loading platform statistics…</p>}
        {error && <div role="alert" className="message message-error mb-6"><p>{error}</p><p className="mt-2">{data ? "Showing the last successful update. " : ""}<Link href="/login">Return to login</Link></p></div>}
        {data && <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5 mb-8">
            {[
              { label: "Total users", value: data.total_users, help: `${number(data.active_users)} enabled accounts` },
              { label: "Restaurants", value: data.total_restaurants, help: `${number(data.restaurants_by_status.open ?? 0)} currently open` },
              { label: "Active orders", value: data.active_orders, help: "Placed through out for delivery" },
              { label: "Total orders", value: data.total_orders, help: "All statuses · All time" },
            ].map((stat) => <section key={stat.label} className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm">
              <h2 className="text-sm font-semibold text-[var(--color-muted)]">{stat.label}</h2><p className="text-4xl font-bold text-[var(--color-forest)] mt-4 tabular-nums">{number(stat.value)}</p><p className="form-help mt-3">{stat.help}</p>
            </section>)}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
            <Breakdown title="People" description="Registered accounts by role" labels={roles} counts={data.users_by_role} total={data.total_users} />
            <Breakdown title="Restaurants" description="Current availability across the platform" labels={restaurantStatuses} counts={data.restaurants_by_status} total={data.total_restaurants} />
            <Breakdown title="Order activity" description="All orders grouped by their current status" labels={orderStatuses} counts={data.orders_by_status} total={data.total_orders} />
          </div>
        </>}
      </div>
    </main>
  );
}
