
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

type Order = {
  id: number;
  restaurant_name: string;
  status: string;
  created_at: string;
  total: string;
  lines: {
    id: number;
    name: string;
    quantity: number;
    unit_price: string;
  }[];
};

type SummaryDetails = {
  subtotal: string;
  delivery_fee: string;
  service_fee: string;
  small_order_surcharge: string;
  total: string;
};

type RefundRequest = {
  id: number;
  order_id: number;
  reason: string;
  reason_display: string;
  details: string;
  requested_amount: string | null;
  status: "pending" | "approved" | "rejected";
  approved_amount: string | null;
  decision_notes: string;
  created_at: string;
  decided_at: string | null;
};

const pastStatuses = new Set([
  "delivered",
  "rejected",
  "cancelled",
  "partially_refunded",
  "refunded",
]);

const refundEligibleStatuses = new Set([
  "delivered",
  "rejected",
  "cancelled",
  "partially_refunded",
]);

const statusLabels: Record<string, string> = {
  placed: "Placed · Waiting for approval",
  accepted: "Accepted",
  preparing: "Preparing",
  ready: "Ready for pickup",
  picked_up: "Out for delivery",
  delivered: "Delivered",
  rejected: "Declined",
  cancelled: "Cancelled",
  partially_refunded: "Partially refunded",
  refunded: "Refunded",
};

const refundStatusLabels: Record<string, string> = {
  pending: "Pending review",
  approved: "Approved",
  rejected: "Rejected",
};

const refundReasons = [
  { value: "not_received", label: "Order never arrived" },
  { value: "missing_items", label: "Missing items" },
  { value: "incorrect_items", label: "Incorrect items" },
  { value: "damaged_items", label: "Damaged or poor quality" },
  { value: "restaurant_cancelled", label: "Cancelled by restaurant" },
  { value: "rejected_order", label: "Rejected by restaurant" },
  { value: "duplicate_payment", label: "Duplicate payment" },
  { value: "other", label: "Other" },
];

const money = (value: string | number) =>
  new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
  }).format(Number(value));

