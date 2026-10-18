"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type OrderLine = {
  id?: number;
  name?: string;
  menu_item_name?: string;
  quantity: number;
  unit_price: number | string;
};

type RestaurantOrder = {
  id: number;
  status: string;
  created_at: string;
  customer_name?: string;
  customer_username?: string;
  lines?: OrderLine[];
  items?: OrderLine[];
};

type OrderAction =
  | "accept"
  | "reject"
  | "start-preparation"
  | "ready";

const API_BASE = "http://localhost:8000";

/*
 * These restaurant-order endpoints will be confirmed when the ORD
 * lifecycle/command branches are pushed.
 *
 * Keeping them here means we only need to change these lines later.
 */
const RESTAURANT_ORDERS_ENDPOINT =
  `${API_BASE}/api/restaurant/orders/`;

const orderActionEndpoint = (
  orderId: number,
  action: OrderAction
) => `${API_BASE}/api/orders/${orderId}/${action}/`;

function getOrderLines(order: RestaurantOrder) {
  return order.lines ?? order.items ?? [];
}

function getCustomerName(order: RestaurantOrder) {
  return (
    order.customer_name ??
    order.customer_username ??
    "Customer"
  );
}

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(date: string) {
  if (!date) {
    return "Unknown time";
  }

  return new Date(date).toLocaleString();
}

function calculateTotal(order: RestaurantOrder) {
  return getOrderLines(order).reduce(
    (total, line) =>
      total +
      Number(line.unit_price) * Number(line.quantity),
    0
  );
}

export default function RestaurantDashboard() {
  const [orders, setOrders] = useState<RestaurantOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [updatingOrderId, setUpdatingOrderId] =
    useState<number | null>(null);

  const loadOrders = useCallback(async (showLoader = false) => {
    if (showLoader) {
        setRefreshing(true);
        setError("");
    }

    try {
      const response = await fetch(
        RESTAURANT_ORDERS_ENDPOINT,
        {
          method: "GET",
          credentials: "include",
        }
      );

      if (!response.ok) {
        throw new Error(
          "Could not load restaurant orders."
        );
      }

      const data = await response.json();

      const receivedOrders = Array.isArray(data)
        ? data
        : data.results ?? data.orders ?? [];

      setOrders(receivedOrders);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load restaurant orders."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => {
        void loadOrders();
    }, 0);

    return () => {
        window.clearTimeout(initialLoad);
    };
    }, [loadOrders]);

  const performOrderAction = async (
    order: RestaurantOrder,
    action: OrderAction
  ) => {
    setError("");
    setMessage("");

    let body: Record<string, string> | undefined;

    if (action === "reject") {
      const reason = window.prompt(
        "Enter a reason for rejecting this order:"
      );

      if (reason === null) {
        return;
      }

      if (!reason.trim()) {
        setError("A rejection reason is required.");
        return;
      }

      body = {
        reason: reason.trim(),
      };
    }

    setUpdatingOrderId(order.id);

    try {
      const response = await fetch(
        orderActionEndpoint(order.id, action),
        {
          method: "POST",
          credentials: "include",
          headers: body
            ? {
                "Content-Type": "application/json",
              }
            : undefined,
          body: body ? JSON.stringify(body) : undefined,
        }
      );

      const responseText = await response.text();

      let data: {
        message?: string;
        status?: string;
      } = {};

      if (responseText) {
        try {
          data = JSON.parse(responseText);
        } catch {
          data = {};
        }
      }

      if (!response.ok) {
        throw new Error(
          data.message ??
            `Could not ${action.replaceAll("-", " ")} order #${order.id}.`
        );
      }

      setMessage(
        data.message ??
          `Order #${order.id} updated successfully.`
      );

      await loadOrders();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not update the order."
      );
    } finally {
      setUpdatingOrderId(null);
    }
  };

  const sortedOrders = useMemo(() => {
    return [...orders].sort(
      (first, second) =>
        new Date(first.created_at).getTime() -
        new Date(second.created_at).getTime()
    );
  }, [orders]);

  const incomingOrders = sortedOrders.filter(
    (order) => order.status === "placed"
  );

  const acceptedOrders = sortedOrders.filter(
    (order) => order.status === "accepted"
  );

  const preparingOrders = sortedOrders.filter(
    (order) => order.status === "preparing"
  );

  const readyOrders = sortedOrders.filter(
    (order) => order.status === "ready"
  );

  const firstAcceptedOrderId =
    acceptedOrders.length > 0
      ? acceptedOrders[0].id
      : null;

  const renderOrderDetails = (order: RestaurantOrder) => {
    const lines = getOrderLines(order);

    return (
      <>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold">
              Order #{order.id}
            </h3>

            <p className="body-text mt-1">
              {getCustomerName(order)}
            </p>
          </div>

          <span className="rounded-full border px-3 py-1 text-xs font-semibold">
            {formatStatus(order.status)}
          </span>
        </div>

        <p className="body-text mt-3">
          {formatDate(order.created_at)}
        </p>

        <div className="mt-4 border-t pt-4">
          <p className="font-semibold">
            Items
          </p>

          {lines.length === 0 ? (
            <p className="body-text mt-2">
              No item details available.
            </p>
          ) : (
            <div className="mt-2 flex flex-col gap-2">
              {lines.map((line, index) => (
                <div
                  key={line.id ?? index}
                  className="flex justify-between gap-4"
                >
                  <span>
                    {line.quantity} ×{" "}
                    {line.menu_item_name ??
                      line.name ??
                      "Menu item"}
                  </span>

                  <span>
                    $
                    {(
                      Number(line.unit_price) *
                      line.quantity
                    ).toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {lines.length > 0 && (
          <p className="mt-4 font-semibold">
            Total: ${calculateTotal(order).toFixed(2)}
          </p>
        )}
      </>
    );
  };

  return (
    <main className="page-container botanical-background">
      <section className="page-content">

        {/* Header */}
        <header className="mb-8">
          <p className="eyebrow">
            Five Leaf Clover
          </p>

          <div className="mt-3 flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <h1 className="page-title">
                Restaurant Dashboard
              </h1>

              <p className="body-text mt-3">
                Manage incoming orders and the kitchen
                preparation queue.
              </p>
            </div>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => loadOrders(true)}
              disabled={refreshing}
            >
              {refreshing
                ? "Refreshing..."
                : "Refresh Orders"}
            </button>
          </div>
        </header>

        {/* Summary */}
        <section className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="form-card">
            <p className="eyebrow">Incoming</p>
            <p className="mt-2 text-3xl font-bold">
              {incomingOrders.length}
            </p>
          </div>

          <div className="form-card">
            <p className="eyebrow">Queued</p>
            <p className="mt-2 text-3xl font-bold">
              {acceptedOrders.length}
            </p>
          </div>

          <div className="form-card">
            <p className="eyebrow">Preparing</p>
            <p className="mt-2 text-3xl font-bold">
              {preparingOrders.length}
            </p>
          </div>

          <div className="form-card">
            <p className="eyebrow">Ready</p>
            <p className="mt-2 text-3xl font-bold">
              {readyOrders.length}
            </p>
          </div>
        </section>

        {message && (
          <div className="message message-success mb-6">
            {message}
          </div>
        )}

        {error && (
          <div className="message message-error mb-6">
            {error}
          </div>
        )}

        {loading ? (
          <section className="form-card">
            <p className="body-text">
              Loading restaurant orders...
            </p>
          </section>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">

            {/* Incoming Orders */}
            <section className="form-card">
              <h2 className="section-title">
                Incoming Orders
              </h2>

              <p className="body-text mt-2">
                Accept or reject newly placed orders.
              </p>

              {incomingOrders.length === 0 && (
                <p className="body-text mt-5">
                  No new orders.
                </p>
              )}

              <div className="mt-5 flex flex-col gap-4">
                {incomingOrders.map((order) => (
                  <article
                    key={order.id}
                    className="rounded-xl border p-4"
                  >
                    {renderOrderDetails(order)}

                    <div className="mt-5 grid grid-cols-2 gap-3">
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={
                          updatingOrderId === order.id
                        }
                        onClick={() =>
                          performOrderAction(
                            order,
                            "accept"
                          )
                        }
                      >
                        Accept
                      </button>

                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={
                          updatingOrderId === order.id
                        }
                        onClick={() =>
                          performOrderAction(
                            order,
                            "reject"
                          )
                        }
                      >
                        Reject
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            {/* Preparation Queue */}
            <section className="form-card">
              <h2 className="section-title">
                Preparation Queue
              </h2>

              <p className="body-text mt-2">
                Accepted orders are shown in FIFO order.
              </p>

              {acceptedOrders.length === 0 &&
                preparingOrders.length === 0 && (
                  <p className="body-text mt-5">
                    The preparation queue is empty.
                  </p>
                )}

              <div className="mt-5 flex flex-col gap-4">
                {acceptedOrders.map((order, index) => {
                  const isNext =
                    order.id === firstAcceptedOrderId;

                  return (
                    <article
                      key={order.id}
                      className="rounded-xl border p-4"
                    >
                      <p className="eyebrow">
                        Queue #{index + 1}
                      </p>

                      <div className="mt-3">
                        {renderOrderDetails(order)}
                      </div>

                      <button
                        type="button"
                        className="btn btn-primary btn-full mt-5"
                        disabled={
                          !isNext ||
                          updatingOrderId === order.id
                        }
                        onClick={() =>
                          performOrderAction(
                            order,
                            "start-preparation"
                          )
                        }
                      >
                        {isNext
                          ? "Start Preparing"
                          : "Waiting in Queue"}
                      </button>
                    </article>
                  );
                })}

                {preparingOrders.map((order) => (
                  <article
                    key={order.id}
                    className="rounded-xl border p-4"
                  >
                    <p className="eyebrow">
                      In Preparation
                    </p>

                    <div className="mt-3">
                      {renderOrderDetails(order)}
                    </div>

                    <button
                      type="button"
                      className="btn btn-primary btn-full mt-5"
                      disabled={
                        updatingOrderId === order.id
                      }
                      onClick={() =>
                        performOrderAction(
                          order,
                          "ready"
                        )
                      }
                    >
                      Mark Ready
                    </button>
                  </article>
                ))}
              </div>
            </section>

            {/* Ready Orders */}
            <section className="form-card">
              <h2 className="section-title">
                Ready for Pickup
              </h2>

              <p className="body-text mt-2">
                Orders waiting for courier pickup.
              </p>

              {readyOrders.length === 0 && (
                <p className="body-text mt-5">
                  No orders are ready for pickup.
                </p>
              )}

              <div className="mt-5 flex flex-col gap-4">
                {readyOrders.map((order) => (
                  <article
                    key={order.id}
                    className="rounded-xl border p-4"
                  >
                    {renderOrderDetails(order)}
                  </article>
                ))}
              </div>
            </section>
          </div>
        )}
      </section>
    </main>
  );
}