function OrderSummary({ orderId }: { orderId: number }) {
  const [summary, setSummary] = useState<SummaryDetails | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const toggleSummary = async () => {
    if (open) {
      setOpen(false);
      return;
    }

    setOpen(true);

    if (summary) return;

    setLoading(true);
    setError("");

    try {
      const response = await apiFetch(
        `/api/pricing/orders/${orderId}/summary/`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not load order summary.");
      }

      setSummary(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not load order summary."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-4 border-t border-[var(--color-border)] pt-4">
      <button
        type="button"
        className="btn btn-secondary"
        onClick={toggleSummary}
      >
        {open ? "Hide summary" : "View summary"}
      </button>

      {open && loading && (
        <p className="mt-3">Loading summary...</p>
      )}

      {open && error && (
        <p className="message message-error mt-3">{error}</p>
      )}

      {open && summary && (
        <div className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <span>Subtotal</span>
            <span>{money(summary.subtotal)}</span>
          </div>

          <div className="flex justify-between">
            <span>Delivery fee</span>
            <span>{money(summary.delivery_fee)}</span>
          </div>

          <div className="flex justify-between">
            <span>Service fee</span>
            <span>{money(summary.service_fee)}</span>
          </div>

          <div className="flex justify-between">
            <span>Small-order surcharge</span>
            <span>{money(summary.small_order_surcharge)}</span>
          </div>

          <div className="flex justify-between font-bold border-t pt-2">
            <span>Final total</span>
            <span>{money(summary.total)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function RefundRequestSection({
  orderId,
  requests,
  onSubmitted,
}: {
  orderId: number;
  requests: RefundRequest[];
  onSubmitted: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [details, setDetails] = useState("");
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const orderRequests = requests.filter(
    (refund) => refund.order_id === orderId
  );

  const pendingRequest = orderRequests.some(
    (refund) => refund.status === "pending"
  );

  const alreadyFullyRefunded = orderRequests.some(
    (refund) => refund.status === "approved"
  );

  const submitRequest = async () => {
    setError("");
    setMessage("");

    if (!reason) {
      setError("Please select a reason for your refund request.");
      return;
    }

    if (
      amount.trim() &&
      (!Number.isFinite(Number(amount)) || Number(amount) <= 0)
    ) {
      setError("Please enter a valid refund amount.");
      return;
    }

    try {
      setSubmitting(true);

      const response = await apiFetch("/api/pricing/refunds/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          order_id: orderId,
          reason,
          details,
          requested_amount: amount.trim() ? amount : null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to submit your refund request."
        );
      }

      setMessage("Your refund request was submitted successfully.");
      setReason("");
      setDetails("");
      setAmount("");
      setOpen(false);

      await onSubmitted();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to submit your refund request."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mt-5 border-t border-[var(--color-border)] pt-4">
      <h4 className="font-semibold text-[var(--color-forest)]">
        Refund requests
      </h4>

      {orderRequests.map((refund) => (
        <div
          key={refund.id}
          className="mt-3 rounded-xl border border-[var(--color-border)] p-4"
        >
          <div className="flex flex-wrap justify-between gap-2">
            <strong>
              {refund.reason_display || refund.reason}
            </strong>

            <span className="rounded-full bg-[var(--color-sage-light)] px-3 py-1 text-sm font-semibold">
              {refundStatusLabels[refund.status] || refund.status}
            </span>
          </div>

          {refund.details && (
            <p className="body-text mt-2">{refund.details}</p>
          )}

          {refund.requested_amount && (
            <p className="body-text mt-2">
              Requested amount: {money(refund.requested_amount)}
            </p>
          )}

          {refund.status === "approved" && (
            <p className="mt-2 font-semibold">
              Approved amount:{" "}
              {money(refund.approved_amount || "0")}
            </p>
          )}

          {refund.status !== "pending" && refund.decision_notes && (
            <p className="body-text mt-2">
              Operator&apos;s decision: {refund.decision_notes}
            </p>
          )}

          <p className="form-help mt-2">
            Submitted:{" "}
            {new Date(refund.created_at).toLocaleString("en-CA")}
          </p>

          {refund.decided_at && (
            <p className="form-help mt-1">
              Decision date:{" "}
              {new Date(refund.decided_at).toLocaleString("en-CA")}
            </p>
          )}
        </div>
      ))}

      {message && (
        <p className="message message-success mt-3">{message}</p>
      )}

      {pendingRequest ? (
        <p className="form-help mt-3">
          You already have a refund request awaiting review for this order.
        </p>
      ) : alreadyFullyRefunded ? (
        <p className="form-help mt-3">
          This order already has an approved refund request.
        </p>
      ) : (
        <>
          <button
            type="button"
            className="btn btn-secondary mt-4"
            onClick={() => {
              setOpen(!open);
              setError("");
            }}
          >
            {open ? "Cancel request" : "Request Refund"}
          </button>

          {open && (
            <div className="mt-4 rounded-xl border border-[var(--color-border)] p-4">
              <h5 className="font-semibold">
                Submit a refund request
              </h5>

              <label className="form-help mt-4 block">
                Reason for refund
              </label>

              <select
                className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              >
                <option value="">Select a reason</option>

                {refundReasons.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>

              <label className="form-help mt-4 block">
                Additional details (optional)
              </label>

              <textarea
                className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
                rows={4}
                value={details}
                onChange={(event) => setDetails(event.target.value)}
                placeholder="Explain what happened..."
              />

              <label className="form-help mt-4 block">
                Requested refund amount (optional)
              </label>

              <input
                type="number"
                min="0.01"
                step="0.01"
                className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder="Leave blank to request a full refund"
              />



              {error && (
                <p role="alert" className="message message-error mt-3">
                  {error}
                </p>
              )}

              <button
                type="button"
                className="btn btn-primary btn-full mt-4"
                disabled={submitting}
                onClick={submitRequest}
              >
                {submitting
                  ? "Submitting..."
                  : "Submit Refund Request"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function CustomerOrders({
  category,
}: {
  category: "active" | "past";
}) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [refunds, setRefunds] = useState<RefundRequest[]>([]);
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

      if (!response.ok) {
        throw new Error(data.detail || "Could not load your orders.");
      }

      if (mounted.current) {
        setOrders(Array.isArray(data) ? data : data.results ?? []);
        setError("");
        setUpdatedAt(new Date());
      }
    } catch (err) {
      if (mounted.current) {
        setError(
          err instanceof Error
            ? err.message
            : "Could not load your orders."
        );
      }
    } finally {
      busy.current = false;

      if (mounted.current) {
        setLoading(false);
      }
    }
  }, []);

  const loadRefunds = useCallback(async () => {
    try {
      const response = await apiFetch("/api/pricing/refunds/");
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not load refund requests.");
      }

      if (mounted.current) {
        setRefunds(Array.isArray(data) ? data : data.results ?? []);
      }
    } catch (err) {
      console.error("Could not load refund requests:", err);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;

    const initial = setTimeout(() => {
      void refresh();
      void loadRefunds();
    }, 0);

    return () => {
      mounted.current = false;
      clearTimeout(initial);
    };
  }, [refresh, loadRefunds]);

  const visibleOrders = orders.filter(
    (order) =>
      pastStatuses.has(order.status) === (category === "past")
  );

  return (
    <section>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={loading}
          onClick={() => {
            if (!busy.current) {
              setLoading(true);
              void refresh();
              void loadRefunds();
            }
          }}
        >
          {loading ? "Refreshing…" : "Refresh orders"}
        </button>
      </div>

      {error && (
        <p role="alert" className="message message-error mb-5">
          {error}
          {updatedAt ? " Showing the last successful update." : ""}
        </p>
      )}

      {loading && !updatedAt && (
        <p role="status" className="body-text">
          Loading your orders…
        </p>
      )}

      {updatedAt && !visibleOrders.length && (
        <div className="form-card">
          <h3 className="font-semibold">
            {category === "active"
              ? "No active orders"
              : "No past orders yet"}
          </h3>


        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {visibleOrders.map((order) => (
          <article
            key={order.id}
            className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-sm"
          >
            <div className="flex flex-wrap justify-between items-start gap-3">
              <div>
                <h3 className="text-lg font-bold text-[var(--color-forest)]">
                  {order.restaurant_name}
                </h3>

                <p className="form-help mt-1">
                  Order #{order.id}
                </p>
              </div>

              <span className="rounded-full bg-[var(--color-sage-light)] px-3 py-2 text-sm font-semibold">
                {statusLabels[order.status] ?? order.status}
              </span>
            </div>

            <time
              className="block form-help mt-3"
              dateTime={order.created_at}
            >
              {new Date(order.created_at).toLocaleString("en-CA")}
            </time>

            <ul className="my-5 py-4 border-y border-[var(--color-border)] space-y-3">
              {order.lines.map((line) => (
                <li
                  key={line.id}
                  className="flex justify-between gap-4 text-sm"
                >
                  <span>
                    {line.quantity} × {line.name}
                  </span>

                  <span className="shrink-0">
                    {money(Number(line.unit_price) * line.quantity)}
                  </span>
                </li>
              ))}
            </ul>

            <div className="flex justify-between font-bold">
              <span>Items subtotal</span>
              <span>{money(order.total)}</span>
            </div>

            {order.status === "delivered" && (
              <OrderSummary orderId={order.id} />
            )}

            {category === "past" &&
              refundEligibleStatuses.has(order.status) && (
                <RefundRequestSection
                  orderId={order.id}
                  requests={refunds}
                  onSubmitted={loadRefunds}
                />
              )}
          </article>
        ))}
      </div>
    </section>
  );
}
